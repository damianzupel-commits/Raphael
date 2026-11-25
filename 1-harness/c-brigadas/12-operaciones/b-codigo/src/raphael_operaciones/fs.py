"""Archivos de la PC dentro de un sandbox. Portado de `tools/filesystem.py`.

Un único punto de control (`Sandbox.resolve`): toda operación de archivos y el directorio de trabajo del shell pasan por
acá. Normaliza `..` y symlinks ANTES de comparar, así que salir con `../../` o con un enlace simbólico falla.

Las raíces dependen del modo de operación (ver `modes.py`):
- AUTÓNOMO: la carpeta segura + `fs_raices`.
- SUPERVISADO: lo anterior + `fs_supervisado`.
Las carpetas de `fs_prohibidas` ganan siempre, aunque caigan dentro de una raíz (material personal que ninguna tool lee).
Borrar está apagado salvo `fs_permitir_borrar`.

No se porta el gancho de `fs_write_file` con `codeedit` (commit reversible en proyectos indexados): es de Autorreparación.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from raphael_core.contract import ActionError

from .config import OpsConfig
from .modes import ModeState

MAX_WRITE_BYTES = 5_000_000


class SandboxError(ActionError, PermissionError):
    """El pedido sale del sandbox o está prohibido."""


class Sandbox:
    def __init__(self, config: OpsConfig, mode: ModeState) -> None:
        self.config = config
        self.mode = mode

    # --- raíces ----------------------------------------------------------------------------------------------------
    def roots(self) -> list[Path]:
        raw: list[str | Path] = [self.config.sandbox_dir, *self.config.fs_roots]
        if self.mode.supervised:
            raw += list(self.config.fs_supervised_roots)
        out: list[Path] = []
        for r in raw:
            try:
                p = Path(r).expanduser().resolve()
            except (OSError, ValueError):
                continue   # una raíz mal escrita no tumba el sandbox: se ignora
            if p not in out:
                out.append(p)
        return out

    def _denied(self) -> list[Path]:
        out: list[Path] = []
        for r in self.config.fs_denied:
            try:
                out.append(Path(r).expanduser().resolve())
            except (OSError, ValueError):
                continue
        return out

    def resolve(self, path: str) -> Path:
        """La ruta absoluta y normalizada, o `SandboxError`. Las relativas parten de la raíz principal (la carpeta segura)."""
        roots = self.roots()
        if not roots:
            raise SandboxError("No hay ninguna carpeta permitida para trabajar con archivos.")
        candidate = Path(str(path)).expanduser()
        try:
            target = candidate.resolve() if candidate.is_absolute() else (roots[0] / candidate).resolve()
        except (OSError, ValueError) as exc:
            raise SandboxError(f"Ruta inválida '{path}': {exc}") from exc
        for denied in self._denied():
            if target == denied or target.is_relative_to(denied):
                raise SandboxError(f"'{path}' está en una carpeta personal bloqueada. Raphael no accede a ese material.")
        for root in roots:
            if target == root or target.is_relative_to(root):
                return target
        allowed = ", ".join(str(r) for r in roots)
        raise SandboxError(f"'{path}' está fuera de las carpetas permitidas ({allowed}).")

    def ensure_home(self) -> Path:
        """Crea la carpeta segura si no existe (solo cuando hace falta escribir ahí)."""
        home = self.roots()[0]
        home.mkdir(parents=True, exist_ok=True)
        return home

    # --- operaciones -----------------------------------------------------------------------------------------------
    def list_dir(self, path: str = ".") -> dict:
        target = self.resolve(path)
        if not target.exists():
            raise ActionError(f"No existe: {target}")
        if not target.is_dir():
            raise ActionError(f"No es una carpeta: {target}")
        entries = [{"name": e.name, "type": "dir" if e.is_dir() else "file",
                    "size_bytes": e.stat().st_size if e.is_file() else None} for e in sorted(target.iterdir())]
        return {"path": str(target), "entries": entries}

    def read_file(self, path: str, max_chars: int = 20000) -> dict:
        target = self.resolve(path)
        if not target.is_file():
            raise ActionError(f"No existe o no es un archivo: {target}")
        content = target.read_text(encoding="utf-8", errors="replace")
        return {"path": str(target), "content": content[:max_chars], "truncated": len(content) > max_chars}

    def write_file(self, path: str, content: str, append: bool = False) -> dict:
        data = str(content)
        if len(data.encode("utf-8")) > MAX_WRITE_BYTES:
            raise ActionError(f"El contenido pasa el tope de {MAX_WRITE_BYTES // 1_000_000} MB por escritura.")
        target = self.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a" if append else "w", encoding="utf-8") as f:
            f.write(data)
        return {"path": str(target), "bytes_written": len(data.encode("utf-8")), "append": append}

    def create_dir(self, path: str) -> dict:
        target = self.resolve(path)
        target.mkdir(parents=True, exist_ok=True)
        return {"path": str(target)}

    def move_path(self, source: str, destination: str) -> dict:
        src, dst = self.resolve(source), self.resolve(destination)
        if not src.exists():
            raise ActionError(f"No existe: {src}")
        if dst.exists():
            raise ActionError(f"Ya existe el destino y no se pisa: {dst}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dst)
        return {"from": str(src), "to": str(dst)}

    def delete_path(self, path: str) -> dict:
        if not self.config.fs_allow_delete:
            raise SandboxError("Borrar está deshabilitado. Se habilita con OPERACIONES_FS_PERMITIR_BORRAR=si.")
        target = self.resolve(path)
        if not target.exists():
            raise ActionError(f"No existe: {target}")
        if target in self.roots():
            raise SandboxError("No se borra una carpeta raíz del sandbox.")
        shutil.rmtree(target) if target.is_dir() else target.unlink()
        return {"deleted": str(target)}

