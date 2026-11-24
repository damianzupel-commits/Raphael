from pathlib import Path

from raphael_core.testing import find_cross_imports


def _pkg(root: Path, name: str, code: str) -> Path:
    p = root / name
    p.mkdir()
    (p / "__init__.py").write_text(code, encoding="utf-8")
    return p


def test_detecta_imports_cruzados_en_todas_sus_formas(tmp_path):
    p = _pkg(tmp_path, "raphael_agenda",
             "import raphael_core\n"
             "from raphael_cobros.brigada import X\n"
             "def f():\n    import raphael_cobros\n"
             "import importlib\nimportlib.import_module('raphael_atencion.algo')\n"
             "__import__('raphael_cobros')\n")
    found = find_cross_imports(p, {"raphael_cobros", "raphael_atencion"})
    assert [(c.line, c.imported) for c in found] == [(2, "raphael_cobros.brigada"), (4, "raphael_cobros"),
                                                       (6, "raphael_atencion.algo"), (7, "raphael_cobros")]


def test_paquete_limpio(tmp_path):
    p = _pkg(tmp_path, "raphael_agenda", "from raphael_core import Cook\nfrom . import algo\n")
    assert find_cross_imports(p, {"raphael_cobros"}) == []
