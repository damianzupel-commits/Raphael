"""Worker de VOZ LOCAL: faster-whisper (voz -> texto) y Piper (texto -> voz), 100 % offline.

Corre como SUBPROCESO del orquestador (lo lanza `voice/engine.py`) con el intérprete que tenga las librerías
(`faster-whisper` y `piper-tts`: el venv del backend si las instalaste, o el del prototipo viejo `_Jarvis-Local`). Así el
orquestador liviano no carga ctranslate2/onnxruntime y los modelos quedan calientes entre pedidos.

Protocolo: una línea JSON por pedido en stdin, una línea JSON por respuesta en stdout (todo lo demás que imprima una
librería se desvía a stderr). Pedidos:
  {"id":1,"op":"check"}                                  -> qué hay disponible (sin cargar modelos)
  {"id":2,"op":"stt","path":"x.webm"}                    -> {"ok":true,"texto":"...","idioma":"es","segundos":1.8}
  {"id":3,"op":"tts","text":"hola","out":"salida.wav"}   -> {"ok":true,"path":"salida.wav"}

Config por entorno (la pasa el engine): VOICE_STT_MODEL (small), VOICE_STT_DEVICE (cpu: NO usa la GPU por default),
VOICE_STT_COMPUTE (int8), VOICE_STT_LANG (es), VOICE_PIPER_VOICE (ruta al .onnx), VOICE_TTS_SPEED (1.0).
Sin red: HF_HUB_OFFLINE=1 y los modelos se buscan solo en disco (`local_files_only`).
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import time
import traceback
import wave


def _cfg() -> dict:
    return {
        "stt_model": os.getenv("VOICE_STT_MODEL", "small"),
        "device": os.getenv("VOICE_STT_DEVICE", "cpu"),
        "compute": os.getenv("VOICE_STT_COMPUTE", "int8"),
        "lang": os.getenv("VOICE_STT_LANG", "es") or None,
        "voice": os.getenv("VOICE_PIPER_VOICE", ""),
        "speed": float(os.getenv("VOICE_TTS_SPEED", "1.0") or 1.0),
    }


_whisper = None
_piper = None


def op_check(c: dict) -> dict:
    out: dict = {"ok": True, "stt": {"ok": False}, "tts": {"ok": False}}
    if importlib.util.find_spec("faster_whisper") is None:
        out["stt"]["motivo"] = "falta el paquete faster-whisper (pip install -r backend/requirements-voice.txt)"
    else:
        try:
            from faster_whisper.utils import download_model

            download_model(c["stt_model"], local_files_only=True)  # solo mira el disco; no descarga nada
            out["stt"]["ok"] = True
        except Exception as exc:  # noqa: BLE001
            out["stt"]["motivo"] = (f"el modelo Whisper '{c['stt_model']}' no está descargado en este equipo "
                                    f"({type(exc).__name__}); bajalo una vez: Systran/faster-whisper-{c['stt_model']} (Hugging Face)")
    if importlib.util.find_spec("piper") is None:
        out["tts"]["motivo"] = "falta el paquete piper-tts (pip install -r backend/requirements-voice.txt)"
    elif not c["voice"] or not os.path.isfile(c["voice"]):
        out["tts"]["motivo"] = ("falta la voz es-AR de Piper (es_AR-daniela-high.onnx + .onnx.json): bajala de "
                                "huggingface.co/rhasspy/piper-voices (es/es_AR/daniela/high) y dejala en backend/data/voices/")
    else:
        out["tts"]["ok"] = True
        out["tts"]["voz"] = os.path.splitext(os.path.basename(c["voice"]))[0]
    return out


def op_stt(c: dict, req: dict) -> dict:
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel

        _whisper = WhisperModel(c["stt_model"], device=c["device"], compute_type=c["compute"], local_files_only=True)
    t0 = time.time()
    segs, info = _whisper.transcribe(req["path"], language=c["lang"], vad_filter=True, beam_size=1)
    texto = " ".join(s.text.strip() for s in segs).strip()
    return {"ok": True, "texto": texto, "idioma": info.language, "audio_segundos": round(info.duration, 2),
            "segundos": round(time.time() - t0, 2)}


def op_tts(c: dict, req: dict) -> dict:
    global _piper
    if _piper is None:
        from piper import PiperVoice

        cfg = c["voice"] + ".json"
        _piper = PiperVoice.load(c["voice"], config_path=cfg if os.path.isfile(cfg) else None)
    from piper.config import SynthesisConfig

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        _piper.synthesize_wav(req["text"], w, syn_config=SynthesisConfig(length_scale=1.0 / max(c["speed"], 0.1)))
    with open(req["out"], "wb") as f:
        f.write(buf.getvalue())
    return {"ok": True, "path": req["out"]}


def main() -> None:
    out = sys.stdout
    sys.stdout = sys.stderr  # el protocolo va SOLO por `out`; cualquier print de una librería no lo ensucia
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    c = _cfg()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        rid = None
        try:
            req = json.loads(line)
            rid = req.get("id")
            op = req.get("op")
            if op == "check":
                res = op_check(c)
            elif op == "stt":
                res = op_stt(c, req)
            elif op == "tts":
                res = op_tts(c, req)
            elif op == "ping":
                res = {"ok": True}
            else:
                res = {"ok": False, "error": f"operación desconocida: {op}"}
        except Exception as exc:  # noqa: BLE001 — un pedido fallido no tumba al worker
            traceback.print_exc(file=sys.stderr)
            res = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300]}
        res["id"] = rid
        out.write(json.dumps(res, ensure_ascii=False) + "\n")
        out.flush()


if __name__ == "__main__":
    main()
