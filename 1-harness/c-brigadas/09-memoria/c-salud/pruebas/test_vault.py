"""El vault: archivos Markdown reales con frontmatter, dos autores que no se mezclan, nada fuera de la carpeta."""

from __future__ import annotations

import zipfile
from datetime import datetime

import pytest

from raphael_memoria.vault import Vault


@pytest.fixture
def vault(tmp_path):
    return Vault(tmp_path / "v", now=lambda: datetime(2026, 11, 25, 10, 0))


def test_guarda_y_lee_con_frontmatter_real(vault):
    n = vault.save("Rotación de claves", "Cada 45 días.", "jarvis", ["seguridad"], "infra")
    assert n.id == "jarvis/rotacion-de-claves" and n.author == "jarvis" and n.tags == ["seguridad"]
    raw = (vault.root / "jarvis" / "rotacion-de-claves.md").read_text(encoding="utf-8")
    assert raw.startswith("---\n") and "title: Rotación de claves" in raw and raw.endswith("Cada 45 días.")
    assert vault.read(n.id).content == "Cada 45 días." and vault.read(n.id).category == "infra"


def test_un_titulo_repetido_no_pisa_la_nota_anterior(vault):
    a = vault.save("Idea", "primera", "jarvis")
    b = vault.save("Idea", "segunda", "jarvis")
    assert a.id != b.id and vault.read(a.id).content == "primera" and vault.read(b.id).content == "segunda"


def test_editar_conserva_la_fecha_de_creacion(vault):
    n = vault.save("Idea", "uno", "jarvis")
    later = Vault(vault.root, now=lambda: datetime(2026, 12, 1, 9, 0))
    m = later.save("Idea", "dos", "jarvis", note_id=n.id)
    assert m.created == n.created and m.updated != n.updated and m.content == "dos"


def test_los_autores_no_se_mezclan(vault):
    vault.save("De Raphael", "x", "jarvis")
    vault.save("De Damián", "y", "human")
    assert [n.author for n in vault.list_notes(author="jarvis")] == ["jarvis"]
    assert [n.author for n in vault.list_notes(author="human")] == ["human"]
    with pytest.raises(ValueError, match="pertenece al autor"):
        vault.save("Cruce", "z", "jarvis", note_id="human/de-damian")
    with pytest.raises(ValueError, match="author debe ser"):
        vault.save("X", "z", "otro")


def test_las_carpetas_tematicas_se_leen_como_human_y_las_excluidas_no(tmp_path):
    root = tmp_path / "v"
    (root / "10-Seguridad").mkdir(parents=True)
    (root / ".obsidian").mkdir()
    (root / "_plantillas").mkdir()
    (root / "privado").mkdir()
    (root / "10-Seguridad" / "a.md").write_text("---\ntitle: Nota A\n---\ntexto", encoding="utf-8")
    (root / ".obsidian" / "b.md").write_text("no", encoding="utf-8")
    (root / "_plantillas" / "c.md").write_text("no", encoding="utf-8")
    (root / "privado" / "d.md").write_text("no", encoding="utf-8")
    v = Vault(root, excluded_dirs=["privado"])
    notas = v.list_notes()
    assert [n.id for n in notas] == ["10-Seguridad/a"] and notas[0].author == "human" and notas[0].title == "Nota A"


def test_un_archivo_sin_frontmatter_o_ilegible_no_rompe_la_lista(tmp_path):
    root = tmp_path / "v"
    (root / "jarvis").mkdir(parents=True)
    (root / "jarvis" / "pelada.md").write_text("solo texto", encoding="utf-8")
    (root / "jarvis" / "rota.md").write_bytes(b"\xff\xfe\x00\xff")
    (root / "jarvis" / "yaml-malo.md").write_text("---\ntitle: [sin cerrar\n---\ncuerpo", encoding="utf-8")
    v = Vault(root)
    ids = {n.id for n in v.list_notes()}
    assert ids == {"jarvis/pelada", "jarvis/yaml-malo"} and v.read("jarvis/pelada").title == "pelada"


@pytest.mark.parametrize("bad", ["../afuera", "jarvis/../../etc/passwd", "/abs", "", "a/../b"])
def test_ningun_id_sale_de_la_carpeta(vault, bad):
    with pytest.raises(ValueError):
        vault.read(bad)
    assert vault.exists(bad) is False


def test_contenido_que_parece_frontmatter_no_rompe_la_nota(vault):
    n = vault.save("Truco", "---\ntitle: otro\nauthor: human\n---\ncuerpo", "jarvis")
    r = vault.read(n.id)
    assert r.title == "Truco" and r.author == "jarvis" and "otro" in r.content


def test_busca_por_palabra_clave_sin_acentos_ni_mayusculas(vault):
    vault.save("Orión", "El servidor ROTA sus claves", "jarvis")
    vault.save("Otra", "nada que ver con esto", "jarvis")
    [(n, s)] = vault.search_keyword("rota claves Orion")
    assert n.title == "Orión" and s >= 2


def test_grafo_por_wikilinks_ignora_fantasmas_y_duplicados(vault):
    a = vault.save("A", "ver [[B]] y [[B|alias]] y [[No existe]] y [[A]]", "jarvis")
    b = vault.save("B", "ver [[A]]", "jarvis")
    g = vault.graph()
    assert len(g["nodes"]) == 2 and g["edges"] == [{"source": a.id, "target": b.id}] or \
        g["edges"] == [{"source": b.id, "target": a.id}]


def test_indice_por_categoria_conecta_cada_nota_al_hub(vault):
    vault.link_to_category_index("Nota 1", "seguridad")
    vault.link_to_category_index("Nota 2", "seguridad")
    h = vault.link_to_category_index("Nota 2", "seguridad")           # repetir no duplica
    assert h.content.count("[[Nota 2]]") == 1 and "[[Nota 1]]" in h.content and h.tags == ["indice"]


def test_borrar_y_exportar(vault, tmp_path):
    n = vault.save("Chau", "x", "jarvis")
    vault.save("Queda", "y", "human")
    vault.delete(n.id)
    with pytest.raises(FileNotFoundError):
        vault.read(n.id)
    z = vault.export_zip(vault.root / "export.zip")                      # aunque el zip caiga adentro, no se incluye a sí mismo
    with zipfile.ZipFile(z) as f:
        assert f.namelist() == ["human/queda.md"]
