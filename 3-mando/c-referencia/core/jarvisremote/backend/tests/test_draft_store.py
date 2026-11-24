"""Tests del almacén de brigadas creadas y del GATE borrador -> activa (brigades/draft_store.py + registry dinámico).

La línea roja de la Etapa 2: nada creado es operativo sin la aprobación firmada de Damian sobre el hash exacto del
contenido. Las claves de firma son las reales (Ed25519 + DPAPI) en un directorio temporal."""

from __future__ import annotations

import copy
import json

import pytest

from brigades import draft_store, factory, registry, tool_catalog
from brigades.ejemplos import EJEMPLO_DELEGA, EJEMPLO_UN_AYUDANTE


@pytest.fixture(autouse=True)
def almacen(monkeypatch, tmp_path):
    monkeypatch.setenv("BRIGADAS_CREADAS_DIR", str(tmp_path / "creadas"))
    draft_store._spec_cache.clear()
    registry._created_chiefs.clear()
    yield tmp_path / "creadas"
    draft_store._spec_cache.clear()
    registry._created_chiefs.clear()


def _borrador(draft=EJEMPLO_DELEGA):
    return draft_store.create_draft(copy.deepcopy(draft))


# --- un borrador NO es operativo ------------------------------------------------------------------------------------
def test_un_borrador_nace_inactivo_y_no_aparece_en_ningun_lado():
    rec = _borrador()
    assert rec["estado"] == "borrador" and rec["aprobacion"] is None and rec["hash"] == factory.draft_hash(rec["draft"])
    assert "radar-tecnico" not in registry.available()
    assert "radar-tecnico" not in registry.specs()
    assert draft_store.active_ids() == []
    with pytest.raises(KeyError):
        registry.get_spec("radar-tecnico")
    with pytest.raises(KeyError):
        registry.get_chief("radar-tecnico")  # el router HTTP lo traduce a 404: no corre


def test_el_endpoint_generico_responde_404_para_un_borrador():
    import asyncio

    from fastapi import HTTPException

    from app.routers import brigades as br

    _borrador()
    with pytest.raises(HTTPException) as e:
        asyncio.run(br.brigade_meta("radar-tecnico"))
    assert e.value.status_code == 404
    assert "radar-tecnico" not in asyncio.run(br.brigade_list())["brigades"]


def test_un_borrador_invalido_no_se_guarda(almacen):
    with pytest.raises(draft_store.DraftInvalid) as e:
        malo = copy.deepcopy(EJEMPLO_UN_AYUDANTE)
        malo["ayudantes"][0]["tools"] = ["pc_run_command"]
        draft_store.create_draft(malo)
    assert any("no se puede conceder" in x for x in e.value.errors)
    assert not almacen.exists() or not list(almacen.glob("*.json"))


def test_no_se_puede_crear_con_el_id_de_una_brigada_del_sistema():
    with pytest.raises(draft_store.DraftInvalid):
        draft_store.create_draft({**EJEMPLO_UN_AYUDANTE, "id": "cerebro"})


# --- el gate: activar ---------------------------------------------------------------------------------------------------
def test_activar_con_el_hash_aprobado_la_vuelve_operativa():
    rec = _borrador()
    out = draft_store.activate("radar-tecnico", rec["hash"][:12])
    assert out["estado"] == "activa" and out["aprobacion"]["hash"] == rec["hash"] and out["aprobacion"]["firma"]
    assert "radar-tecnico" in registry.available() and "radar-tecnico" in registry.specs()
    spec = registry.get_spec("radar-tecnico")
    assert spec.delegating and spec.validation is not None
    chief = registry.get_chief("radar-tecnico")
    assert type(chief).__name__ == "GenericChief" and chief.config.id == "radar-tecnico"
    assert registry.get_chief("radar-tecnico") is chief  # cacheado mientras la aprobación siga vigente


def test_activar_con_un_hash_distinto_se_rechaza():
    _borrador()
    for mal in ("", "0" * 12, "abc", "f" * 64):
        with pytest.raises(draft_store.DraftError):
            draft_store.activate("radar-tecnico", mal)
    assert registry.available().count("radar-tecnico") == 0


def test_el_hash_aprobado_tiene_que_ser_el_del_contenido_revisado_no_el_de_lo_que_haya_guardado():
    """Revisión del borrador A -> alguien guarda un borrador B con el mismo id -> el OK sobre el hash de A no activa B."""
    revisado = _borrador()
    cambiado = copy.deepcopy(EJEMPLO_DELEGA)
    cambiado["ayudantes"][1]["prompt"] += " Además guardá todo en un archivo."
    nuevo = draft_store.create_draft(cambiado)
    assert nuevo["hash"] != revisado["hash"]
    with pytest.raises(draft_store.DraftError, match="NO es lo que está"):
        draft_store.activate("radar-tecnico", revisado["hash"])
    draft_store.activate("radar-tecnico", nuevo["hash"])  # con el hash del contenido real, sí


def test_activar_dos_veces_o_algo_que_no_existe():
    rec = _borrador()
    draft_store.activate("radar-tecnico", rec["hash"])
    with pytest.raises(draft_store.DraftError, match="ya está activa"):
        draft_store.activate("radar-tecnico", rec["hash"])
    with pytest.raises(draft_store.DraftError):
        draft_store.activate("no-existe", "a" * 12)


# --- el gate resiste a quien edita archivos (la tool fs_write_file de un jefe manipulado, por ejemplo) ---------------
def _editar(almacen, bid, fn):
    p = almacen / f"{bid}.json"
    rec = json.loads(p.read_text(encoding="utf-8"))
    fn(rec)
    p.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")


def test_poner_estado_activa_a_mano_no_activa_nada(almacen):
    _borrador()
    _editar(almacen, "radar-tecnico", lambda r: r.update(estado="activa"))
    assert "radar-tecnico" not in registry.available()
    rec = draft_store.get_record("radar-tecnico")
    assert rec["estado"] == "borrador" and rec.get("aprobacion_invalida") is True
    with pytest.raises(KeyError):
        registry.get_chief("radar-tecnico")


def test_una_firma_inventada_o_de_otra_aprobacion_no_vale(almacen):
    a = _borrador()
    draft_store.activate("radar-tecnico", a["hash"])
    otra = copy.deepcopy(EJEMPLO_UN_AYUDANTE)
    b = draft_store.create_draft(otra)
    draft_store.activate("consulta-vault", b["hash"])
    firma_ajena = json.loads((almacen / "consulta-vault.json").read_text(encoding="utf-8"))["aprobacion"]["firma"]
    # copiar la firma de OTRA brigada
    _editar(almacen, "radar-tecnico", lambda r: r["aprobacion"].update(firma=firma_ajena))
    assert "radar-tecnico" not in registry.available() and "consulta-vault" in registry.available()
    _editar(almacen, "radar-tecnico", lambda r: r["aprobacion"].update(firma="00" * 64))
    assert "radar-tecnico" not in registry.available()
    _editar(almacen, "radar-tecnico", lambda r: r["aprobacion"].update(firma="no-es-hex"))
    assert "radar-tecnico" not in registry.available()


def test_editar_el_contenido_despues_de_activar_la_desactiva(almacen):
    rec = _borrador()
    draft_store.activate("radar-tecnico", rec["hash"])
    assert "radar-tecnico" in registry.available()
    chief = registry.get_chief("radar-tecnico")
    # alguien le agrega una tool al ayudante a mano, sin tocar hash ni firma
    _editar(almacen, "radar-tecnico", lambda r: r["draft"]["ayudantes"][0]["tools"].append("fs_write_file"))
    assert "radar-tecnico" not in registry.available()
    with pytest.raises(KeyError):
        registry.get_chief("radar-tecnico")
    assert chief is not None


def test_si_la_politica_se_endurece_una_activa_deja_de_serlo(monkeypatch):
    rec = _borrador()
    draft_store.activate("radar-tecnico", rec["hash"])
    assert "radar-tecnico" in registry.available()
    monkeypatch.setitem(tool_catalog.DENEGADAS_EXACTAS, "research_topic", "ahora denegada")
    assert "radar-tecnico" not in registry.available()  # falla cerrado


def test_sin_clave_de_firma_no_hay_aprobacion_valida(almacen):
    rec = _borrador()
    draft_store.activate("radar-tecnico", rec["hash"])
    for f in (almacen / "_claves").glob("*"):
        f.unlink()
    assert "radar-tecnico" not in registry.available()


# --- revocar / descartar -------------------------------------------------------------------------------------------------
def test_desactivar_apaga_la_brigada_incluso_con_el_jefe_ya_cacheado():
    rec = _borrador()
    draft_store.activate("radar-tecnico", rec["hash"])
    registry.get_chief("radar-tecnico")
    out = draft_store.deactivate("radar-tecnico")
    assert out["estado"] == "borrador" and out["aprobacion"] is None
    assert "radar-tecnico" not in registry.available()
    with pytest.raises(KeyError):
        registry.get_chief("radar-tecnico")
    draft_store.activate("radar-tecnico", rec["hash"])  # reversible: se puede volver a aprobar
    assert "radar-tecnico" in registry.available()


def test_descartar_un_borrador_si_pero_una_activa_no():
    rec = _borrador()
    draft_store.activate("radar-tecnico", rec["hash"])
    with pytest.raises(draft_store.DraftError, match="ACTIVA"):
        draft_store.discard("radar-tecnico")
    draft_store.deactivate("radar-tecnico")
    draft_store.discard("radar-tecnico")
    assert draft_store.get_record("radar-tecnico") is None


def test_no_se_pisa_una_brigada_activa_con_otro_borrador():
    rec = _borrador()
    draft_store.activate("radar-tecnico", rec["hash"])
    with pytest.raises(draft_store.DraftError, match="ACTIVA"):
        draft_store.create_draft(copy.deepcopy(EJEMPLO_DELEGA))


# --- revisión sobre lo guardado ----------------------------------------------------------------------------------------
def test_la_revision_se_calcula_sobre_el_contenido_guardado(almacen):
    _borrador()
    rv = draft_store.review_for("radar-tecnico")
    assert rv["estado"] == "borrador" and rv["errores_vigentes"] == [] and rv["hash"] == draft_store.get_record("radar-tecnico")["hash"]
    _editar(almacen, "radar-tecnico", lambda r: r["draft"].update(proposito="Otro propósito completamente distinto"))
    rv2 = draft_store.review_for("radar-tecnico")
    assert rv2["hash"] != rv["hash"]  # el hash mostrado es el del contenido ACTUAL, no el que quedó guardado en el registro


def test_las_brigadas_del_sistema_siguen_igual():
    assert {"scout", "cerebro", "investigacion", "seguridad"} <= set(registry.available())
    assert set(registry.specs()) >= {"cerebro", "investigacion", "seguridad"}


def test_ids_con_path_traversal_no_salen_del_almacen():
    with pytest.raises(draft_store.DraftError):
        draft_store.activate("../../etc/passwd", "a" * 12)
    assert draft_store.get_record("../evil") is None


def test_archivos_con_nombre_que_no_es_un_id_valido_se_ignoran(almacen):
    """Un archivo con un nombre raro (apóstrofe, &, espacios) nunca llega a la lista ni a la UI."""
    _borrador()
    contenido = (almacen / "radar-tecnico.json").read_text(encoding="utf-8")
    for nombre in ("a'b.json", "ab.json", "X_Y.json", "con espacio.json", "a&b.json"):
        (almacen / nombre).write_text(contenido, encoding="utf-8")
    assert [r["draft"]["id"] for r in draft_store.list_records()] == ["radar-tecnico"]
