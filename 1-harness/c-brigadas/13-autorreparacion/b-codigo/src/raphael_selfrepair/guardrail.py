"""Líneas rojas de la autorreparación: lo que NINGÚN arreglo puede tocar, ni con aprobación.

La regla (decisión de Damián, 6 oct 2026): la auto-modificación nunca debilita la seguridad. Si hay que cambiar un
archivo protegido, lo cambia Damián a mano, fuera de este camino. Es un chequeo de ruta puro (sin modelo) y se corre
al proponer Y al aplicar. La config puede SUMAR fragmentos, nunca sacar los de fábrica.
"""

from __future__ import annotations

from collections.abc import Iterable

#: fragmentos de ruta (minúsculas, con "/") que se buscan como subcadena de la ruta normalizada
DEFAULT_PROTECTED: tuple[str, ...] = (
    # alcance del pentest y secretos
    "authorized_targets", ".env", "raphael.env", "meta.env", "tienda.env", "secrets", "secreto", "credentials",
    "credenciales", "claves/", "clave-", "password", "private_key", ".pem",
    # puertas, políticas, aprobaciones y auditoría del harness
    "raphael_core/policy", "raphael_core/approvals", "raphael_core/audit", "raphael_core/isolation",
    "raphael_core/tools.py", "raphael_core/contract", "raphael_core/runtime", "raphael_core/loader",
    "raphael_core/manifest", "raphael_core/installation", "raphael_core/drafts/",
    # niveles de autonomía, modelos e instalación
    "manifest.yaml", "installation.yaml", "modelos.yaml",
    # puerta de tests y automatizaciones
    "gate.py", "gate.bat", "b-herramientas/", ".github/",
    # el repositorio mismo y esta brigada (no puede reescribir su propio guardarraíl)
    ".git/", "13-autorreparacion", "raphael_selfrepair",
    # auth
    "/auth/", "/auth.", "/authentication", "/oauth",
)


def normalize(path: str) -> str:
    return (path or "").replace("\\", "/").lower()


def fragments(extra: Iterable[str] = ()) -> list[str]:
    return [*DEFAULT_PROTECTED, *(normalize(e).strip() for e in extra if e and e.strip())]


def check(path: str, extra: Iterable[str] = ()) -> str | None:
    """El motivo si la ruta es intocable, o None si se puede modificar. Se le pueden pasar varias formas de la misma
    ruta (la que dio la persona y la ya resuelta) con `check_all`."""
    norm = normalize(path)
    # una barra al principio hace que "/auth" y ".git/" también peguen en rutas relativas de primer nivel
    probe = norm if norm.startswith("/") else "/" + norm
    hit = next((f for f in fragments(extra) if f in probe), None)
    if hit is None:
        return None
    return (f"'{path}' es una LÍNEA ROJA de seguridad (coincide con «{hit}»): la autorreparación no puede tocarlo, "
            "ni con aprobación. Si hay que cambiarlo, lo hacés vos a mano, fuera de este camino.")


def check_all(paths: Iterable[str], extra: Iterable[str] = ()) -> str | None:
    for p in paths:
        reason = check(p, extra)
        if reason:
            return reason
    return None
