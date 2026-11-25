"""Conectar un vault real (el de Damián, ~900 notas de Obsidian): carpetas marcadas como sensibles (sin bloquearlas), nada
escrito fuera de `jarvis/`, lectura rápida con cache y texto a embeber acotado."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from kit import System

from raphael_memoria import vault as vault_mod
from raphael_memoria.brain import EMBED_MAX_CHARS, embedding_text
from raphael_memoria.config import memoria_config
from raphael_memoria.vault import Note, Vault


def _nota(root: Path, rel: str, titulo: str, cuerpo: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\ntitle: {titulo}\n---\n{cuerpo}", encoding="utf-8")
    return p


def _vault_tipo_fenix(root: Path) -> None:
    """Una carpeta con la forma de Vault-Fenix: temáticas con tildes, sistema de Obsidian, plantillas y subcarpetas."""
    _nota(root, "02-Fénix/proyecto.md", "Proyecto Fénix", "Notas del proyecto.")
    _nota(root, "07-Conciencia/espacio/gwt.md", "Espacio de trabajo global", "Baars y Dehaene.")
    _nota(root, "10-Raphael-Seguridad/attack/nmap.md", "Nmap", "Escaneo de puertos con nmap.")
    _nota(root, "_Plantillas/plantilla.md", "Plantilla", "no es una nota")
    _nota(root, ".obsidian/workspace.md", "Sistema", "no es una nota")
    _nota(root, ".smart-env/multi/algo.md", "Plugin", "no es una nota")
    _nota(root, "jarvis/ingerida.md", "Ingerida", "Algo que ingirió Raphael.")
    (root / "human").mkdir(parents=True, exist_ok=True)


def _huellas(root: Path, *, salvo: tuple[str, ...]) -> dict[str, str]:
    out = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_file() and not rel.startswith(salvo):
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


# --- config por entorno -------------------------------------------------------------------------------------------------
def test_las_carpetas_sensibles_y_excluidas_pueden_venir_del_entorno():
    cfg = memoria_config({}, {"MEMORIA_SENSITIVE_DIRS": "02-Fénix, 07-Conciencia ,01-Bitácora", "MEMORIA_EXCLUDED_DIRS": "05-Archivo"})
    assert cfg.vault.sensitive_dirs == ["02-Fénix", "07-Conciencia", "01-Bitácora"] and cfg.vault.excluded_dirs == ["05-Archivo"]


def test_lo_que_dice_la_config_de_la_instalacion_gana_sobre_el_entorno():
    cfg = memoria_config({"vault": {"sensitive_dirs": ["10-Personal"]}}, {"MEMORIA_SENSITIVE_DIRS": "02-Fénix"})
    assert cfg.vault.sensitive_dirs == ["10-Personal"]


def test_sin_entorno_ni_config_no_hay_carpetas_marcadas():
    assert memoria_config({}, {}).vault.sensitive_dirs == []


# --- un vault con la forma del real -------------------------------------------------------------------------------------
def test_el_vault_tipo_fenix_se_lee_sin_las_carpetas_de_sistema(tmp_path):
    x = System(tmp_path)
    _vault_tipo_fenix(x.vault)
    ids = sorted(n["id"] for n in x.cmd("recuperador", "notas"))
    assert ids == ["02-Fénix/proyecto", "07-Conciencia/espacio/gwt", "10-Raphael-Seguridad/attack/nmap", "jarvis/ingerida"]


def test_marcar_una_carpeta_no_la_bloquea_y_el_estado_lo_cuenta(tmp_path):
    x = System(tmp_path, {"vault": {"sensitive_dirs": ["02-Fénix", "07-Conciencia"]}})
    _vault_tipo_fenix(x.vault)
    x.cmd("consolidador", "reindexar")
    ev = x.cmd("recuperador", "recordar", {"query": "proyecto Fénix notas", "limit": 5})
    fuente = next(f for f in ev["fuentes"] if f["id"] == "02-Fénix/proyecto")
    assert fuente["sensible"] is True and "Notas del proyecto" in fuente["extracto"]        # se lee igual
    est = x.cmd("recuperador", "estado")
    assert est["sensibles"]["carpetas"] == {"02-Fénix": 1, "07-Conciencia": 1}
    assert est["carpetas"]["10-Raphael-Seguridad"] == 1 and est["notas"] == 4


def test_las_tools_marcan_lo_sensible_en_buscar_y_leer(tmp_path):
    x = System(tmp_path, {"vault": {"sensitive_dirs": ["02-Fénix"]}})
    _vault_tipo_fenix(x.vault)
    leer = x.rt.run(x.rt.tools.get("memoria_leer_nota").run({"id": "02-Fénix/proyecto"}))
    otra = x.rt.run(x.rt.tools.get("memoria_leer_nota").run({"id": "jarvis/ingerida"}))
    assert leer["sensible"] is True and "Notas del proyecto" in leer["content"] and otra["sensible"] is False
    buscar = x.rt.run(x.rt.tools.get("memoria_buscar").run({"query": "proyecto Fénix"}))
    assert {r["id"]: r["sensible"] for r in buscar["resultados"]}["02-Fénix/proyecto"] is True


def test_conectar_el_vault_no_escribe_fuera_de_jarvis_ni_del_espejo_de_episodios(tmp_path):
    x = System(tmp_path)
    _vault_tipo_fenix(x.vault)
    antes = _huellas(x.vault, salvo=("jarvis/", "12-Memoria-Raphael/", ".salud"))
    x.cmd("consolidador", "reindexar")
    x.save("Una nota nueva", "Raphael solo escribe en jarvis.")
    x.cmd("recuperador", "recordar", {"query": "nmap puertos"})
    x.cmd("asociativo", "asociar", {"query": "espacio de trabajo", "reforzar": True})
    despues = _huellas(x.vault, salvo=("jarvis/", "12-Memoria-Raphael/", ".salud"))
    assert antes == despues


# --- cache de lectura ---------------------------------------------------------------------------------------------------
def test_la_segunda_lectura_no_vuelve_a_parsear_los_archivos(tmp_path, monkeypatch):
    v = Vault(tmp_path / "v")
    for i in range(5):
        _nota(v.root, f"tema/n{i}.md", f"Nota {i}", f"contenido {i}")
    llamadas = []
    original = Vault._parse

    def contar(self, path):
        llamadas.append(path.name)
        return original(self, path)

    monkeypatch.setattr(Vault, "_parse", contar)
    vault_mod._CACHE.clear()
    assert len(v.list_notes()) == 5 and len(llamadas) == 5
    assert len(Vault(v.root).list_notes()) == 5 and len(llamadas) == 5      # otro objeto, mismo vault: usa la cache


def test_si_otro_programa_edita_una_nota_se_relee(tmp_path):
    v = Vault(tmp_path / "v")
    p = _nota(v.root, "tema/a.md", "A", "versión uno")
    assert v.read("tema/a").content == "versión uno"
    p.write_text("---\ntitle: A\n---\nversión dos, más larga", encoding="utf-8")
    st = p.stat()
    os.utime(p, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000))           # que la fecha cambie aunque el reloj sea grueso
    assert v.read("tema/a").content == "versión dos, más larga"


def test_guardar_dos_veces_seguidas_la_misma_nota_no_devuelve_la_vieja(tmp_path):
    v = Vault(tmp_path / "v")
    n = v.save("Idea", "uno", "jarvis")
    m = v.save("Idea", "dos", "jarvis", note_id=n.id)
    assert m.content == "dos" and v.read(n.id).content == "dos"


def test_borrar_una_nota_la_saca_de_la_lista(tmp_path):
    v = Vault(tmp_path / "v")
    n = v.save("Idea", "uno", "jarvis")
    assert [x.id for x in v.list_notes()] == [n.id]
    v.delete(n.id)
    assert v.list_notes() == []


def test_modificar_la_nota_devuelta_no_envenena_la_cache(tmp_path):
    v = Vault(tmp_path / "v")
    n = v.save("Idea", "uno", "jarvis", ["a"])
    v.read(n.id).tags.append("b")
    assert v.read(n.id).tags == ["a"]


# --- texto a embeber ----------------------------------------------------------------------------------------------------
def test_el_texto_a_embeber_tiene_tope_y_conserva_el_comienzo():
    larga = Note(id="x/larga", title="Larga", author="human", content="palabra " * 5000)
    t = embedding_text(larga)
    assert len(t) == EMBED_MAX_CHARS and t.startswith("Larga\n")


def test_una_nota_larga_se_indexa_igual(tmp_path):
    x = System(tmp_path)
    _nota(x.vault, "tema/larga.md", "Larga", "palabra " * 5000)
    x.cmd("consolidador", "reindexar")
    assert x.cmd("recuperador", "estado")["con_vector"] == 1


# --- el script de revisión ----------------------------------------------------------------------------------------------
def test_revisar_vault_cuenta_sin_escribir_nada(tmp_path):
    import importlib.util

    spec = importlib.util.spec_from_file_location("revisar_vault", Path(__file__).resolve().parents[1] / "mantenimiento" / "revisar_vault.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _vault_tipo_fenix(tmp_path / "v")
    antes = _huellas(tmp_path / "v", salvo=())
    r = mod.revisar(tmp_path / "v", ["02-Fénix", "07-Inexistente"], [])
    assert r["notas"] == 4 and r["salteados_de_sistema"] == 3 and r["sensibles"] == {"02-Fénix": 1, "07-Inexistente": 0}
    assert r["sensibles_inexistentes"] == ["07-Inexistente"] and _huellas(tmp_path / "v", salvo=()) == antes
