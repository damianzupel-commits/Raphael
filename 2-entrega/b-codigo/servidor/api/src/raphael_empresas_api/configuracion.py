"""Configuración desde la app: poner o sacar claves a voluntad, sin tocar archivos ni código.

Las claves se guardan SOLO en el archivo local `raphael.env` de la carpeta de datos (fuera de git, permisos 600) y se
aplican en caliente: la IA y el canal de Meta las toman en el momento. Después de guardadas nunca se devuelven completas:
la app solo ve "cargada" y los últimos 4 caracteres. Las de la tienda pedirían reiniciar.
"""

from __future__ import annotations

import contextlib
import os
import re
import tempfile
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path

from .entorno import parse_env


@dataclass(frozen=True)
class Field:
    name: str
    group: str
    label: str
    secret: bool = True
    live: bool = True            # False = hace falta reiniciar
    help: str = ""


FIELDS: tuple[Field, ...] = (
    Field("OPENROUTER_API_KEY", "ia", "Clave de OpenRouter", help="openrouter.ai → Keys (empieza con sk-or-)"),
    Field("META_MODE", "meta", "Modo del canal", secret=False, help="mock = no manda nada · real = manda de verdad"),
    Field("META_VERIFY_TOKEN", "meta", "Verify token del webhook", help="Lo inventás vos y lo pegás igual en la app de Meta"),
    Field("META_APP_SECRET", "meta", "Clave secreta de la app de Meta", help="Configuración → Básica en developers.facebook.com"),
    Field("META_WA_TOKEN", "meta", "WhatsApp: token", help="Token permanente del usuario del sistema"),
    Field("META_WA_PHONE_ID", "meta", "WhatsApp: id del número", secret=False, help="Phone number ID"),
    Field("META_IG_TOKEN", "meta", "Instagram: token", help="Token de usuario de la cuenta profesional"),
    Field("META_IG_HOST", "meta", "Instagram: servidor", secret=False, help="graph.instagram.com o graph.facebook.com"),
    Field("RAPHAEL_PUBLIC_URL", "red", "Dirección pública", secret=False, help="La del túnel; sirve para mostrarte el webhook"),
    Field("TIENDANUBE_TOKEN", "tienda", "Tiendanube: token", live=False),
    Field("SHOPIFY_TOKEN", "tienda", "Shopify: token", live=False),
    Field("WOO_KEY", "tienda", "WooCommerce: key", live=False),
    Field("WOO_SECRET", "tienda", "WooCommerce: secret", live=False),
)
BY_NAME = {f.name: f for f in FIELDS}
MAX_LEN = 600
_ASCII_LINE = re.compile(r"^[\x21-\x7e]+$")   # claves y tokens: sin espacios ni saltos de línea


def hint(value: str) -> str:
    return "…" + value[-4:] if len(value) >= 12 else "••••"


def view(env: Mapping[str, str]) -> list[dict]:
    """Lo que ve la app: nunca el valor completo de un secreto."""
    out = []
    for f in FIELDS:
        v = env.get(f.name, "")
        row = {"name": f.name, "group": f.group, "label": f.label, "secret": f.secret, "help": f.help, "set": bool(v),
               "live": f.live}
        if v:
            row["hint" if f.secret else "value"] = hint(v) if f.secret else v
        out.append(row)
    return out


def validate(name: str, value: str) -> str:
    """El valor limpio o ValueError con el motivo (en español, sin repetir el valor)."""
    if name not in BY_NAME:
        raise ValueError(f"{name} no se puede cambiar desde la app")
    v = value.strip()
    if not v:
        raise ValueError(f"{name} está vacío (para sacarla usá «quitar»)")
    if len(v) > MAX_LEN or not _ASCII_LINE.match(v):
        raise ValueError(f"{name} tiene espacios, saltos de línea o caracteres raros: copiala de nuevo, entera")
    if name == "META_MODE" and v.lower() not in ("mock", "real"):
        raise ValueError("el modo es mock o real")
    if name == "META_IG_HOST" and v not in ("graph.instagram.com", "graph.facebook.com"):
        raise ValueError("el servidor de Instagram es graph.instagram.com o graph.facebook.com")
    if name == "RAPHAEL_PUBLIC_URL" and not v.startswith("https://"):
        raise ValueError("la dirección pública empieza con https://")
    return v.lower() if name == "META_MODE" else v


def write_env_file(path: Path, changes: Mapping[str, str | None]) -> None:
    """Pone (valor) o saca (None) variables en el archivo, conservando comentarios y el resto. Atómico, permisos 600."""
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines() if path.is_file() else []
    seen: set[str] = set()
    out: list[str] = []
    for ln in lines:
        m = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", ln)
        if m and m.group(1) in changes and not ln.lstrip().startswith("#"):
            seen.add(m.group(1))
            v = changes[m.group(1)]
            out.append(f"{m.group(1)}={v or ''}")
        else:
            out.append(ln)
    out += [f"{k}={v}" for k, v in changes.items() if k not in seen and v]
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".raphael-env-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(out) + "\n")
        with contextlib.suppress(OSError):
            os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def apply(path: Path, environ: MutableMapping[str, str], set_: Mapping[str, str], clear: list[str]) -> list[str]:
    """Valida todo primero (si algo está mal no se cambia nada), guarda en el archivo y en el entorno del proceso.
    Devuelve los nombres que necesitan reiniciar para tener efecto."""
    changes: dict[str, str | None] = {}
    for name, value in set_.items():
        changes[name] = validate(name, str(value))
    for name in clear:
        if name not in BY_NAME:
            raise ValueError(f"{name} no se puede cambiar desde la app")
        changes[name] = None
    for name, v in changes.items():
        if v:
            environ[name] = v
        else:
            environ.pop(name, None)
    write_env_file(path, changes)
    return [n for n in changes if not BY_NAME[n].live]


def file_values(path: Path) -> dict[str, str]:
    return parse_env(path.read_text(encoding="utf-8-sig", errors="replace")) if path.is_file() else {}
