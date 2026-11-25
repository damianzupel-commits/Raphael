"""Cambio puntual de código: reemplazo mecánico, diff, commit propio, vuelta atrás y verificación.

Diseño conservador (portado de `codeedit/fixer.py` de JarvisRemote):
- Quien redacta `old_snippet`/`new_snippet` es una persona o un modelo; este módulo NO inventa nada: hace el reemplazo
  mecánico, el diff y (si corresponde) el commit.
- `plan` nunca escribe: calcula el diff. `apply` escribe. Ninguna de las dos decide si se puede: eso es de la
  aprobación y de la línea roja, que corren antes.
- El snippet tiene que aparecer EXACTAMENTE una vez.
- Si la raíz es un repo git, cada cambio queda en su propio commit con `git add -- <archivo>` + `git commit -- <archivo>`
  (nunca `-A`), así no arrastra nada más y se revierte con `git revert`.
"""

from __future__ import annotations

import difflib
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

MAX_FILE_BYTES = 2_000_000
MAX_SNIPPET_CHARS = 20_000


class FixError(ValueError):
    """El arreglo no se puede planear o aplicar (el mensaje va a la persona)."""


class SnippetNotFoundError(FixError):
    pass


class SnippetAmbiguousError(FixError):
    pass


@dataclass(frozen=True)
class Plan:
    rel: str            # ruta relativa a la raíz, con "/"
    target: Path
    original: str
    updated: str
    diff: str


def resolve_in_root(root: Path, file: str) -> Path:
    """La ruta ya resuelta (con symlinks) y garantizada adentro de la raíz."""
    if not file or "\x00" in file:
        raise FixError("falta el archivo")
    root = root.resolve()
    candidate = Path(file)
    target = (candidate if candidate.is_absolute() else root / candidate).resolve()
    if target != root and root not in target.parents:
        raise PermissionError(f"'{file}' está fuera de la raíz del proyecto ({root})")
    return target


def _eol(text: str, like: str) -> str:
    """Si el archivo usa CRLF y el snippet LF, lo pasa a CRLF (el modelo casi siempre escribe LF)."""
    if "\r\n" in like and "\r\n" not in text:
        return text.replace("\n", "\r\n")
    return text


def _read(target: Path) -> str:
    if not target.is_file():
        raise FixError(f"'{target.name}' no existe o no es un archivo")
    if target.stat().st_size > MAX_FILE_BYTES:
        raise FixError(f"'{target.name}' pesa más de {MAX_FILE_BYTES // 1_000_000} MB: no lo toco")
    raw = target.read_bytes()
    if b"\x00" in raw:
        raise FixError(f"'{target.name}' es binario: la autorreparación solo edita texto")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise FixError(f"'{target.name}' no está en UTF-8: no lo toco") from None


def plan(root: Path, file: str, old: str, new: str) -> Plan:
    if not old:
        raise FixError("falta el texto original (old_snippet)")
    if old == new:
        raise FixError("el texto nuevo es igual al original: no hay nada que cambiar")
    if len(old) > MAX_SNIPPET_CHARS or len(new) > MAX_SNIPPET_CHARS:
        raise FixError(f"un arreglo puntual no pasa de {MAX_SNIPPET_CHARS} caracteres por lado")
    root = root.resolve()
    target = resolve_in_root(root, file)
    original = _read(target)
    old_n, new_n = _eol(old, original), _eol(new, original)
    count = original.count(old_n)
    if count == 0:
        raise SnippetNotFoundError("el texto original no aparece en el archivo: puede que ya haya cambiado. "
                                   "Volvé a leerlo antes de reintentar.")
    if count > 1:
        raise SnippetAmbiguousError(f"el texto original aparece {count} veces: sumale contexto para que "
                                    "identifique un único lugar.")
    updated = original.replace(old_n, new_n, 1)
    rel = target.relative_to(root).as_posix()
    diff = "".join(difflib.unified_diff(original.splitlines(keepends=True), updated.splitlines(keepends=True),
                                        fromfile=f"a/{rel}", tofile=f"b/{rel}"))
    return Plan(rel, target, original, updated, diff)


def write_text(target: Path, text: str) -> None:
    """Escribe sin tocar los fin de línea (bytes) y de forma atómica."""
    tmp = target.with_name(target.name + ".raphael-tmp")
    tmp.write_bytes(text.encode("utf-8"))
    os.replace(tmp, target)


# --- git --------------------------------------------------------------------------------------------------------------
def _git(root: Path, *args: str, timeout: int = 30) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=timeout,
                              stdin=subprocess.DEVNULL)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def is_git_repo(root: Path) -> bool:
    r = _git(root, "rev-parse", "--is-inside-work-tree", timeout=15)
    return bool(r and r.returncode == 0 and r.stdout.strip() == "true")


def commit_file(root: Path, rel: str, message: str) -> dict:
    """Commitea solo `rel`. Devuelve {committed, commit, note}."""
    if not is_git_repo(root):
        return {"committed": False, "commit": None, "note": "la raíz no es un repo git: sin commit, no se revierte con git"}
    add = _git(root, "add", "--", rel)
    commit = _git(root, "commit", "-m", message, "--", rel) if add and add.returncode == 0 else None
    if not commit or commit.returncode != 0:
        return {"committed": False, "commit": None, "note": "es un repo git pero el commit no se pudo crear (mirá `git status`)"}
    rev = _git(root, "rev-parse", "--short", "HEAD", timeout=15)
    h = rev.stdout.strip() if rev and rev.returncode == 0 else None
    return {"committed": True, "commit": h, "note": f"commit {h}"}


# --- verificación -----------------------------------------------------------------------------------------------------
def verify(command: list[str], root: Path, timeout: int) -> tuple[bool, str]:
    """Corre el comando de verificación (sin shell). Devuelve (ok, cola de la salida)."""
    if not command:
        return True, ""
    try:
        r = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL,
                           encoding="utf-8", errors="replace",
                           env={**os.environ, "PYTHONUTF8": "1"})   # en Windows un hijo escribe en cp1252
    except subprocess.TimeoutExpired:
        return False, f"se pasó de {timeout} s"
    except (FileNotFoundError, OSError) as exc:
        return False, f"no se pudo correr: {exc}"
    tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-15:])
    return r.returncode == 0, tail
