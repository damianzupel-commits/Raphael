"""Tests de la brigada de Seguridad (brigades/seguridad.py): ruteo, menor privilegio, cableado al registro y a las
tools reales, delegación en ayudantes. Sin LLM ni red: el ayudante se fakea y no se corre ningún escaneo."""

from __future__ import annotations

import asyncio
import re

import pytest

from brigades import chief as chief_mod
from brigades import registry
from brigades import seguridad as seg
from brigades.engine import GenericChief
from brigades.seguridad_scene import (
    ROUTING_DEFAULT, ROUTING_ESCANEO, ROUTING_REPORTE, UNAUTHORIZED_TARGETS, VALIDATION,
)


# --- ruteo --------------------------------------------------------------------
@pytest.mark.parametrize("msg", ROUTING_ESCANEO + ["Hacé un recon del 10.13.37.150", "Escanéame el host", "escaneá y hacé el reporte"])
def test_pedidos_de_escaneo_van_al_ayudante_de_escaneo(msg):
    assert seg.ROUTING.clasificar(msg) == "escaneo"


@pytest.mark.parametrize("msg", ROUTING_REPORTE + ROUTING_DEFAULT + ["Hacé el informe del escaneo de ayer", "", "hola"])
def test_reporte_y_ambiguos_van_al_ayudante_pasivo(msg):
    # 'escaneo' como SUSTANTIVO no es una orden de escanear; ante la duda, el ayudante que no toca la red
    assert seg.ROUTING.clasificar(msg) == "reporte"


# --- menor privilegio -----------------------------------------------------------
_PROHIBIDAS = re.compile(r"^(packet_capture|phone_|pc_run|fs_write|fs_|shell|desktop_|browser_|selfrepair|code_|metasploit|ssh)")


def test_las_tools_son_las_existentes_y_nada_de_explotacion_captura_ni_shell():
    assert seg.ESCANEO_TOOLS == {"nmap_scan", "zap_scan", "sqlmap_scan", "pentest_generate_report"}
    assert seg.REPORTE_TOOLS == {"pentest_generate_report"}  # el ayudante pasivo no puede escanear
    for tools in (seg.ESCANEO_TOOLS, seg.REPORTE_TOOLS, seg.SPEC.tool_names()):
        assert not [t for t in tools if _PROHIBIDAS.match(t)]
    assert seg.SPEC.tool_names() == seg.ESCANEO_TOOLS | seg.REPORTE_TOOLS


def test_las_tools_estan_registradas_tras_cargar_sus_modulos():
    seg.SPEC.ensure_tool_modules()
    from app.tools import get_tools

    assert seg.SPEC.tool_names() <= set(get_tools())


def test_ayudantes_efimeros_con_su_propia_allowlist():
    for a in seg.AYUDANTES.values():
        cfg = a.config()
        assert cfg.persistent is False and cfg.tool_names == a.tool_names()
        assert a.client_model.__module__.endswith("config")  # modelo LOCAL: los resultados de tu red no salen de la PC
    assert "authorized_targets.yaml" in seg.ESCANEO_PROMPT and "NUNCA explotás" in seg.ESCANEO_PROMPT
    assert "'detect'" in seg.ESCANEO_PROMPT and "'spider'" in seg.ESCANEO_PROMPT


# --- registro / molde -----------------------------------------------------------
def test_registrada_como_brigada_declarativa():
    assert "seguridad" in registry.available() and {"scout", "cerebro", "investigacion"} <= set(registry.available())
    assert registry.get_spec("seguridad") is seg.SPEC and seg.SPEC.delegating
    assert seg.SPEC.tool_modules == seg.TOOL_MODULES
    assert {s["modo"] for s in seg.describe_skills()} == {"escaneo", "reporte"}


def test_el_endpoint_generico_la_sirve():
    from app.routers import brigades as br

    assert "seguridad" in asyncio.run(br.brigade_list())["brigades"]


def test_escena_de_validacion_consistente_con_el_spec():
    ids = [s.id for s in VALIDATION.steps]
    assert ids == ["alcance", "ruteo", "gate", "reporte_simulado", "recon", "vuln", "web", "reporte", "e2e"]
    # los pasos que necesitan la VM traen prerrequisito (-> SIN VALIDAR); los 4 primeros no
    con_prereq = [s.id for s in VALIDATION.steps if s.prereq]
    assert con_prereq == ["recon", "vuln", "web", "reporte", "e2e"]
    assert VALIDATION.prerequisites == ()  # sin modelo ni red global
    assert all(t not in {"10.13.37.150"} for t in UNAUTHORIZED_TARGETS)


# --- delegación -----------------------------------------------------------------
class _FakeHelper:
    def __init__(self, tag):
        self.tag = tag

    async def run(self, message, on_event=None):
        await on_event({"type": "final", "reply": f"ok-{self.tag}"})
        return f"ok-{self.tag}", []


def _jefe(monkeypatch, tmp_path):
    monkeypatch.setattr(chief_mod, "_STATE_DIR", tmp_path)
    jefe = GenericChief.from_spec(seg.SPEC, client=None, model="x")
    jefe._spawn = lambda modo: _FakeHelper(modo)
    return jefe


def test_el_jefe_delega_en_el_ayudante_que_corresponde(monkeypatch, tmp_path):
    jefe = _jefe(monkeypatch, tmp_path)
    for msg, helper in (("Escaneá el 10.13.37.150", "seguridad-escaneo"), ("Armá el reporte", "seguridad-reporte")):
        events: list[dict] = []

        async def on_event(ev, _e=events):
            _e.append(ev)

        asyncio.run(jefe.run(msg, on_event=on_event))
        assert [e["name"] for e in events if e["type"] == "tool" and e["name"].startswith("delegar:")] == [f"delegar:{helper}"]


def test_un_ayudante_caido_no_tumba_al_jefe(monkeypatch, tmp_path):
    jefe = _jefe(monkeypatch, tmp_path)

    class Roto:
        async def run(self, message, on_event=None):
            raise RuntimeError("nmap no está instalado")

    jefe._spawn = lambda modo: Roto()
    reply, _ = asyncio.run(jefe.run("Escaneá el 10.13.37.150"))
    assert "falló: nmap no está instalado" in reply
