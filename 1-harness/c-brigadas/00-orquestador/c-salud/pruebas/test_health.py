"""Salud y privacidad: qué falta se avisa, y lo privado nunca sale a la nube cuando no hay modelo local."""

from __future__ import annotations

import asyncio

import kit
from kit import Script, runtime
from test_o5 import ROUTING, master, say

from raphael_orchestrator import health
from raphael_orchestrator.config import config_from
from raphael_orchestrator.speech import MockSpeech, NoSpeech

LOCAL = {"providers": {"nube": {"base_url": "https://nube.example/v1", "model": "grande", "api_key_env": "K"},
                       "ollama": {"base_url": "http://localhost:11434/v1", "model": "llama3"}},
         "tiers": {"pago": [], "gratis": ["nube"], "local": ["ollama"]},
         "roles": {r: ["gratis", "local"] for r in ("mando", "voz", "ruteo", "jefe", "efimero")}}


def run(coro):
    return asyncio.run(coro)


def texts(rt):
    return [n["text"] for n in rt.notices()]


def test_sin_modelo_el_tick_avisa_una_vez_por_dia_y_sigue_por_reglas():
    rt = master(models=False)
    rt.run(rt.tick())
    rt.run(rt.tick())
    t = texts(rt)
    assert len(t) == 3 and all("sigo por reglas" in x for x in t)
    rt.clock.advance(hours=25)
    rt.run(rt.tick())
    assert len(texts(rt)) == 6


def test_con_modelo_no_avisa_y_se_puede_apagar_el_aviso():
    rt = master()
    rt.run(rt.tick())
    assert rt.notices() == []
    rt2 = master(models=False, cfg={"proactive": {"warn_no_ai": False}})
    rt2.run(rt2.tick())
    assert rt2.notices() == []


def test_brigada_privada_sin_modelo_local_avisa_y_no_manda_nada_a_la_nube():
    script = Script()
    rt = master(script, private=("osint",))
    rt.run(rt.tick())
    assert any("modelo local" in x and "NO se manda a la nube" in x for x in texts(rt))
    before = len(script.bodies)
    say(rt, "buscá en la web algo de rust")
    assert all("nube.example" not in str(b) for b in script.bodies[before:]) or script.bodies[before:] == []


def test_con_modelo_local_prendido_no_hay_aviso_de_privacidad(monkeypatch):
    monkeypatch.setattr(kit, "MODELS", LOCAL)
    rt = master(private=("osint",))
    rt.run(rt.tick())
    assert not any("modelo local" in x for x in texts(rt))


def test_health_report_cuenta_roles_privacidad_y_voz(monkeypatch):
    rt = runtime(routing=ROUTING, private=("osint",))
    cfg = config_from({})
    ctx = kit.owner(rt)
    r = run(health.report(ctx, cfg, MockSpeech()))
    assert r["ok"] and r["mode"] == "master" and r["roles"]["voz"]["available"]
    assert r["privacy"] == {"private_brigades": ["osint"], "local_model": False, "private_goes_to_cloud": False}
    assert any("modelo local" in w for w in r["warnings"])
    r2 = run(health.report(ctx, cfg, NoSpeech("sin paquetes")))
    assert any("Voz hablada" in w and "sin paquetes" in w for w in r2["warnings"])


def test_health_sin_claves_lista_los_roles_sin_modelo():
    rt = runtime(models=False)
    r = run(health.report(kit.owner(rt), config_from({})))
    assert not any(v["available"] for v in r["roles"].values()) and len(r["warnings"]) == 3


def test_los_ejemplos_enchufables_son_validos_y_lo_privado_exige_local():
    import pathlib

    import yaml
    from raphael_core.models import models_from

    code = pathlib.Path(health.__file__).resolve().parents[2]
    models = models_from(yaml.safe_load((code / "modelos.personal.ejemplo.yaml").read_text(encoding="utf-8")))
    assert models.tiers["local"] == ["local-ollama"] and "memoria" in models.private
    assert config_from(yaml.safe_load((code / "orquestador.config.ejemplo.yaml").read_text(encoding="utf-8"))).mode == "master"
    env = (code / "orquestador.env.plantilla").read_text(encoding="utf-8")
    assert all(ln.split("=", 1)[1].strip() == "" or ln.startswith(("RAPHAEL_VOZ_MODO", "VOICE_")) for ln in env.splitlines()
               if "=" in ln and not ln.startswith("#"))   # ninguna clave real en la plantilla
