"""Voz hablada enchufable: adaptador simulado, worker falso por el protocolo real, y qué pasa si falta algo."""

from __future__ import annotations

import asyncio
import sys
import textwrap

import pytest

from raphael_orchestrator import config_from, speech
from raphael_orchestrator.speech import LocalSpeech, MockSpeech, NoSpeech, SpeechError


def run(coro):
    return asyncio.run(coro)


FAKE = textwrap.dedent('''
    import json, sys, os
    mode = os.environ.get("FAKE_MODE", "ok")
    for line in sys.stdin:
        req = json.loads(line)
        if mode == "crash":
            sys.exit(3)
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


def test_la_limpieza_saca_markdown_codigo_y_urls():
    t = speech.clean_for_speech("# Título\n- punto **uno**\n```py\nx=1\n```\nmirá https://a.com/x y [[nota]]")
    assert "```" not in t and "https" not in t and "*" not in t and "#" not in t
    assert "un enlace" in t and "nota" in t


def test_la_limpieza_corta_en_limite_de_oracion():
    t = speech.clean_for_speech("Hola. " * 400, max_chars=100)
    assert len(t) < 140 and t.endswith("Cortado por largo.")


def test_mock_oye_y_habla_sin_modelos():
    s = MockSpeech(heard="abrí el panel")
    assert run(s.transcribe(b"audio"))["texto"] == "abrí el panel"
    assert run(s.speak("**Listo** https://x.org")).startswith(b"RIFF")
    assert s.spoken == ["Listo un enlace"]
    assert run(s.status())["stt"]["mock"] is True
    with pytest.raises(SpeechError):
        run(s.transcribe(b""))
    with pytest.raises(SpeechError):
        run(s.speak("```solo código```"))


def test_apagada_dice_el_motivo_y_no_lanza_al_consultar_el_estado():
    s = NoSpeech("apagada")
    assert run(s.status())["stt"] == {"ok": False, "motivo": "apagada"}
    with pytest.raises(SpeechError, match="apagada"):
        run(s.speak("hola"))


def test_local_con_worker_falso_habla_el_protocolo(fake_cmd):
    async def go():
        s = LocalSpeech(cmd=fake_cmd)
        try:
            st = await s.status()
            heard = await s.transcribe(b"12345", ".ogg")
            wav = await s.speak("Hola **Damián**")
            return st, heard, wav
        finally:
            await s.close()

    st, heard, wav = run(go())
    assert st["stt"]["ok"] and st["tts"]["voz"] == "fake"
    assert heard["texto"] == "hola raphael 5" and wav == "RIFFHola Damián".encode()


def test_si_el_worker_muere_avisa_claro_y_se_relanza(fake_cmd):
    async def go():
        s = LocalSpeech(cmd=fake_cmd, env={"FAKE_MODE": "crash"})
        try:
            with pytest.raises(SpeechError, match="se cerró"):
                await s.speak("hola")
            s._env_extra["FAKE_MODE"] = "ok"
            return await s.speak("hola de nuevo")
        finally:
            await s.close()

    assert run(go()) == b"RIFFhola de nuevo"


def test_local_sin_python_con_las_librerias_dice_que_instalar():
    async def go():
        s = LocalSpeech(python=None)
        s._python = None
        return await s.status()

    # sin VOICE_PYTHON ni los paquetes en este entorno: el estado lo explica, no lanza
    st = run(go())
    if st["stt"]["ok"]:
        pytest.skip("este entorno sí tiene las librerías de voz")
    assert "Instalá" in st["stt"]["motivo"] or "falta" in st["stt"]["motivo"]


def test_speech_from_elige_adaptador_y_no_adivina():
    assert isinstance(speech.speech_from("mock", {}), MockSpeech)
    assert isinstance(speech.speech_from("off", {}), NoSpeech)
    assert isinstance(speech.speech_from("mock", {"VOICE_ENABLED": "0"}), NoSpeech)
    assert isinstance(speech.speech_from("off", {"RAPHAEL_VOZ_MODO": "mock"}), MockSpeech)   # la variable gana
    auto = speech.speech_from("auto", {"VOICE_PYTHON": "/no/existe"})
    assert isinstance(auto, NoSpeech) and "sigo por texto" in auto.reason
    with pytest.raises(ValueError, match="desconocido"):
        speech.speech_from("auto", {"RAPHAEL_VOZ_MODO": "xyz"})


def test_la_config_acepta_speech_y_rechaza_modos_raros():
    assert config_from({"speech": {"mode": "mock"}}).speech.mode == "mock"
    with pytest.raises(ValueError):
        config_from({"speech": {"mode": "nube"}})
