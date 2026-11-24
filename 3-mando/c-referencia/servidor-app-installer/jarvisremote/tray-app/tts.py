"""TTS local para Raphael -- Fase 1 de docs/SPEC-RAPHAEL-VOZ.md

Le da VOZ DE SALIDA a Raphael (que hable sus respuestas), con la misma filosofía
100% local del resto: motor **Piper** (offline, gratis).

Diseño robusto a propósito: si falta el paquete `piper-tts` o el modelo de voz,
`speak()` NO habla y NO rompe el loop de voz -- solo loguea un warning. Así la
escucha (voice_listener.py) sigue funcionando aunque el TTS todavía no esté listo.

Config por variables de entorno (opcionales):
  TTS_ENABLED       "false" para apagar la voz (default: on)
  TTS_PIPER_MODEL   ruta a un .onnx de Piper (default: models/tts/*.onnx)
  TTS_MAX_CHARS     tope de caracteres a leer en voz alta (default: 600). Los
                    resultados largos se resumen/guardan en archivo en la Fase 3;
                    hasta entonces esto evita que lea un informe entero.
"""

import io
import logging
import os
import re
import threading
import wave
from pathlib import Path

logger = logging.getLogger("jarvis.tts")

_ENABLED = os.getenv("TTS_ENABLED", "true").lower() not in ("0", "false", "no")
_MODEL_ENV = os.getenv("TTS_PIPER_MODEL", "").strip()
_MAX_CHARS = int(os.getenv("TTS_MAX_CHARS", "600"))

# Motor de voz: "piper" (local, offline, default) o "edge" (edge-tts: voces
# neuronales de Microsoft, más naturales, con acento AR -- necesita internet).
# Para probar edge sin cambios permanentes, lanzá la tray con la variable seteada:
#   $env:TTS_ENGINE="edge"; .venv\Scripts\pythonw.exe tray.py
_ENGINE = os.getenv("TTS_ENGINE", "piper").strip().lower()
_EDGE_VOICE = os.getenv("TTS_EDGE_VOICE", "es-AR-TomasNeural").strip()  # rioplatense
_EDGE_RATE = os.getenv("TTS_EDGE_RATE", "+0%").strip()

_voice = None
_load_lock = threading.Lock()
_play_lock = threading.Lock()  # que dos respuestas no se reproduzcan encimadas

# Nivel de audio EN VIVO mientras Raphael habla (0.0 = silencio, 1.0 = fuerte).
# El orbe lo lee (tts.get_level()) para expandirse/latir al ritmo de la voz.
_level = 0.0


def get_level() -> float:
    """Nivel de audio actual de la voz (0..1). 0 cuando no está hablando."""
    return _level


def _default_model_path() -> Path | None:
    """Ruta al modelo de voz Piper. Prioriza TTS_PIPER_MODEL; si no, el primer
    .onnx dentro de tray-app/models/tts/."""
    if _MODEL_ENV and Path(_MODEL_ENV).exists():
        return Path(_MODEL_ENV)
    base = Path(__file__).parent / "models" / "tts"
    if base.is_dir():
        found = sorted(base.glob("*.onnx"))
        if found:
            return found[0]
    return None


def _get_voice():
    global _voice
    if _voice is not None:
        return _voice
    with _load_lock:
        if _voice is not None:
            return _voice
        try:
            from piper import PiperVoice
        except Exception:
            logger.warning(
                "piper-tts no está instalado; Raphael no va a hablar. "
                "Instalá con: pip install piper-tts"
            )
            return None
        model = _default_model_path()
        if model is None:
            logger.warning(
                "no hay modelo de voz Piper (models/tts/*.onnx). "
                "Corré tray-app/download_tts_voice.py para bajar una voz en español."
            )
            return None
        try:
            _voice = PiperVoice.load(str(model))
            logger.info("voz Piper cargada: %s", model.name)
        except Exception:
            logger.exception("no se pudo cargar la voz Piper (%s)", model)
            return None
    return _voice


def is_available() -> bool:
    if not _ENABLED:
        return False
    if _ENGINE == "edge":
        try:
            import edge_tts  # noqa: F401
            return True
        except Exception:
            return False
    return _get_voice() is not None


# Emojis y pictogramas: rangos Unicode que Piper leería como nombres raros o
# ruiditos. Los sacamos para que la voz suene natural.
_EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"   # emoticons, pictogramas, transporte, símbolos suplementarios
    "\U00002600-\U000027BF"   # símbolos misc + dingbats
    "\U00002190-\U000021FF"   # flechas
    "\U00002B00-\U00002BFF"   # símbolos y flechas misc
    "\U0001F1E6-\U0001F1FF"   # banderas (indicadores regionales)
    "\U0000FE00-\U0000FE0F"   # selectores de variación
    "\U00002000-\U0000206F"   # puntuación general rara (incluye ZWJ)
    "\U00002300-\U000023FF"   # símbolos técnicos misc (⏰, ⌨, etc.)
    "]+",
    flags=re.UNICODE,
)

_MD_PATTERNS = [
    (re.compile(r"```.*?```", re.S), " "),   # bloques de código
    (re.compile(r"`([^`]*)`"), r"\1"),        # código inline
    (re.compile(r"\[([^\]]+)\]\([^)]+\)"), r"\1"),  # links -> texto
    (re.compile(r"[*_#>`~|]+"), " "),         # énfasis/headers/símbolos de markdown sueltos
    (re.compile(r"[•▪◦·–—]+"), " "),  # viñetas y guiones largos
    (re.compile(r"\s+"), " "),                # colapsar espacios
]


def _clean_for_speech(text: str) -> str:
    """Prepara el texto para la voz: saca emojis, markdown y símbolos sueltos (que
    Piper leería como 'asterisco' o ruiditos), y recorta a un tope (el detalle largo
    se maneja en la Fase 3: resumen + archivo)."""
    out = text or ""
    out = _EMOJI_RE.sub(" ", out)  # emojis primero
    for pat, repl in _MD_PATTERNS:
        out = pat.sub(repl, out)
    out = out.strip()
    if _MAX_CHARS and len(out) > _MAX_CHARS:
        corte = out[:_MAX_CHARS].rsplit(" ", 1)[0]
        out = corte + "… (te dejé el resto por escrito)"
    return out


def _synthesize_pcm(voice, text: str):
    """Devuelve (np.int16, sample_rate) o None. Soporta varias APIs de piper-tts:
    la vieja (rhasspy: synthesize_stream_raw / synthesize a WAV) y la nueva
    (piper 1.x / OHF-Voice: synthesize -> AudioChunk, synthesize_wav)."""
    import numpy as np

    sr_default = getattr(getattr(voice, "config", None), "sample_rate", 22050)

    # API VIEJA: synthesize_stream_raw(text) -> bytes int16
    if hasattr(voice, "synthesize_stream_raw"):
        try:
            chunks = [np.frombuffer(b, dtype=np.int16) for b in voice.synthesize_stream_raw(text)]
            if chunks:
                return np.concatenate(chunks), sr_default
        except Exception:
            logger.exception("piper synthesize_stream_raw (API vieja) falló")

    # API NUEVA (piper 1.x): synthesize(text) -> iterable de AudioChunk
    try:
        chunks = []
        sr = sr_default
        for chunk in voice.synthesize(text):
            raw = getattr(chunk, "audio_int16_bytes", None)
            if raw is None and isinstance(chunk, (bytes, bytearray)):
                raw = bytes(chunk)
            if raw:
                chunks.append(np.frombuffer(raw, dtype=np.int16))
                sr = getattr(chunk, "sample_rate", sr)
        if chunks:
            return np.concatenate(chunks), sr
    except Exception:
        logger.exception("piper synthesize (API nueva) falló")

    # API NUEVA alternativa: synthesize_wav(text, wav_file) -> escribe WAV
    try:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            voice.synthesize_wav(text, wf)
        buf.seek(0)
        with wave.open(buf, "rb") as wf:
            sr = wf.getframerate()
            frames = wf.readframes(wf.getnframes())
        return np.frombuffer(frames, dtype=np.int16), sr
    except Exception:
        logger.exception("piper synthesize_wav falló")
        return None


def _edge_synthesize_pcm(text: str):
    """Sintetiza con edge-tts (voces neuronales de Microsoft) y decodifica el mp3
    a PCM int16 con ffmpeg. Devuelve (np.int16, sr) o None. Necesita internet,
    el paquete `edge-tts`, y ffmpeg en el PATH (ya lo está en esta máquina)."""
    import asyncio
    import subprocess

    import numpy as np

    try:
        import edge_tts
    except Exception:
        logger.warning("edge-tts no está instalado; instalá con: pip install edge-tts")
        return None

    async def _collect() -> bytes:
        data = bytearray()
        com = edge_tts.Communicate(text, _EDGE_VOICE, rate=_EDGE_RATE)
        async for chunk in com.stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                data.extend(chunk["data"])
        return bytes(data)

    try:
        mp3 = asyncio.run(_collect())
    except Exception:
        logger.exception("edge-tts falló al sintetizar (¿internet? ¿voz válida?)")
        return None
    if not mp3:
        return None

    target_sr = 22050
    try:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
             "-f", "s16le", "-ac", "1", "-ar", str(target_sr), "pipe:1"],
            input=mp3, capture_output=True,
        )
        if proc.returncode != 0 or not proc.stdout:
            logger.error("ffmpeg no pudo decodificar el mp3 de edge-tts: %s",
                         proc.stderr.decode(errors="ignore")[:200])
            return None
        return np.frombuffer(proc.stdout, dtype=np.int16), target_sr
    except FileNotFoundError:
        logger.error("ffmpeg no está en el PATH; edge-tts necesita ffmpeg para reproducir.")
        return None
    except Exception:
        logger.exception("fallo decodificando el audio de edge-tts")
        return None


def speak(text: str) -> None:
    """Sintetiza y reproduce `text` en voz alta (bloqueante). NUNCA lanza: ante
    cualquier problema, loguea y sigue -- el loop de voz no se puede caer por esto.
    Usa el motor `_ENGINE` (piper local por default, o edge-tts si TTS_ENGINE=edge)."""
    if not _ENABLED:
        return
    clean = _clean_for_speech(text)
    if not clean:
        return
    try:
        if _ENGINE == "edge":
            result = _edge_synthesize_pcm(clean)
        else:
            voice = _get_voice()
            result = _synthesize_pcm(voice, clean) if voice is not None else None
        if result is None:
            return
        audio, sr = result
        with _play_lock:
            _play_with_level(audio, sr)
    except Exception:
        logger.exception("TTS falló al reproducir")


def _play_with_level(audio, sr) -> None:
    """Reproduce el audio en bloques de ~30ms y va publicando el nivel (RMS) en
    `_level`, para que el orbe pueda latir al ritmo de la voz. Si algo falla,
    cae a sd.play() simple. Siempre deja `_level` en 0 al terminar."""
    global _level
    import numpy as np
    import sounddevice as sd

    block = max(1, int(sr * 0.03))  # 30 ms
    stream = None
    try:
        stream = sd.OutputStream(samplerate=sr, channels=1, dtype="int16")
        stream.start()
        for i in range(0, len(audio), block):
            chunk = audio[i:i + block]
            stream.write(chunk)
            if len(chunk):
                rms = float(np.sqrt(np.mean((chunk.astype(np.float32) / 32768.0) ** 2)))
                _level = min(1.0, rms * 3.5)  # escalar a un rango visible
        stream.stop()
    except Exception:
        logger.exception("reproducción por bloques falló; caigo a sd.play simple")
        try:
            sd.play(audio, sr)
            sd.wait()
        except Exception:
            logger.exception("sd.play falló")
    finally:
        _level = 0.0
        if stream is not None:
            try:
                stream.close()
            except Exception:
                pass
