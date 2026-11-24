"""Paralelismo con git worktrees (spec §5).

Problema: varios agentes escribiendo sobre el mismo repo se pisan. Solución:
cada agente que MODIFICA archivos corre en su propio `git worktree` (copia de
trabajo aislada, misma historia de git); el orquestador integra y limpia. Los
agentes read-only (escaneo, triage) comparten el checkout, no necesitan worktree.

Dos partes:
- Lógica PURA (testeable sin git): partir un repo grande en pedazos balanceados
  y mergear los hallazgos de las corridas paralelas sin duplicar.
- Wrappers de git (subprocess): add/remove/list de worktrees. Requieren un repo
  git real; son best-effort y devuelven el resultado del comando.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, TypeVar

T = TypeVar("T")


# --- Lógica pura ---------------------------------------------------------------

def partition_files(
    files: list[str],
    n_chunks: int,
    size_of: Callable[[str], int] | None = None,
) -> list[list[str]]:
    """Reparte `files` en `n_chunks` pedazos lo más balanceados posible.

    Si se pasa `size_of`, balancea por TAMAÑO (greedy: cada archivo va al pedazo
    más liviano) -- mejor para repos donde unos pocos archivos son gigantes. Si
    no, balancea por CANTIDAD (round-robin). Nunca devuelve pedazos vacíos de más:
    el número real de pedazos es min(n_chunks, len(files))."""
    if n_chunks < 1:
        raise ValueError("n_chunks debe ser >= 1")
    if not files:
        return []
    k = min(n_chunks, len(files))
    chunks: list[list[str]] = [[] for _ in range(k)]

    if size_of is None:
        for i, f in enumerate(files):
            chunks[i % k].append(f)
        return chunks

    loads = [0] * k
    # de más grande a más chico para que el greedy balancee mejor
    for f in sorted(files, key=size_of, reverse=True):
        j = min(range(k), key=lambda idx: loads[idx])
        chunks[j].append(f)
        loads[j] += size_of(f)
    return chunks


def merge_results(
    result_lists: Iterable[list[T]],
    key: Callable[[T], Any] = lambda x: getattr(x, "id", x),
) -> list[T]:
    """Junta los resultados de las corridas paralelas descartando duplicados
    (por `key`, default el `.id` de un Finding). Preserva el primer visto."""
    seen: set[Any] = set()
    merged: list[T] = []
    for lst in result_lists:
        for item in lst:
            k = key(item)
            if k in seen:
                continue
            seen.add(k)
            merged.append(item)
    return merged


# --- Wrappers de git (requieren un repo real) ----------------------------------

@dataclass
class GitResult:
    ok: bool
    stdout: str
    stderr: str


def _git(repo: str, *args: str) -> GitResult:
    try:
        proc = subprocess.run(
            ["git", "-C", repo, *args],
            capture_output=True, text=True, timeout=120,
        )
        return GitResult(proc.returncode == 0, proc.stdout.strip(), proc.stderr.strip())
    except (OSError, subprocess.SubprocessError) as exc:  # git no instalado, timeout, etc.
        return GitResult(False, "", str(exc))


def add_worktree(repo: str, path: str, branch: str) -> GitResult:
    """Crea un worktree aislado en `path` sobre una rama nueva `branch`."""
    return _git(repo, "worktree", "add", "-b", branch, path)


def remove_worktree(repo: str, path: str, force: bool = False) -> GitResult:
    args = ["worktree", "remove", path]
    if force:
        args.append("--force")
    return _git(repo, *args)


def list_worktrees(repo: str) -> GitResult:
    return _git(repo, "worktree", "list", "--porcelain")
