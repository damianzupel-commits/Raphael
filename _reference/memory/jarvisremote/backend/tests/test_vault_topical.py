"""Tests de la lectura UNIFICADA del vault (2026-10-05): además de jarvis/ y human/,
list_notes debe leer las carpetas TEMÁTICAS recursivamente como autor 'human', con id
= ruta relativa, y saltear las carpetas de sistema (. / _)."""

import frontmatter

from app.obsidian import vault


def _write(path, title, author="human"):
    path.parent.mkdir(parents=True, exist_ok=True)
    post = frontmatter.Post(f"cuerpo de {title}", title=title, author=author)
    path.write_text(frontmatter.dumps(post), encoding="utf-8")


def _setup_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(vault, "_vault_root", lambda: tmp_path)
    _write(tmp_path / "jarvis" / "nota-jarvis.md", "Nota Jarvis", author="jarvis")
    _write(tmp_path / "10-Seguridad" / "attack" / "foo.md", "Ataque Foo")
    _write(tmp_path / "07-Conciencia" / "idea.md", "Una idea")
    _write(tmp_path / "_Plantillas" / "tpl.md", "Plantilla")  # debe IGNORARSE
    (tmp_path / ".obsidian").mkdir(parents=True, exist_ok=True)
    _write(tmp_path / ".obsidian" / "x.md", "oculta")  # debe IGNORARSE


def test_lee_tematicas_y_autor(tmp_path, monkeypatch):
    _setup_vault(tmp_path, monkeypatch)
    notes = vault.list_notes()
    by_id = {n.id: n for n in notes}
    assert "jarvis/nota-jarvis" in by_id
    assert "10-Seguridad/attack/foo" in by_id  # anidada, id = ruta relativa
    assert "07-Conciencia/idea" in by_id
    assert by_id["10-Seguridad/attack/foo"].author == "human"
    assert by_id["jarvis/nota-jarvis"].author == "jarvis"
    # carpetas de sistema/plantillas excluidas
    assert not any(n.id.startswith("_Plantillas") or n.id.startswith(".obsidian") for n in notes)


def test_filtro_por_autor_jarvis_no_trae_tematicas(tmp_path, monkeypatch):
    _setup_vault(tmp_path, monkeypatch)
    jarvis = vault.list_notes(author="jarvis")
    assert all(n.author == "jarvis" for n in jarvis)
    assert not any("Seguridad" in n.id for n in jarvis)


def test_read_note_resuelve_id_anidado(tmp_path, monkeypatch):
    _setup_vault(tmp_path, monkeypatch)
    n = vault.read_note("10-Seguridad/attack/foo")
    assert n.title == "Ataque Foo" and n.author == "human"


def test_note_path_rechaza_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(vault, "_vault_root", lambda: tmp_path)
    import pytest
    with pytest.raises(ValueError):
        vault._note_path("../fuera")
