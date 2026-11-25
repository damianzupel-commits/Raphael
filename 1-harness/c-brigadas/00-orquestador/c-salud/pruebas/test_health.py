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


def test_seguridad_alerta_avisa_una_vez_y_con_la_gravedad():
    rt = master()
    ev = {"severity": "critical", "rule": "puerto-abierto", "message": "el puerto 22 está abierto al mundo", "fix": "cerralo"}
    for _ in range(2):
        run(rt.bus.apublish("seguridad.alerta", ev, source="seguridad"))
    run(rt._settle())
    [n] = rt.notices()
    assert n["text"] == "Alerta de seguridad (CRÍTICA): el puerto 22 está abierto al mundo. Arreglo sugerido: cerralo"
    run(rt.bus.apublish("seguridad.alerta", {**ev, "rule": "otra"}, source="seguridad"))
    run(rt._settle())
    assert len(rt.notices()) == 2


def test_eventos_de_autorreparacion_se_avisan():
    rt = master()
    run(rt.bus.apublish("arreglo.aplicado", {"id": "fx-1", "summary": "cambié un timeout"}, source="autorreparacion"))
    run(rt.bus.apublish("autodiagnostico.hallazgo", {"id": "hz-9", "summary": "loop de escritura"}, source="autorreparacion"))
    run(rt._settle())
    t = texts(rt)
    assert "Se aplicó un arreglo: cambié un timeout" in t and any(x.startswith("Autodiagnóstico") for x in t)


def test_exporta_el_registro_de_tool_calls_al_formato_de_la_introspeccion(tmp_path):
    import json

    from raphael_orchestrator import toolcalls
    entries = [{"n": 1, "what": "tool", "who": "osint", "when": "2026-11-25T10:00:00", "tool": "search"},
               {"n": 2, "what": "tool_fallida", "who": "osint", "when": "2026-11-25T10:01:00", "tool": "search", "error": "boom"},
               {"n": 3, "what": "evento", "who": "osint", "when": "2026-11-25T10:02:00"}]
    path = tmp_path / "sub" / "tools.jsonl"
    assert toolcalls.export_jsonl(entries, path) == 2
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["ok"] is True and rows[1] == {"timestamp": "2026-11-25T10:01:00", "conversation_id": "osint:2026-11-25",
                                                 "tool": "search", "ok": False, "arguments": {}, "error": "boom"}


def test_ingesta_fallo_avisa_una_vez_por_item():
    rt = master()
    ev = {"fuente": "youtube", "ref": "abc123", "titulo": "Charla sobre Rust", "motivo": "el video no tiene subtítulos"}
    for _ in range(2):
        run(rt.bus.apublish("ingesta.fallo", ev, source="ingesta"))
    run(rt.bus.apublish("ingesta.fallo", {**ev, "ref": "zzz", "titulo": ""}, source="ingesta"))
    run(rt._settle())
    t = texts(rt)
    assert t[0] == "No se pudo traer «Charla sobre Rust» de youtube: el video no tiene subtítulos" and len(t) == 2


def _talk(rt, text="buscá en la web algo de rust"):
    from test_o5 import say
    return say(rt, text)


def test_al_cerrar_un_turno_publica_memoria_turno(monkeypatch):
    from raphael_core.context import OrchestratorContext
    from test_o5 import good_script
    got = []
    monkeypatch.setattr(OrchestratorContext, "publish", lambda self, ev, data: got.append((ev, data)), raising=False)
    rt = master(good_script())
    r = _talk(rt)
    assert r.text and len(got) == 1
    ev, data = got[0]
    assert ev == "memoria.turno" and data["conv_id"] == "app" and data["dominio"] == "osint"
    assert data["history"][0] == {"role": "user", "content": "buscá en la web algo de rust"}
    assert data["history"][1]["role"] == "assistant" and data["history"][1]["content"] == r.text


def test_memoria_turno_se_puede_apagar_y_en_la_nube_no_va(monkeypatch):
    from raphael_core.context import OrchestratorContext
    from test_o5 import good_script
    got = []
    monkeypatch.setattr(OrchestratorContext, "publish", lambda self, ev, data: got.append(ev), raising=False)
    rt = master(good_script(), cfg={"memory": {"publish_turns": False}, "watchdog": {"poll_seconds": 0.01},
                                    "routing": {"classifier": False}})
    _talk(rt)
    rt2 = master(good_script(), edition="cloud")
    _talk(rt2)
    assert got == []


def test_sin_forma_de_publicar_el_turno_sigue_y_queda_anotado_una_vez():
    from test_o5 import good_script
    rt = master(good_script())
    assert _talk(rt).text
    _talk(rt)
    notes = [e for e in rt.audit.entries() if e["what"] == "memoria_turno_no_publicado"]
    assert len(notes) == 1


def test_si_publicar_falla_no_rompe_el_turno(monkeypatch):
    from raphael_core.context import OrchestratorContext
    from test_o5 import good_script

    def boom(self, ev, data):
        raise RuntimeError("bus caído")

    monkeypatch.setattr(OrchestratorContext, "publish", boom, raising=False)
    rt = master(good_script())
    assert _talk(rt).text
    assert any(e["what"] == "memoria_turno_fallido" for e in rt.audit.entries())
