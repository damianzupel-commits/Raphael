"""Suite de contrato y matriz de montaje (H5). La puerta de la fase 1: la brigada de ejemplo pasa la suite en las dos
ediciones y la matriz está en verde. Además: la suite tiene que AGARRAR brigadas rotas a propósito."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_loader import EJEMPLOS, brigade

from raphael_core import loader as L
from raphael_core.testing.contract import combinations, matrix_text, packages_of, run_contract_suite, run_matrix


# --- puerta de la fase 1 -----------------------------------------------------------------------------------------------
@pytest.mark.parametrize("edition", ["personal", "cloud"])
def test_la_brigada_de_ejemplo_pasa_la_suite_de_contrato(edition):
    found, _ = L.discover([EJEMPLOS], installed=False)
    siblings = packages_of(found["eco"])
    r = run_contract_suite(EJEMPLOS / "saludo", edition=edition, config={"saludo": "¡Hola"}, siblings=siblings)
    assert r.ok, r.text()
    names = [c.name for c in r.checks]
    for must in ("se monta", "nada con aprobación se ejecuta sin OK", "el jefe reporta con el contrato",
                 "en la nube no carga nada peligroso", "se desmonta limpio", "se puede volver a montar",
                 "sin imports de brigadas hermanas"):
        assert must in names
    assert "ejemplo_eco" in next(c.detail for c in r.checks if c.name == "sin imports de brigadas hermanas")


def test_la_brigada_minima_tambien_pasa():
    assert run_contract_suite(EJEMPLOS / "eco").ok


def test_la_matriz_de_las_brigadas_de_ejemplo_esta_en_verde():
    rows = run_matrix([EJEMPLOS])
    assert [r.label for r in rows] == ["todas", "sin eco", "sin saludo", "ninguna"]
    assert all(r.ok for r in rows), matrix_text(rows)


def test_combinaciones_sin_repetir():
    assert combinations(["a"]) == [("todas", ("a",)), ("sin a", ()), ]
    assert len(combinations(["a", "b", "c"])) == 1 + 3 + 3 + 1
    assert combinations([]) == [("todas", ())]


# --- la suite agarra lo que está mal -----------------------------------------------------------------------------------
def _failed(r) -> dict[str, str]:
    return {c.name: c.detail for c in r.failed()}


def test_agarra_un_manifiesto_invalido_y_un_contrato_incompatible(tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "manifest.yaml").write_text("id: X Mal\n", encoding="utf-8")
    assert "manifiesto válido" in _failed(run_contract_suite(tmp_path / "x"))
    brigade(tmp_path, "vieja", manifest={"contract": "^1.0"})
    r = run_contract_suite(tmp_path / "vieja")
    assert "contrato compatible" in _failed(r) and len(r.checks) == 2


def test_agarra_un_cocinero_que_explota_al_contestar(tmp_path):
    brigade(tmp_path, "rompe", code="""
        from raphael_core import Cook
        class One(Cook):
            def interest(self, msg, ctx): return 0.5
            def handle(self, msg, ctx): raise KeyError("se me cayó")
    """)
    detail = _failed(run_contract_suite(tmp_path / "rompe"))["contesta mensajes de prueba sin romper"]
    assert "se me cayó" in detail


def test_agarra_una_accion_no_declarada(tmp_path):
    brigade(tmp_path, "pide", code="""
        from raphael_core import Action, Cook, Reply
        class One(Cook):
            def interest(self, msg, ctx): return 0.5
            def handle(self, msg, ctx): return Reply("ok", [Action("borrar_todo", summary="borrar")])
    """)
    r = run_contract_suite(tmp_path / "pide")
    assert _failed(r) == {"solo pide acciones declaradas": "borrar_todo"}   # y no se ejecutó: quedó pendiente


def test_agarra_imports_entre_brigadas_hermanas(tmp_path):
    brigade(tmp_path, "otra", pkg="brig_hermana_otra")
    brigade(tmp_path, "mira", code="""
        import brig_hermana_otra
        from raphael_core import Cook
        class One(Cook): pass
    """)
    found, _ = L.discover([tmp_path], installed=False)
    r = run_contract_suite(found["mira"], siblings=packages_of(found["otra"]))
    assert "brig_hermana_otra" in _failed(r)["sin imports de brigadas hermanas"]


def test_agarra_un_cocinero_que_no_arranca_y_la_matriz_lo_marca(tmp_path):
    brigade(tmp_path, "sana")
    brigade(tmp_path, "no-arranca", code="""
        from raphael_core import Cook
        class One(Cook):
            def start(self, ctx): raise RuntimeError("sin base de datos")
    """)
    rows = {r.label: r for r in run_matrix([tmp_path])}
    assert list(rows) == ["todas", "sin no-arranca", "sin sana", "ninguna"]
    assert rows["sin no-arranca"].ok and rows["ninguna"].ok
    assert not rows["todas"].ok and "sin base de datos" in rows["todas"].detail and not rows["sin sana"].ok


def test_agarra_una_config_invalida_y_una_edicion_que_no_corre(tmp_path):
    assert "se arma (entries y config)" in _failed(run_contract_suite(EJEMPLOS / "saludo", config={"otro": 1}))
    brigade(tmp_path, "solo-pc", manifest={"editions": ["personal"]})
    assert "corre en la edición" in _failed(run_contract_suite(tmp_path / "solo-pc", edition="cloud"))


def test_el_texto_del_resultado_sirve_para_leerlo(tmp_path):
    txt = run_contract_suite(Path(EJEMPLOS / "eco")).text()
    assert txt.startswith("Suite de contrato · eco · edición personal: OK") and "✓ se monta" in txt
