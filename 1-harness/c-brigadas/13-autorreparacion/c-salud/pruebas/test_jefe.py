"""El jefe de Autorreparación y sus efímeros: cada tool declarada está registrada y en la caja de alguien, el ruteo manda al
efímero correcto, las tools de lectura corren solas y lo que tiene efecto o gasta pide aprobación. Sin red ni modelo real:
el modelo es un guion."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from raphael_core import Loader, Runtime
from raphael_core.contract import Level
from raphael_core.installation import installation_from
from raphael_core.manifest import load_manifest
from raphael_core.models import ModelGateway, Usage, models_from
from raphael_core.store import Store
from raphael_core.testing import Clock

from raphael_selfrepair.spec import SPEC

BRIGADE_DIR = Path(__file__).resolve().parents[2] / "b-codigo"
ID = "autorreparacion"
PRIVATE = True
MANIFEST = load_manifest(BRIGADE_DIR / "manifest.yaml")
CONFIG = {"root": tempfile.mkdtemp()}
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
    assert SPEC.routing.classify("¿qué patrones de falla hay en el registro?") == "introspeccion"
    assert SPEC.routing.classify("arreglá el bug de calc.py") == "proponer"
    assert {h.mode for h in SPEC.helpers} == {"proponer", "introspeccion"}


def test_una_tool_de_lectura_corre_sola_y_el_resultado_llega_al_modelo():
    t = Script(helper=[msg(calls=[call("autorreparacion_linea_roja", {"path": "app/auth.py"})]), msg("Listo.")],
               chief=[{"summary": "Reporte armado con lo que devolvió la tool.", "confidence": "medium"}])
    rt = montar(t)
    rep = rt.run(rt.ask(ID, "¿app/auth.py se puede tocar?"))
    assert rt.approvals.list() == [] and not rep.degraded
    resultados = [m["content"] for c in t.calls for m in c["body"]["messages"] if m.get("role") == "tool"]
    assert resultados and not any("no está en la caja" in r or "no está cargada" in r for r in resultados)


def test_sin_modelo_local_no_se_manda_nada_a_la_nube_y_el_reporte_sale_degradado():
    t = Script(helper=[msg("hola")], chief=[{"summary": "algo", "confidence": "high"}])
    rt = montar(t, local=False)
    rep = rt.run(rt.ask(ID, "¿qué patrones de falla hay?"))
    assert t.calls == [] and rep.degraded


def test_proponer_guarda_en_seco_y_no_toca_el_proyecto():
    root = Path(CONFIG["root"])
    (root / "calc.py").write_text("def total(items):\n    return sum(items) + 1\n", encoding="utf-8")
    args = {"file": "calc.py", "old_snippet": "    return sum(items) + 1\n", "new_snippet": "    return sum(items)\n",
            "rationale": "el total sumaba 1 de más"}
    t = Script(helper=[msg(calls=[call("autorreparacion_proponer", args)]), msg("Propuesta guardada.")],
               chief=[{"summary": "Propuse el arreglo; no se aplicó.", "confidence": "high"}])
    rt = montar(t)
    rt.run(rt.ask(ID, "arreglá el total de calc.py"))
    assert (root / "calc.py").read_text(encoding="utf-8").endswith("+ 1\n")        # el proyecto sigue igual
    [p] = rt.store.space(ID).list("proposals")
    assert p["status"] == "propuesta" and p["file"] == "calc.py" and rt.approvals.list() == []


def test_aplicar_y_revertir_no_son_tools():
    assert not {t.name for t in MANIFEST.tools} & {"aplicar_arreglo", "revertir_arreglo", "autorreparacion_aplicar"}
    assert not any("aplicar" in n or "revertir" in n for n in set().union(*(h.tools for h in SPEC.helpers)))
