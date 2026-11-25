"""Salud, config, montar/desmontar y exportar."""

from __future__ import annotations

import zipfile

from kit import BRIGADE_DIR, System
from raphael_core import Loader, Runtime
from raphael_core.installation import installation_from


def salud(x):
    return x.rt.run(x.rt.check_health("memoria"))


def test_sin_modelo_ni_embeddings_la_salud_es_buena_y_lo_dice(tmp_path):
    x = System(tmp_path, {"embeddings": {"provider": "off"}})
    h = salud(x)
    assert h["ok"] and "sin embeddings" in h["detail"] and "sin modelo local" in h["detail"]


def test_un_vault_que_no_se_puede_escribir_es_salud_mala(tmp_path):
    f = tmp_path / "archivo"
    f.write_text("x")
    x = System(tmp_path, {"vault": {"path": str(f / "vault")}})
    assert salud(x)["ok"] is False


def test_una_config_invalida_no_monta_y_dice_el_campo(tmp_path):
    inst = {"id": "t", "edition": "personal", "brigades": {"memoria": {"active": True, "config": {"consolidation": {"threshold": 5}}}}}
    rt = Runtime(installation_from(inst))
    rep = rt.run(Loader(rt, [BRIGADE_DIR], installed=False).apply())
    assert "memoria" not in rt.brigades and "threshold" in str(rep["errors"])


def test_desmontar_exporta_lo_aprendido_y_deja_el_vault_en_su_lugar(tmp_path):
    x = System(tmp_path)
    x.save("Nota", "contenido")
    x.cmd("asociativo", "feedback", {"ids": ["a", "b"], "signals": {"explicit": 1}})
    out = x.rt.run(x.rt.unmount("memoria"))
    assert "aprendizaje" in out["memoria"] and (x.vault / "jarvis" / "nota.md").exists()
    assert x.rt.store.space("memoria").list("embeddings") == []
    x.rt.run(x.loader.apply())
    assert x.cmd("recuperador", "notas")[0]["id"] == "jarvis/nota"


def test_exportar_el_vault_pide_aprobacion_y_crea_el_zip(tmp_path):
    x = System(tmp_path)
    x.save("Nota", "contenido")
    dest = tmp_path / "salida" / "vault.zip"
    assert x.cmd("consolidador", "exportar", {"destino": str(dest)})["estado"] == "pending" and not dest.exists()
    x.approve(x.pending("exportar_vault")[0]["id"])
    with zipfile.ZipFile(dest) as z:
        assert "jarvis/nota.md" in z.namelist()


def test_contenido_demasiado_largo_o_sin_titulo_es_un_error(tmp_path):
    x = System(tmp_path)
    assert x.save("T", "x" * 60_000)["estado"] == "error"
    assert x.cmd("consolidador", "guardar", {"content": "c"})["estado"] == "error"
    assert x.save("T", "c", tags="no-lista")["estado"] == "error"


def test_la_persona_puede_guardar_como_human_pero_por_defecto_es_jarvis(tmp_path):
    x = System(tmp_path)
    assert x.save("Mía", "c", author="human")["resultado"]["nota"].startswith("human/")
    assert x.save("Suya", "c")["resultado"]["nota"].startswith("jarvis/")
