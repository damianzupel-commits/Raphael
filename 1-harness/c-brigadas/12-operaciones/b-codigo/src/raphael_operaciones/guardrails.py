"""Guardarraíles de texto: listas de patrones obviamente destructivos. Portado de `pc_command.py`, `phone_link.py` y
`desktop.py` de JarvisRemote.

IMPORTANTE: es una mitigación de "evitar el desastre obvio" por coincidencia de texto, NO un sandbox. Lo que no coincide
se ejecuta igual (siempre después de la aprobación que pide el manifiesto). La defensa de verdad es el nivel de
autonomía: ningún comando corre sin que Damián lo apruebe.

Cambio respecto de JarvisRemote: `format` solo bloquea el comando `format` de Windows (en posición de comando y con una
unidad: `format c:`), no cualquier texto que tenga la palabra (`git log --format=...`, `"{}".format(x)`).
"""

from __future__ import annotations

import re

from raphael_core.contract import ActionError


class BlockedError(ActionError):
    """El guardarraíl frenó el pedido. El mensaje va a la persona."""


_CMD_START = r"(?:^|[;&|(]\s*|/[ck]\s+|-command\s+|-c\s+)"   # al empezar, tras ; & | ( o tras cmd /c, powershell -command

PC_COMMAND_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("format (formatear un disco)", re.compile(_CMD_START + r"format(\.com)?\s+[a-z]:")),
    ("diskpart (partición de discos)", re.compile(r"\bdiskpart(\.exe)?\b")),
    ("cipher /w (borrado seguro de espacio libre)", re.compile(r"\bcipher\b[^\n]*\s/w\b")),
    ("vssadmin delete (borra shadow copies/backups)", re.compile(r"\bvssadmin\b[^\n]*\bdelete\b")),
    ("bcdedit (config de arranque)", re.compile(r"\bbcdedit(\.exe)?\b")),
    ("shutdown/reinicio/cierre de sesión forzado de la PC",
     re.compile(r"\bshutdown\b[^\n]*(/s|/r|/l|-s\b|-r\b)")),
    ("rmdir /s o del /f /s /q sobre una unidad completa",
     re.compile(r"\b(rmdir|rd|del|erase)\b[^\n]*\s/s\b[^\n]*\b[a-z]:\\?\s*($|[\\\"'])")),
    ("Remove-Item recursivo/forzado sobre la raíz o el home (PowerShell)",
     re.compile(r"remove-item[^\n]*-recurse[^\n]*-force[^\n]*(\$env:userprofile|~|[a-z]:\\\s*($|[\"']))")),
    ("rm -rf sobre la raíz o el home (bash/WSL/git-bash)",
     re.compile(r"\brm\s+(-[a-z]*r[a-z]*f[a-z]*|-[a-z]*f[a-z]*r[a-z]*)\s+(/|~|\$home)(\s|/\*|$)")),
    ("mkfs (formatear un filesystem)", re.compile(r"\bmkfs(\.\w+)?\b")),
    ("dd escribiendo directo a un block device", re.compile(r"\bdd\b[^\n]*\bof=/dev/")),
    ("fork bomb (bash)", re.compile(r":\s*\(\s*\)\s*\{[^}]*:\s*\|\s*:.*&.*\}\s*;\s*:")),
    ("fork bomb (batch de Windows, %0|%0)", re.compile(r"%0\s*\|\s*%0")),
]

LAUNCH_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("format (formatear un disco)", re.compile(r"\bformat(\.com)?\b", re.IGNORECASE)),
    ("diskpart (partición de discos)", re.compile(r"\bdiskpart(\.exe)?\b", re.IGNORECASE)),
    ("cipher /w (borrado seguro de espacio libre)", re.compile(r"\bcipher\b[^\n]*\s/w\b", re.IGNORECASE)),
    ("vssadmin delete (borra shadow copies/backups)", re.compile(r"\bvssadmin\b[^\n]*\bdelete\b", re.IGNORECASE)),
    ("bcdedit (config de arranque)", re.compile(r"\bbcdedit(\.exe)?\b", re.IGNORECASE)),
]

PHONE_COMMAND_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("rm -rf sobre la raíz o el home",
     re.compile(r"\brm\s+(-[a-z]*r[a-z]*f[a-z]*|-[a-z]*f[a-z]*r[a-z]*)\s+(/|~|\$home)(\s|/\*|$)")),
    ("mkfs (formatear un filesystem)", re.compile(r"\bmkfs(\.\w+)?\b")),
    ("dd escribiendo directo a un block device", re.compile(r"\bdd\b[^\n]*\bof=/dev/")),
    ("fork bomb", re.compile(r":\s*\(\s*\)\s*\{[^}]*:\s*\|\s*:.*&.*\}\s*;\s*:")),
    ("chmod/chown recursivo sobre la raíz", re.compile(r"\b(chmod|chown)\s+-r\s+\S+\s+/(\s|$)")),
    ("escritura directa a un block device", re.compile(r">\s*/dev/(sd|mmcblk|block)\w*")),
]


def _normalize(command: str) -> str:
    return " ".join(str(command).lower().split())


def _check(patterns: list[tuple[str, re.Pattern]], text: str, what: str) -> None:
    for name, pattern in patterns:
        if pattern.search(text):
            raise BlockedError(f"{what} rechazado por el guardarraíl de seguridad (patrón: {name}). Es una mitigación de "
                               "'evitar el desastre obvio' por coincidencia de texto, no un sandbox: si de verdad hace "
                               "falta, hacelo a mano.")


def check_pc_command(command: str) -> None:
    _check(PC_COMMAND_PATTERNS, _normalize(command), "Comando")


def check_launch(path_or_name: str) -> None:
    _check(LAUNCH_PATTERNS, str(path_or_name), "Lanzamiento")


def check_phone_command(command: str) -> None:
    _check(PHONE_COMMAND_PATTERNS, _normalize(command), "Comando del celular")


# --- lo que queda en el registro ------------------------------------------------------------------------------------
SECRET_KEYS = ("password", "clave", "contrasena", "contraseña", "token", "secret", "passwd")
TYPED_KEYS = ("text", "texto", "content", "contenido")   # lo que se tipea o escribe: puede ser una clave; solo el largo


def redact_args(args: dict, limit: int = 200) -> dict:
    """Los argumentos de un llamado, listos para el registro: sin secretos ni texto tipeado, y acotados."""
    out: dict = {}
    for key, value in (args or {}).items():
        low = str(key).lower()
        if any(s in low for s in SECRET_KEYS):
            out[key] = "***"
        elif low in TYPED_KEYS and isinstance(value, str):
            out[key] = f"<{len(value)} caracteres>"
        elif isinstance(value, str) and len(value) > limit:
            out[key] = value[:limit] + "…"
        else:
            out[key] = value
    return out
