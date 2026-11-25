"""El reemplazo mecánico: un solo lugar, sin tocar fin de línea, con diff y commit propio."""

import subprocess

import pytest

from raphael_selfrepair import fixer


def test_plan_no_escribe_y_da_el_diff(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("x = 1\ny = 2\n")
    pl = fixer.plan(tmp_path, "a.py", "y = 2", "y = 3")
    assert f.read_text() == "x = 1\ny = 2\n"
    assert "-y = 2" in pl.diff and "+y = 3" in pl.diff and pl.rel == "a.py"


def test_no_aparece_y_ambiguo(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\nx = 1\n")
    with pytest.raises(fixer.SnippetNotFoundError):
        fixer.plan(tmp_path, "a.py", "z = 9", "z = 8")
    with pytest.raises(fixer.SnippetAmbiguousError):
        fixer.plan(tmp_path, "a.py", "x = 1", "x = 2")


@pytest.mark.parametrize("old,new", [("", "a"), ("a", "a")])
def test_snippets_invalidos(tmp_path, old, new):
    (tmp_path / "a.py").write_text("a\n")
    with pytest.raises(fixer.FixError):
        fixer.plan(tmp_path, "a.py", old, new)


def test_binario_y_no_utf8(tmp_path):
    (tmp_path / "b.bin").write_bytes(b"a\x00b")
    (tmp_path / "l.txt").write_bytes("áé".encode("latin-1"))
    for f in ("b.bin", "l.txt"):
        with pytest.raises(fixer.FixError):
            fixer.plan(tmp_path, f, "a", "b")


def test_archivo_que_no_existe(tmp_path):
    with pytest.raises(fixer.FixError):
        fixer.plan(tmp_path, "nada.py", "a", "b")


def test_crlf_se_conserva_aunque_el_snippet_venga_con_lf(tmp_path):
    f = tmp_path / "w.py"
    f.write_bytes(b"a = 1\r\nb = 2\r\n")
    pl = fixer.plan(tmp_path, "w.py", "a = 1\nb = 2\n", "a = 1\nb = 3\n")
    fixer.write_text(pl.target, pl.updated)
    assert f.read_bytes() == b"a = 1\r\nb = 3\r\n"


def test_write_text_no_deja_temporales(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("a")
    fixer.write_text(f, "b")
    assert f.read_text() == "b" and [p.name for p in tmp_path.iterdir()] == ["a.py"]


def test_commit_solo_del_archivo(tmp_path):
    from kit import make_project
    root = make_project(tmp_path, git=True)
    (root / "app" / "auth.py").write_text("OTRO = 1\n")           # cambio en curso ajeno: no debe entrar al commit
    (root / "app" / "calc.py").write_text("def total(items):\n    return sum(items)\n")
    r = fixer.commit_file(root, "app/calc.py", "fix: prueba")
    assert r["committed"] and r["commit"]
    show = ["git", "-C", str(root), "show", "--name-only", "--format=", "HEAD"]
    files = subprocess.run(show, capture_output=True, text=True).stdout
    assert files.split() == ["app/calc.py"]
    assert "auth.py" in subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True).stdout


def test_sin_git_no_commitea(tmp_path):
    (tmp_path / "a.py").write_text("a")
    r = fixer.commit_file(tmp_path, "a.py", "m")
    assert not r["committed"] and "git" in r["note"]


def test_verify(tmp_path):
    from kit import PY_FAIL, PY_OK
    assert fixer.verify([], tmp_path, 5) == (True, "")
    assert fixer.verify(PY_OK, tmp_path, 5)[0]
    ok, tail = fixer.verify(PY_FAIL, tmp_path, 5)
    assert not ok and "rompió" in tail
    assert not fixer.verify(["comando-que-no-existe-xyz"], tmp_path, 5)[0]
