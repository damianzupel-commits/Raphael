"""Tests del diseñador de brigadas (brigades/designer.py): descripción -> borrador con un LLM FALSO (no se levanta ningún modelo).
Lo que importa: la salida del modelo es dato no confiable, solo puede producir un borrador, y nunca llega a la activación."""

from __future__ import annotations

import asyncio
import copy
import json

import pytest

from brigades import designer, draft_store, registry
from brigades.ejemplos import EJEMPLO_DELEGA, EJEMPLO_UN_AYUDANTE


@pytest.fixture(autouse=True)
def almacen(monkeypatch, tmp_path):
    monkeypatch.setenv("BRIGADAS_CREADAS_DIR", str(tmp_path / "creadas"))
    draft_store._spec_cache.clear()
    registry._created_chiefs.clear()


class LLM:
    """LLM falso: devuelve respuestas en orden y recuerda los mensajes que recibió."""

    def __init__(self, *respuestas):
        self.respuestas, self.llamadas = list(respuestas), []

    async def __call__(self, messages):
        self.llamadas.append(messages)
        return self.respuestas.pop(0) if len(self.respuestas) > 1 else self.respuestas[0]


def run(descripcion, llm):
    return asyncio.run(designer.design_from_description(descripcion, llm))


DESC = "Quiero una brigada que consulte mi vault y, si pido investigar, salga a la web y deje una nota."


def test_una_descripcion_produce_un_borrador_nunca_una_activa():
    llm = LLM(json.dumps(EJEMPLO_DELEGA))
    rec = run(DESC, llm)
    assert rec["estado"] == "borrador" and rec["origen"] == "descripcion" and rec["descripcion_original"] == DESC
    assert rec["draft"]["id"] == "radar-tecnico" and "radar-tecnico" not in registry.available()


def test_tolera_bloques_de_codigo_y_texto_alrededor():
    txt = "Claro, acá va:\n```json\n" + json.dumps(EJEMPLO_UN_AYUDANTE, ensure_ascii=False) + "\n```\nCualquier cosa avisame."
    assert run(DESC, LLM(txt))["draft"]["id"] == "consulta-vault"


def test_si_el_modelo_se_equivoca_se_le_devuelven_los_errores_y_corrige():
    malo = copy.deepcopy(EJEMPLO_UN_AYUDANTE)
    malo["ayudantes"][0]["tools"] = ["obsidian_search_notes", "pc_run_command"]
    llm = LLM(json.dumps(malo), json.dumps(EJEMPLO_UN_AYUDANTE))
    rec = run(DESC, llm)
    assert rec["draft"]["ayudantes"][0]["tools"] == ["obsidian_buscar_asociativo", "obsidian_search_notes"]
    assert rec["draft"]["tools"] == []  # el jefe no tiene tools
    segunda = llm.llamadas[1]
    assert segunda[-1]["role"] == "user" and "no se puede conceder" in segunda[-1]["content"]  # recibió el error real
    assert "pc_run_command" in segunda[-2]["content"]  # y su propia respuesta anterior, para corregirla


def test_basura_y_json_invalido_se_reintentan_y_al_final_no_se_guarda_nada(almacen=None):
    llm = LLM("no tengo idea", "{ roto", json.dumps({"id": "x"}))
    with pytest.raises(draft_store.DraftInvalid):
        run(DESC, llm)
    assert len(llm.llamadas) == designer.MAX_INTENTOS
    assert draft_store.list_records() == []


def test_un_modelo_que_insiste_en_una_tool_denegada_no_logra_nada():
    malo = copy.deepcopy(EJEMPLO_UN_AYUDANTE)
    malo["ayudantes"][0]["tools"] = ["pc_run_command"]
    with pytest.raises(draft_store.DraftInvalid) as e:
        run(DESC, LLM(json.dumps(malo)))
    assert any("no se puede conceder" in x for x in e.value.errors)
    assert draft_store.list_records() == []


def test_al_modelo_no_se_le_ofrecen_las_tools_denegadas():
    msgs = designer.build_messages(DESC)
    system = msgs[0]["content"]
    for denegada in ("pc_run_command", "selfrepair_propose_fix", "fs_delete_path", "desktop_click", "web_login"):
        assert denegada not in system
    assert "obsidian_search_notes" in system and "TOOLS SENSIBLES" in system and "nmap_scan" in system


def test_el_modelo_no_tiene_camino_a_la_activacion():
    import inspect

    src = inspect.getsource(designer)
    assert "activate" not in src.replace("`activate`", "").replace("a la activación", "")  # nunca llama a activate()
    rec = run(DESC, LLM(json.dumps(EJEMPLO_DELEGA)))
    assert draft_store.get_record(rec["draft"]["id"])["estado"] == "borrador"


def test_descripcion_muy_corta_y_tope_de_longitud():
    with pytest.raises(draft_store.DraftError):
        run("hola", LLM("{}"))
    msgs = designer.build_messages("x" * 10000)
    assert len(msgs[1]["content"]) < designer.MAX_DESCRIPCION + 100


def test_el_mismo_id_que_una_activa_no_se_pisa():
    rec = draft_store.create_draft(copy.deepcopy(EJEMPLO_DELEGA))
    draft_store.activate("radar-tecnico", rec["hash"])
    with pytest.raises(draft_store.DraftError, match="ACTIVA"):
        run(DESC, LLM(json.dumps(EJEMPLO_DELEGA)))
