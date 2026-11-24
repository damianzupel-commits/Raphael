"""Chequeo por AST: ningún paquete de brigada importa a otra brigada.

Se lee el código sin ejecutarlo. Cuenta como import cruzado cualquier `import x` / `from x import …`
(también dentro de funciones o con `importlib.import_module("x")` y `__import__("x")` con texto fijo)
cuyo paquete raíz sea el de otra brigada.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CrossImport:
    file: str
    line: int
    imported: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line} importa {self.imported}"


def _imported_names(tree: ast.AST) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(node.lineno, a.name) for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.append((node.lineno, node.module))
        elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant) \
                and isinstance(node.args[0].value, str):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""
            if name in ("import_module", "__import__"):
                out.append((node.lineno, node.args[0].value))
    return out


def find_cross_imports(package_dir: str | Path, siblings: set[str] | list[str]) -> list[CrossImport]:
    """Imports desde `package_dir` hacia los paquetes raíz de `siblings` (no incluir el propio)."""
    root = Path(package_dir)
    forbidden = set(siblings)
    found: list[CrossImport] = []
    for py in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError as exc:
            found.append(CrossImport(str(py), exc.lineno or 0, f"<no se pudo leer: {exc.msg}>"))
            continue
        for line, name in _imported_names(tree):
            if name.split(".")[0] in forbidden:
                found.append(CrossImport(str(py.relative_to(root.parent)), line, name))
    return found
