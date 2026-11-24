"""El DAG del reparto y el control del mando: puerta de O3 (parte 1). Sin red ni modelos reales.

Lo de JR (`mando.repartir`, `_dependencias`, `concluir`) no tenía tests en la copia: estos son nuevos, con los casos que
pide el DISENO (ciclos, dependencias raras, presupuesto) y los controles del mando (inventos, señal de su brigada).
"""

from __future__ import annotations

import asyncio
import json

import pytest
from kit import CEREBRO_ROUTING, INVESTIGACION_ROUTING, catalog_entry
from raphael_core.engine.reports import REPORT_VERSION, InternalReport

from raphael_orchestrator import command
from raphael_orchestrator.joint import combine_reports
from raphael_orchestrator.plan import Plan, apply_budget, topological_levels, validate_after
from raphael_orchestrator.routing import candidates

NODES = ["a", "b", "c"]
CANDS = candidates([catalog_entry("memoria-cerebro", CEREBRO_ROUTING), catalog_entry("investigacion", INVESTIGACION_ROUTING)])
PURPOSES = {"memoria-cerebro": "lo que ya está en tus notas", "investigacion": "web y casos"}
REQUEST = "Fijate en mis notas qué servidores tengo y buscá en la web vulnerabilidades de esos"


def run(coro):
    return asyncio.run(coro)


class Model:
    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    async def __call__(self, messages):
        self.calls.append(messages)
        r = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(r, Exception):
            raise r
        return r if r is None or isinstance(r, str) else json.dumps(r, ensure_ascii=False)


# --- validación de dependencias ---
def test_sin_dependencias_todo_va_en_paralelo():
    assert validate_after(None, NODES) == ({}, "") and validate_after({}, NODES) == ({}, "")
    assert Plan({n: "x" for n in NODES}, "model").levels() == [NODES]


def test_dependencias_validas_se_ordenan_por_niveles_y_las_repetidas_se_juntan():
    deps, problem = validate_after({"c": ["a", "b", "a"], "b": ["a"]}, NODES)
    assert problem == "" and deps == {"c": ("a", "b"), "b": ("a",)}
    assert topological_levels(NODES, deps) == [["a"], ["b"], ["c"]]
    deps, _ = validate_after({"c": ["a"]}, NODES)
    assert topological_levels(NODES, deps) == [["a", "b"], ["c"]]


@pytest.mark.parametrize("raw,problem", [
    ({"a": ["b"], "b": ["a"]}, "ciclo"),
    ({"a": ["b"], "b": ["c"], "c": ["a"]}, "ciclo"),
    ({"a": ["a"]}, "sí misma"),
    ({"a": ["zeta"]}, "no es una brigada del plan"),
    ({"zeta": ["a"]}, "no es una brigada del plan"),
    ({"a": "b"}, "no son una lista"),
    ({"a": []}, "no son una lista"),
    ({"a": [3]}, "no es una brigada del plan"),
    (["a", "b"], "no son un objeto"),
    ("a antes de b", "no son un objeto"),
])
def test_cualquier_cosa_rara_en_las_dependencias_se_descarta(raw, problem):
    deps, why = validate_after(raw, NODES)
    assert deps == {} and problem in why


def test_un_ciclo_que_se_cuele_no_se_ejecuta():
    with pytest.raises(ValueError, match="ciclo"):
        topological_levels(NODES, {"a": ("b",), "b": ("a",)})


# --- presupuesto ---
def test_el_presupuesto_recorta_brigadas_y_etapas_y_lo_dice():
    tasks = {f"b{i}": "x" for i in range(6)}
    p = apply_budget(Plan(tasks, "model", {"b1": ("b0",), "b5": ("b1",)}), max_brigades=3, max_levels=5)
    assert list(p.tasks) == ["b0", "b1", "b2"] and p.after == {"b1": ("b0",)}
    assert any("quedaron afuera b3, b4, b5" in w for w in p.warnings)
    chain = {"a": ("b",), "b": ("c",)}
    p = apply_budget(Plan({"a": "x", "b": "x", "c": "x"}, "model", chain), max_brigades=5, max_levels=2)
    assert p.after == {} and p.levels() == [["a", "b", "c"]] and any("3 etapas" in w for w in p.warnings)


# --- repartir ---
GOOD = {"memoria-cerebro": "Fijate en mis notas qué servidores tengo",
        "investigacion": "Buscá en la web vulnerabilidades de esos servidores",
        "after": {"investigacion": ["memoria-cerebro"]}}


def test_el_mando_reparte_y_propone_dependencias_validas():
    m = Model(GOOD)
    p = run(command.split(REQUEST, PURPOSES, llm=m, cands=CANDS, user="Damián"))
    assert p.via == "model" and p.tasks["investigacion"].startswith("Buscá en la web")
    assert p.after == {"investigacion": ("memoria-cerebro",)} and p.levels() == [["memoria-cerebro"], ["investigacion"]]
    system, user = m.calls[0]
    assert "REPARTIRLO" in system["content"] and user["content"].count("<<<DATO") == 2


def test_una_sub_tarea_que_inventa_o_pierde_su_senal_se_reemplaza_por_el_pedido_y_no_hay_dag():
    bad = {**GOOD, "investigacion": "Buscá las 300 vulnerabilidades de 2024"}   # cifras que el pedido no tiene
    p = run(command.split(REQUEST, PURPOSES, llm=Model(bad), cands=CANDS))
    assert p.via == "model+request" and p.tasks["investigacion"] == REQUEST and p.after == {}
    assert any("investigacion no pasó el control" in w for w in p.warnings)
    lost = {**GOOD, "investigacion": "Buscá vulnerabilidades de esos servidores"}   # sin «en la web»
    p = run(command.split(REQUEST, PURPOSES, llm=Model(lost), cands=CANDS))
    assert p.tasks["investigacion"] == REQUEST
    long_ = {**GOOD, "memoria-cerebro": "en mis notas " + "x" * 500}
    assert run(command.split(REQUEST, PURPOSES, llm=Model(long_), cands=CANDS)).tasks["memoria-cerebro"] == REQUEST


@pytest.mark.parametrize("answer", [None, "no sé repartir", RuntimeError("429"), ["lista"]])
def test_sin_reparto_del_modelo_cada_brigada_recibe_el_pedido_entero(answer):
    p = run(command.split(REQUEST, PURPOSES, llm=Model(answer), cands=CANDS))
    assert p.via == "request" and set(p.tasks.values()) == {REQUEST} and p.after == {}
    assert p.warnings


def test_sin_modelo_o_con_dag_apagado():
    p = run(command.split(REQUEST, PURPOSES, llm=None))
    assert p.via == "request" and p.warnings == []
    p = run(command.split(REQUEST, PURPOSES, llm=Model(GOOD), cands=CANDS, dag=False))
    assert p.via == "model" and p.after == {}


def test_dependencias_raras_del_modelo_quedan_en_paralelo_con_aviso():
    cyc = {**GOOD, "after": {"investigacion": ["memoria-cerebro"], "memoria-cerebro": ["investigacion"]}}
    p = run(command.split(REQUEST, PURPOSES, llm=Model(cyc), cands=CANDS))
    assert p.via == "model" and p.after == {} and any("ciclo" in w for w in p.warnings)


# --- concluir ---
def _rep(brigade, summary, conf="high", **kw):
    return InternalReport.validate({"version": REPORT_VERSION, "brigade": brigade, "summary": summary, "confidence": conf, **kw})


REPORTS = [("Cerebro", _rep("memoria-cerebro", "Tenés 2 servidores: Orión y Vega.")),
           ("Investigación", _rep("investigacion", "Orión tiene la CVE-2024-6387 sin parchear.", "medium"))]


def test_la_conclusion_usa_solo_lo_de_los_reportes():
    m = Model({"conclusion": "De tus 2 servidores, Orión tiene la CVE-2024-6387 sin parchear.", "confidence": "medium"})
    text, conf, why = run(command.conclude(REPORTS, "¿qué servidores tengo vulnerables?", llm=m))
    assert text.startswith("De tus 2") and conf == "medium" and why == ""
    assert "REPORTES DE LAS BRIGADAS" in m.calls[0][1]["content"]


def test_una_conclusion_que_inventa_se_reintenta_y_si_no_se_corrige_no_hay():
    m = Model({"conclusion": "Tenés 5 servidores vulnerables.", "confidence": "high"},
              {"conclusion": "Orión tiene la CVE-2024-6387.", "confidence": "high"})
    text, _conf, _ = run(command.conclude(REPORTS, "x", llm=m))
    assert text == "Orión tiene la CVE-2024-6387." and "5" in m.calls[1][-1]["content"]
    for bad in ({"conclusion": "Hay 9.", "confidence": "high"}, {"conclusion": "x" * 800, "confidence": "high"},
                {"conclusion": "Orión.", "confidence": "altísima"}, {"conclusion": "", "confidence": "low"}):
        text, conf, why = run(command.conclude(REPORTS, "x", llm=Model(bad)))
        assert text == "" and "no pasó el control" in why
    assert run(command.conclude(REPORTS, "x", llm=None))[0] == ""
    assert run(command.conclude(REPORTS, "x", llm=Model(None)))[2] == "no hay modelo para el mando"


# --- combinar reportes ---
def test_combinar_reportes_no_inventa_y_conserva_los_numeros_reales_de_los_pendientes():
    src = {"type": "url", "ref": "https://ejemplo.org/cve", "title": "CVE", "excerpt": ""}
    a = _rep("memoria-cerebro", "Tenés 2 servidores.", sources=[src],
             findings=[{"text": "Orión y Vega", "helper": "h", "sources": [src["ref"]]}],
             pending_proposals=[{"type": "other", "id": "7", "description": "parchear Orión", "pending_id": 7}])
    b = _rep("investigacion", "Orión es vulnerable.", "low", sources=[src],
             pending_proposals=[{"type": "other", "id": "7", "description": "parchear Orión", "pending_id": 7},
                                {"type": "fix", "id": "FIX-1", "description": "otra cosa"}],
             failures=[{"helper": "investigacion-scout", "reason": "timeout", "detail": "no terminó"}], degraded=True)
    r = combine_reports([("Cerebro", a), ("Investigación", b)], "Orión es el vulnerable.", "medium", ["aviso del plan"])
    assert r.summary.startswith("[Conclusión del orquestador] Orión es el vulnerable.\n[Cerebro] Tenés 2 servidores.")
    assert r.confidence == "low" and r.degraded and len(r.sources) == 1 and r.failures[0].helper == "investigacion-scout"
    assert [(p.id, p.pending_id) for p in r.pending_proposals] == [("7", 7), ("FIX-1", None)]
    assert r.brigade == "memoria-cerebro+investigacion" and "aviso del plan" in r.warnings
