import pytest

from raphael_core.store import Store


def test_espacios_aislados_y_contadores(tmp_path):
    """Portado de test_almacen_por_espacios_y_contadores (Empresas)."""
    s = Store(str(tmp_path / "x.sqlite"))
    uno, dos = s.space("uno"), s.space("dos")
    uno.put("c", 1, {"v": 1})
    assert dos.get("c", 1) is None
    assert [uno.next("n"), uno.next("n"), dos.next("n")] == [1, 2, 1]
    assert uno.list("c", v=1) == [{"v": 1}]


def test_actualizar_borrar_y_fecha():
    s = Store()
    e = s.space("uno")
    e.put("c", "a", {"v": 1})
    e.put("c", "a", {"v": 2})
    assert e.list("c") == [{"v": 2}] and e.updated("c", "a") is not None
    assert e.delete("c", "a") and not e.delete("c", "a")


def test_exportar_y_purgar_una_brigada_con_sus_cocineros():
    s = Store()
    s.space("empresas").put("cfg", 1, {"a": 1})
    s.space("empresas/agenda").put("turnos", 1, {"t": 1})
    s.space("empresas/agenda").next("turnos")
    s.space("empresas-viejo").put("cfg", 1, {"ajena": True})   # mismo prefijo, otra brigada
    s.space("_harness").put("cfg", 1, {"h": 1})
    s.space("xharness/sub").put("cfg", 1, {"x": 1})              # "_" no es comodín
    e = s.space("empresas")
    assert e.export() == {"empresas": {"cfg": {"1": {"a": 1}}}, "empresas/agenda": {"turnos": {"1": {"t": 1}}}}
    assert e.export(["turnos"]) == {"empresas/agenda": {"turnos": {"1": {"t": 1}}}}
    assert e.purge() == 2
    assert e.export() == {} and s.space("empresas/agenda").next("turnos") == 1
    assert s.space("empresas-viejo").get("cfg", 1) == {"ajena": True}
    assert s.space("_harness").purge() == 1 and s.space("xharness/sub").get("cfg", 1) == {"x": 1}


def test_purgar_solo_algunas_colecciones():
    s = Store()
    e = s.space("b")
    e.put("cache", 1, {})
    e.put("datos", 1, {})
    assert e.purge(["cache"]) == 1 and e.collections() == ["datos"]


@pytest.mark.parametrize("name", ["Uno", "uno/dos/tres", "", "a b", "../x", "uno/_x"])
def test_nombres_de_espacio_invalidos(name):
    with pytest.raises(ValueError):
        Store().space(name)


def test_nombre_de_coleccion_invalido():
    with pytest.raises(ValueError):
        Store().space("uno").put("Mala Coleccion", 1, {})


def test_una_base_de_empresas_v1_no_se_abre_ni_se_toca(tmp_path):
    import sqlite3

    from raphael_core.store import LegacyDatabaseError

    ruta = tmp_path / "v1.sqlite"
    db = sqlite3.connect(ruta)
    db.execute("CREATE TABLE docs (espacio TEXT, coleccion TEXT, clave TEXT, json TEXT, actualizado TEXT)")
    db.execute("INSERT INTO docs VALUES ('encargos', 'encargos', '1', '{}', 'x')")
    db.commit()
    db.close()
    antes = ruta.read_bytes()
    with pytest.raises(LegacyDatabaseError):
        Store(str(ruta))
    assert ruta.read_bytes() == antes
