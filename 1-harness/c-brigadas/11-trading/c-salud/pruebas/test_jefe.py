"""El jefe de Trading y sus efímeros: cada tool declarada está registrada y en la caja de alguien, el ruteo manda al
efímero correcto, las tools de lectura corren solas y lo que tiene efecto o gasta pide aprobación. Sin red ni modelo real:
el modelo es un guion."""

from __future__ import annotations

import json
from pathlib import Path

from raphael_core import Loader, Runtime
from raphael_core.contract import Level
from raphael_core.installation import installation_from
from raphael_core.manifest import load_manifest
from raphael_core.models import ModelGateway, Usage, models_from
from raphael_core.store import Store
from raphael_core.testing import Clock

from raphael_trading.spec import SPEC

BRIGADE_DIR = Path(__file__).resolve().parents[2] / "b-codigo"
ID = "trading"
PRIVATE = False
MANIFEST = load_manifest(BRIGADE_DIR / "manifest.yaml")
CONFIG = {}
EDITION = "personal"


class Script:
    """Transporte falso del modelo: `helper` contesta a los efímeros (pedidos con tools) y `chief` al jefe."""

    def __init__(self, helper=(), chief=()):
        self.helper, self.chief, self.calls = list(helper), list(chief), []

    def __call__(self, url, body, headers):
        self.calls.append({"url": url, "body": body})
        queue = self.helper if "tools" in body else self.chief
        r = queue.pop(0) if len(queue) > 1 else (queue[0] if queue else {"summary": "ok", "confidence": "low"})
        if isinstance(r, dict) and "choices" in r:
            return r
        return msg(r if isinstance(r, str) else json.dumps(r, ensure_ascii=False))


def msg(content="", calls=None):
    return {"choices": [{"message": {"content": content, "tool_calls": calls or []}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}}


def call(name, args, cid="c1"):
    return {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def gateway(transport, *, local: bool = True):
    providers = {"nube": {"base_url": "https://nube.example/v1", "model": "grande", "api_key_env": "K"}}
    if local:
        providers["casa"] = {"base_url": "http://127.0.0.1:11434/v1", "model": "chico"}
    cfg = {"providers": providers, "tiers": {"pago": ["nube"], "gratis": [], "local": ["casa"] if local else []},
           "roles": {r: ["pago", "local"] for r in ("mando", "voz", "ruteo", "jefe", "cocinero", "efimero")},
           "private": [ID] if PRIVATE else []}
    return ModelGateway(models_from(cfg), Usage(Store().space("_uso"), 1000, Clock()), env={"K": "k"}, transport=transport)


def montar(transport=None, *, local: bool = True):
    inst = installation_from({"id": "t", "edition": EDITION, "identity": {"assistant": "Raphael", "user": "Damian"},
                              "brigades": {ID: {"active": True, "config": CONFIG}}})
    rt = Runtime(inst, clock=Clock(), models=gateway(transport, local=local) if transport is not None else None)
    report = rt.run(Loader(rt, [BRIGADE_DIR], installed=False).apply())
    assert not report["errors"], report["errors"]
    return rt


def test_cada_tool_declarada_esta_registrada_y_en_la_caja_de_un_efimero():
    rt = montar()
    declaradas = {t.name for t in MANIFEST.tools}
    en_cajas = set().union(*(h.tools for h in SPEC.helpers))
    assert declaradas <= set(rt.tools.names()) and en_cajas == declaradas
    assert rt.status()["brigades"][ID]["chief"]
    assert all(h.private for h in SPEC.helpers) == PRIVATE and SPEC.private == PRIVATE


def test_las_tools_con_efecto_piden_aprobacion_y_las_de_lectura_no():
    for t in MANIFEST.tools:
        con_efecto = {"irreversible", "spend"} & {str(x.value if hasattr(x, "value") else x) for x in t.tags}
        assert not con_efecto or t.level is Level.APPROVAL, t.name
    assert set() == {t.name for t in MANIFEST.tools if t.level is not Level.AUTO}


def test_el_ruteo_manda_cada_pedido_a_su_efimero():
    assert SPEC.routing.classify("¿hay señal en USD/JPY?") == "analista"
    assert SPEC.routing.classify("¿qué posiciones tengo abiertas?") == "cartera"
    assert {h.mode for h in SPEC.helpers} == {"analista", "cartera"}


def test_una_tool_de_lectura_corre_sola_y_el_resultado_llega_al_modelo():
    t = Script(helper=[msg(calls=[call("trading_analizar", {"instrument": "USD/JPY"})]), msg("Listo.")],
               chief=[{"summary": "Reporte armado con lo que devolvió la tool.", "confidence": "medium"}])
    rt = montar(t)
    rep = rt.run(rt.ask(ID, "¿hay señal en USD/JPY?"))
    assert rt.approvals.list() == [] and not rep.degraded
    resultados = [m["content"] for c in t.calls for m in c["body"]["messages"] if m.get("role") == "tool"]
    assert resultados and not any("no está en la caja" in r or "no está cargada" in r for r in resultados)


def test_ninguna_tool_opera_y_pedir_una_orden_no_tiene_efecto():
    """Regla de Damián: Trading no ejecuta nada sin su aprobación, ni en demo. Los efímeros ni siquiera tienen cómo."""
    todas = {t.name for t in MANIFEST.tools}
    assert all(t.level is Level.AUTO for t in MANIFEST.tools)
    assert not any(p in n for n in todas for p in ("ejecutar", "cerrar", "enviar", "comprar", "vender"))
    t = Script(helper=[msg(calls=[call("ejecutar_orden", {"signal_id": "x", "units": 1000})]), msg("No pude.")],
               chief=[{"summary": "No se ejecutó nada.", "confidence": "high"}])
    rt = montar(t)
    rt.run(rt.ask(ID, "comprá 1000 USD/JPY ya"))
    assert rt.store.space(ID).list("orders") == [] and rt.approvals.list() == []
    resultados = [m["content"] for c in t.calls for m in c["body"]["messages"] if m.get("role") == "tool"]
    assert resultados and "no está en la caja" in resultados[0]


def test_el_analisis_dice_de_donde_salen_los_datos():
    rt = montar()
    r = rt.tools.get("trading_analizar").fn(instrument="USD/JPY")
    assert r["source"]["simulated"] is True and r["disclaimer"]
    assert rt.tools.get("trading_backtest").fn(candles=300)["warnings"]
