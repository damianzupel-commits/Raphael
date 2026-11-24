"""Voz LOCAL del orquestador (voice/engine.py + endpoints /api/voz*). Sin modelos: se usa un worker FALSO que habla el mismo
protocolo JSON-lines. La prueba con los modelos reales (faster-whisper + Piper) corre solo si RUN_VOICE_REAL=1."""

from __future__ import annotations

import asyncio
import os
import sys
import textwrap
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from orquestador.server import create_app
from voice import engine as E

PORT = 8016
HOST = {"host": f"127.0.0.1:{PORT}"}
AUTH = {"Authorization": "Bearer tok", **HOST}

FAKE = textwrap.dedent('''
    import json, sys, os
    mode = os.environ.get("FAKE_MODE", "ok")
    for line in sys.stdin:
        req = json.loads(line)
        if mode == "crash":
            sys.exit(3)
        if mode == "hang":
            import time; time.sleep(60)
        op = req["op"]
        if op == "check":
            res = {"ok": True, "stt": {"ok": True}, "tts": {"ok": True, "voz": "fake"}}
        elif op == "stt":
            res = {"ok": True, "texto": "hola raphael " + str(os.path.getsize(req["path"])), "idioma": "es", "segundos": 0.1}
        elif op == "tts":
            open(req["out"], "wb").write(b"RIFF" + req["text"].encode("utf-8"))
            res = {"ok": True, "path": req["out"]}
        else:
            res = {"ok": False, "error": "nada"}
        res["id"] = req["id"]
        print(json.dumps(res), flush=True)
''')


@pytest.fixture
def fake_cmd(tmp_path):
    p = tmp_path / "fake_worker.py"
    p.write_text(FAKE, encoding="utf-8")
    return [sys.executable, str(p)]


def run(coro):
    return asyncio.run(coro)


# --- texto -> voz ---------------------------------------------------------------------------------------------------
def test_limpiar_para_voz_saca_markdown_codigo_urls_y_wikilinks():
    md = "## Resumen\n- **Rotación** cada `45` días\n- Fuente: [[Rotación de claves del servidor Orión]] y https://x.com/a\n```py\nprint(1)\n```\n| a | b |\n|---|---|\n| 1 | 2 |"
    t = E.limpiar_para_voz(md)
    for malo in ("##", "**", "`", "[[", "https", "print(1)", "---"):
        assert malo not in t
    assert "Rotación cada 45 días" in t and "Rotación de claves del servidor Orión" in t and "un enlace" in t


def test_limpiar_para_voz_recorta_en_un_limite_de_oracion():
    largo = ". ".join(f"Esta es la oración número {i}" for i in range(400))
    t = E.limpiar_para_voz(largo, max_chars=300)
    assert len(t) < 340 and t.endswith("Cortado por largo.") and E.limpiar_para_voz("") == ""


# --- qué intérprete y qué voz se usan --------------------------------------------------------------------------------
def test_pick_python_respeta_el_orden(monkeypatch, tmp_path):
    fake = tmp_path / "py.exe"
    fake.write_text("x")
    monkeypatch.setenv("VOICE_PYTHON", str(fake))
    assert E.pick_python() == str(fake)
    monkeypatch.setenv("VOICE_PYTHON", str(tmp_path / "no-existe.exe"))
    assert E.pick_python() is None                       # una ruta explícita rota no cae a otra en silencio
    monkeypatch.delenv("VOICE_PYTHON")
    monkeypatch.setattr(E.importlib.util, "find_spec", lambda m: object())
    assert E.pick_python() == sys.executable             # el Python actual ya tiene las librerías


def test_pick_voice_busca_en_el_orden_documentado(monkeypatch, tmp_path):
    v = tmp_path / "otra.onnx"
    v.write_text("x")
    monkeypatch.setenv("VOICE_PIPER_VOICE", str(v))
    assert E.pick_voice() == str(v)
    monkeypatch.delenv("VOICE_PIPER_VOICE")
    monkeypatch.setattr(E, "BACKEND", tmp_path)
    monkeypatch.setattr(E, "_PROTOTIPO", tmp_path / "proto")
    assert E.pick_voice() is None                         # sin voz: no inventa una
    (tmp_path / "data" / "voices").mkdir(parents=True)
    (tmp_path / "data" / "voices" / f"{E.VOICE_NAME}.onnx").write_text("x")
    assert E.pick_voice().endswith(f"{E.VOICE_NAME}.onnx")


# --- motor (con worker falso) -----------------------------------------------------------------------------------------
def test_status_transcribir_y_hablar_con_el_worker(fake_cmd):
    async def main():
        e = E.VoiceEngine(cmd=fake_cmd)
        st = await e.status()
        assert st["enabled"] and st["local"] and st["stt"]["ok"] and st["tts"]["voz"] == "fake"
        r = await e.transcribe(b"x" * 2500, ".webm")
        assert r["texto"] == "hola raphael 2500" and r["idioma"] == "es"
        wav = await e.speak("## Hola **Damián**")
        assert wav == b"RIFF" + "Hola Damián".encode("utf-8")  # el texto llegó LIMPIO a Piper
        await e.close()

    run(main())


def test_sin_audio_o_demasiado_grande_y_sin_nada_que_leer(fake_cmd):
    async def main():
        e = E.VoiceEngine(cmd=fake_cmd)
        with pytest.raises(E.VoiceError, match="no llegó audio"):
            await e.transcribe(b"")
        with pytest.raises(E.VoiceError, match="demasiado largo"):
            await e.transcribe(b"x" * (E.MAX_AUDIO_BYTES + 1))
        with pytest.raises(E.VoiceError, match="nada que leer"):
            await e.speak("```solo codigo```")
        await e.close()

    run(main())


def test_si_el_worker_muere_se_explica_y_se_relanza(fake_cmd, monkeypatch):
    async def main():
        monkeypatch.setenv("FAKE_MODE", "crash")
        e = E.VoiceEngine(cmd=fake_cmd)
        with pytest.raises(E.VoiceError, match="se cerró"):
            await e.transcribe(b"x" * 10)
        monkeypatch.setenv("FAKE_MODE", "ok")             # el próximo pedido relanza un worker sano
        assert (await e.transcribe(b"x" * 10))["texto"].startswith("hola")
        await e.close()

    run(main())


def test_si_el_worker_se_cuelga_hay_timeout_y_se_mata(fake_cmd, monkeypatch):
    async def main():
        monkeypatch.setenv("FAKE_MODE", "hang")
        e = E.VoiceEngine(cmd=fake_cmd)
        with pytest.raises(E.VoiceError, match="no respondió a tiempo"):
            await e._call({"op": "ping"}, timeout=0.5)
        assert e._proc is None
        await e.close()

    run(main())


def test_apagada_por_env_no_levanta_nada(monkeypatch, fake_cmd):
    monkeypatch.setenv("VOICE_ENABLED", "0")

    async def main():
        e = E.VoiceEngine(cmd=fake_cmd)
        st = await e.status()
        assert st["enabled"] is False and not st["stt"]["ok"] and "apagada" in st["tts"]["motivo"]
        with pytest.raises(E.VoiceError, match="apagada"):
            await e.speak("hola")
        assert e._proc is None                            # ni siquiera arrancó el worker

    run(main())


def test_sin_interprete_dice_exactamente_que_instalar(monkeypatch):
    monkeypatch.setattr(E, "pick_python", lambda: None)

    async def main():
        st = await E.VoiceEngine().status()
        assert not st["stt"]["ok"] and "pip install -r backend/requirements-voice.txt" in st["stt"]["motivo"]

    run(main())


# --- endpoints ---------------------------------------------------------------------------------------------------------
@pytest.fixture
def client(fake_cmd, monkeypatch):
    monkeypatch.setattr(E, "_ENGINE", E.VoiceEngine(cmd=fake_cmd))
    with TestClient(create_app(PORT, token="tok"), headers=HOST) as c:
        yield c


def test_endpoints_exigen_token(client):
    assert client.get("/api/voz").status_code in (401, 403)
    assert client.post("/api/voz/transcribir", content=b"x").status_code in (401, 403)
    assert client.post("/api/voz/hablar", json={"texto": "hola"}).status_code in (401, 403)


def test_endpoints_de_voz(client):
    assert client.get("/api/voz", headers=AUTH).json()["tts"]["ok"] is True
    r = client.post("/api/voz/transcribir", content=b"x" * 3000, headers={**AUTH, "Content-Type": "audio/webm;codecs=opus"})
    assert r.status_code == 200 and r.json()["texto"] == "hola raphael 3000"
    h = client.post("/api/voz/hablar", json={"texto": "## Hola"}, headers=AUTH)
    assert h.status_code == 200 and h.headers["content-type"] == "audio/wav" and h.content.startswith(b"RIFF")


def test_errores_de_voz_son_503_claros_y_el_resto_sigue(client, monkeypatch):
    monkeypatch.setenv("VOICE_ENABLED", "0")
    r = client.post("/api/voz/hablar", json={"texto": "hola"}, headers=AUTH)
    assert r.status_code == 503 and "apagada" in r.json()["detail"]
    assert client.get("/api/health").status_code == 200   # el orquestador no se entera


def test_audio_enorme_se_rechaza(client, monkeypatch):
    monkeypatch.setattr(E, "MAX_AUDIO_BYTES", 100)
    import voice.engine as ve

    r = client.post("/api/voz/transcribir", content=b"x" * 500, headers=AUTH)
    assert ve.MAX_AUDIO_BYTES == 100 and r.status_code == 413


def test_la_ui_tiene_el_microfono_y_el_toggle_de_lectura():
    ui = (Path(__file__).resolve().parent.parent / "orquestador" / "ui.html").read_text(encoding="utf-8")
    for pieza in ('id="vozchip"', 'class="mic"', "/api/voz/transcribir", "/api/voz/hablar", "getUserMedia", "MediaRecorder",
                  "toggleMic", "function hablar", "localStorage.setItem(\"leer\""):
        assert pieza in ui, pieza
    assert "if(leer && ev.reply) hablar(ev.reply)" in ui
    assert 'esc(j.texto)' in ui and "esc(e.name" in ui     # lo transcripto y los errores se muestran escapados


def test_el_orquestador_liviano_no_importa_las_librerias_de_voz():
    import subprocess

    code = "import sys; sys.path.insert(0, '.'); import voice.engine, orquestador.server; print(any(m in sys.modules for m in ('faster_whisper','piper','ctranslate2','onnxruntime')))"
    out = subprocess.run([sys.executable, "-I", "-c", code], cwd=Path(__file__).resolve().parent.parent, capture_output=True, text=True, timeout=60)
    assert out.stdout.strip() == "False", out.stderr[-300:]


@pytest.mark.skipif(os.getenv("RUN_VOICE_REAL") != "1", reason="usa los modelos reales (CPU): RUN_VOICE_REAL=1")
def test_real_ida_y_vuelta_piper_whisper():
    async def main():
        e = E.VoiceEngine()
        wav = await e.speak("Hola Damián, la rotación de claves es cada cuarenta y cinco días.")
        r = await e.transcribe(wav, ".wav")
        await e.close()
        assert "claves" in r["texto"].lower() and r["idioma"] == "es"

    run(main())
