"""Archivos de claves que solo puede leer el usuario de esta PC.

En Linux y macOS alcanza con `chmod 600`. En Windows `chmod` no restringe nada (solo el bit de solo lectura), así que
se usa `icacls`: se cortan los permisos heredados y se deja el acceso solo al usuario actual. Es lo mejor posible sin
privilegios; si `icacls` no está o falla, devuelve False y quien llama avisa en vez de fingir que quedó protegido.
"""

from __future__ import annotations

import getpass
import os
import subprocess
import sys
from pathlib import Path


def icacls_args(path: Path, user: str) -> list[str]:
    """Quitar la herencia y dejar control total solo al usuario actual (y a SYSTEM, que Windows necesita)."""
    return ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:(F)", "/grant:r", "*S-1-5-18:(F)"]


def restringir(path: str | Path, *, windows: bool | None = None, run=subprocess.run, user: str | None = None) -> bool:
    """Deja `path` legible solo por el usuario actual. True si quedó restringido, False si no se pudo."""
    path = Path(path)
    windows = (sys.platform == "win32") if windows is None else windows
    if not windows:
        try:
            os.chmod(path, 0o600)
        except OSError:
            return False
        return True
    try:
        r = run(icacls_args(path, user or os.environ.get("USERNAME") or getpass.getuser()), capture_output=True, text=True,
                timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return r.returncode == 0


def es_privado(path: str | Path, *, windows: bool | None = None, run=subprocess.run) -> bool:
    """¿Solo el usuario actual (y SYSTEM/administradores) puede leerlo? Para los tests y el chequeo de arranque."""
    path = Path(path)
    windows = (sys.platform == "win32") if windows is None else windows
    if not windows:
        return (path.stat().st_mode & 0o077) == 0
    try:
        out = run(["icacls", str(path)], capture_output=True, text=True, timeout=20, check=False).stdout or ""
    except (OSError, subprocess.SubprocessError):
        return False
    abiertos = ("Everyone", "BUILTIN\\Users", "NT AUTHORITY\\Authenticated Users", "Todos", "*S-1-1-0", "*S-1-5-32-545")
    return not any(a.lower() in out.lower() for a in abiertos)
