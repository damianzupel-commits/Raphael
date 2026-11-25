"""Puerta de cada tanda: contrato del harness, ningún import ajeno y NINGUNA acción con efecto sin su nivel.

(a) todo `Action("x")` del código está declarado con nivel en el manifiesto (y todo lo declarado se usa);
(b) cada acción no automática queda pendiente y no tiene efecto hasta que la persona decide;
(c) los comandos de escritura los rechaza el harness si los pide el orquestador;
(d) lo `irreversible` nunca baja solo a automático por confianza progresiva (se propone y espera);
(e) los dos manifiestos (el del paquete y el de desarrollo) son idénticos.
"""

from __future__ import annotations

import ast
import sys
from datetime import timedelta

import pytest
from kit import BRIGADE_DIR, System
from raphael_core import Action, ActionError
from raphael_core.manifest import load_manifest
from raphael_core.testing.contract import run_contract_suite

from raphael_empresas.sample import MINIMAL

SRC = BRIGADE_DIR / "src" / "raphael_empresas"
MANIFEST = load_manifest(SRC / "manifest.yaml")
ALLOWED_IMPORTS = {"raphael_core", "raphael_empresas", "pydantic", "httpx", "yaml", "__future__"}


def _py_files():
    return sorted(SRC.rglob("*.py"))


def test_los_dos_manifiestos_son_el_mismo():
    assert (SRC / "manifest.yaml").read_bytes() == (BRIGADE_DIR / "manifest.yaml").read_bytes(), \
        "correr scripts/sync_manifest.py"


@pytest.mark.parametrize("edition", ["personal", "cloud"])
def test_suite_de_contrato(edition):
    r = run_contract_suite(BRIGADE_DIR, edition=edition, config=MINIMAL)
    assert r.ok, r.text()


def test_solo_importa_el_nucleo_y_la_stdlib():
    bad = []
    stdlib = set(sys.stdlib_module_names)
    for f in _py_files():
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module] if isinstance(node, ast.ImportFrom) and node.module and node.level == 0 else []
            for n in names:
                top = n.split(".")[0]
                if top not in ALLOWED_IMPORTS and top not in stdlib:
                    bad.append(f"{f.name}:{node.lineno} importa {n}")
    assert not bad, bad


def _action_literals() -> set[str]:
    found = set()
    for f in _py_files():
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Action" and node.args \
                    and isinstance(node.args[0], ast.Constant):
                found.add(node.args[0].value)
            if isinstance(node, ast.Compare) and isinstance(node.left, ast.Attribute) and node.left.attr == "type":
                found |= {c.value for c in node.comparators if isinstance(c, ast.Constant) and isinstance(c.value, str)}
    return found


def test_toda_accion_del_codigo_esta_declarada_con_nivel_y_viceversa():
    used = _action_literals()
    assert used - set(MANIFEST.actions) == set(), "acciones sin declarar en el manifiesto"
    assert set(MANIFEST.actions) - used == set(), "acciones declaradas que el código no usa"
    for name, spec in MANIFEST.actions.items():
        assert spec.level is not None and spec.description, name


def test_lo_que_sale_al_mundo_esta_etiquetado():
    tags = {a: set(s.tags) for a, s in MANIFEST.actions.items()}
    assert {"irreversible"} <= tags["confirmar_pago"]
    assert {"external", "irreversible"} <= tags["enviar_presupuesto"] and {"external", "irreversible"} <= tags["cancelar_pedido"]
    for a in ("responder_duda", "enviar_link_pago", "confirmar_turno", "enviar_recordatorio", "avisar_estado"):
        assert "external" in tags[a], a


# --- (b) cada acción no automática queda pendiente, sin efecto ---------------------------------------------------------
SHORT = {"orders": {"required_steps": ["prenda", "nombre"]}}


def _trigger(kind: str) -> System:
    x = System(SHORT)
    if kind == "responder_duda":
        x.receive("¿hacen arreglos de ruedos?")
    elif kind == "derivar_humano":
        x.receive("me llegó roto, quiero hablar con alguien")
    elif kind == "confirmar_turno":
        x.chat("quiero un turno para probarme", "el jueves a las 17")
    elif kind == "enviar_presupuesto":
        x.chat("quiero un vestido a medida", "Lu")
    elif kind == "confirmar_pago":
        x.publish("encargo.presupuesto_enviado", {"number": 1, "contact": "whatsapp:549341", "client": "Lu",
                                                  "price": 1000, "deposit": 500})
        x.receive("ya te transferí la seña")
    elif kind == "enviar_link_pago":
        x = System({**SHORT, "payments": {"deposit_pct": 50, "mercadopago": {"mode": "mock"}}})
        x.publish("encargo.presupuesto_enviado", {"number": 1, "contact": "whatsapp:549341", "client": "Lu",
                                                  "price": 1000, "deposit": 500})
    elif kind == "avisar_estado":
        x.chat("quiero un vestido a medida", "Lu")
        x.cmd("encargos", "estado", {"number": 1, "status": "listo"})
    elif kind == "enviar_recordatorio":
        x.receive("turno para probarme el 30/11 a las 10", sender="1")
        x.approve(x.pending()[0]["id"])
        x.clock.now += timedelta(days=9)
        x.tick()
    elif kind == "cancelar_pedido":
        x.chat("quiero un vestido a medida", "Lu")
        x.ctx("encargos").request(Action("cancelar_pedido", {"number": 1}, "Cancelar el encargo #1", "whatsapp:549341"))
    return x


NOT_AUTO = sorted(a for a, s in MANIFEST.actions.items() if s.level.value != "automatico")


@pytest.mark.parametrize("kind", NOT_AUTO)
def test_ninguna_accion_no_automatica_se_ejecuta_sin_ok(kind):
    x = _trigger(kind)
    mine = x.pending(kind)
    assert len(mine) == 1, (kind, x.pending())
    assert mine[0]["level"] == MANIFEST.actions[kind].level.value
    executed = [e for e in x.rt.audit.entries() if e["what"] == "accion_ejecutada" and e.get("tipo") == kind]
    assert executed == []


def test_cubre_todas_las_no_automaticas():
    assert set(NOT_AUTO) == {"responder_duda", "derivar_humano", "confirmar_turno", "enviar_presupuesto", "confirmar_pago",
                             "cancelar_pedido", "enviar_link_pago", "enviar_recordatorio", "avisar_estado"}


# --- (c) comandos de escritura -----------------------------------------------------------------------------------------
@pytest.mark.parametrize("cook,name,data", [("encargos", "estado", {"number": 1, "status": "listo"}),
                                            ("tienda", "sincronizar", {})])
def test_el_orquestador_no_corre_comandos_de_escritura(cook, name, data):
    x = System()
    assert MANIFEST.commands[name].read is False
    with pytest.raises(ActionError):
        x.cmd(cook, name, data, who="orquestador")


def test_todos_los_comandos_de_los_cocineros_estan_declarados():
    x = System()
    for cid, cook in x.rt.brigades["empresas"].cooks.items():
        assert set(cook.commands) <= set(MANIFEST.commands), cid


# --- (d) confianza progresiva ------------------------------------------------------------------------------------------
def test_lo_irreversible_no_baja_solo_a_automatico():
    x = System(trust={"enabled": True, "approvals_to_step_down": 2})
    for n in (1, 2):
        contact = f"whatsapp:{n}"
        x.publish("encargo.presupuesto_enviado", {"number": n, "contact": contact, "client": "Lu", "price": 1000,
                                                  "deposit": 500})
        x.receive("ya te transferí la seña", sender=str(n))
        x.approve(x.pending("confirmar_pago")[0]["id"])
    assert x.rt.policy.decide("empresas", "confirmar_pago").level.value == "aprobacion"
    assert any(p["kind"] == "trust" for p in x.rt.approvals.list())       # se propone y la dueña decide


def test_bajar_a_automatico_algo_irreversible_exige_confirmed_by():
    sin = System(autonomy={"empresas.confirmar_pago": "automatico"})      # sin confirmed_by: se ignora, con aviso
    assert sin.rt.policy.decide("empresas", "confirmar_pago").level.value == "aprobacion"
    x = System(autonomy={"empresas.confirmar_pago": {"level": "automatico", "confirmed_by": "Ana",
                                                     "confirmed_at": "2026-11-22"}})
    assert x.rt.policy.decide("empresas", "confirmar_pago").level.value == "automatico"
