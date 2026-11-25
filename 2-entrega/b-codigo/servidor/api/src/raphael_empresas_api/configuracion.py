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
from urllib.parse import urlparse

from . import permisos
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
    Field("MP_ACCESS_TOKEN", "cobros", "Mercado Pago: token", live=False, help="developers de Mercado Pago → Credenciales (el de prueba primero)"),
    Field("MP_WEBHOOK_SECRET", "cobros", "Mercado Pago: clave de avisos", live=False, help="Sin ella no se acepta ningún aviso de pago"),
    Field("MP_MODE", "cobros", "Mercado Pago: modo", secret=False, live=False, help="mock = simulado · real = cobra de verdad"),
    Field("TRANSFER_TITULAR", "cobros", "Transferencia: titular", secret=False, live=False, help="Nombre del titular de la cuenta de la dueña"),
    Field("TRANSFER_CBU_CVU", "cobros", "Transferencia: CBU o CVU", secret=False, live=False, help="22 dígitos"),
    Field("TRANSFER_ALIAS", "cobros", "Transferencia: alias", secret=False, live=False),
    Field("TRANSFER_BANCO", "cobros", "Transferencia: banco", secret=False, live=False),
    Field("LOCAL_LLM_URL", "ia", "Modelo local: dirección", secret=False, help="Ollama http://127.0.0.1:11434 · LM Studio :1234"),
    Field("LOCAL_LLM_KIND", "ia", "Modelo local: programa", secret=False, help="ollama o lmstudio"),
    Field("DUCKDNS_TOKEN", "red", "DuckDNS: token (opcional)", live=False, help="duckdns.org, arriba en la página"),
    Field("DUCKDNS_DOMAIN", "red", "DuckDNS: subdominio", secret=False, live=False, help="Sin .duckdns.org"),
    Field("HCLOUD_TOKEN", "red", "Hetzner: token (opcional)", live=False, help="Solo cuando haya VPS"),
    Field("RAPHAEL_PUBLIC_URL", "red", "Dirección pública", secret=False, help="La del túnel; sirve para mostrarte el webhook"),
    Field("TIENDANUBE_TOKEN", "tienda", "Tiendanube: token", live=False),
    Field("SHOPIFY_TOKEN", "tienda", "Shopify: token", live=False),
    Field("WOO_KEY", "tienda", "WooCommerce: key", live=False),
    Field("WOO_SECRET", "tienda", "WooCommerce: secret", live=False),
)
BY_NAME = {f.name: f for f in FIELDS}
MAX_LEN = 600
FREE_TEXT = {"TRANSFER_TITULAR", "TRANSFER_BANCO"}
_ASCII_LINE = re.compile(r"^[\x21-\x7e]+$")   # claves y tokens: sin espacios ni saltos de línea


def hint(value: str) -> str:
    return "…" + value[-4:] if len(value) >= 12 else "••••"


def view(env: Mapping[str, str], fields: tuple[Field, ...] = FIELDS) -> list[dict]:
    """Lo que ve la app: nunca el valor completo de un secreto."""
    out = []
    for f in fields:
        v = env.get(f.name, "")
        row = {"name": f.name, "group": f.group, "label": f.label, "secret": f.secret, "help": f.help, "set": bool(v),
               "live": f.live}
        if v:
            row["hint" if f.secret else "value"] = hint(v) if f.secret else v
        out.append(row)
    return out


def validate(name: str, value: str, by_name: Mapping[str, Field] = BY_NAME, extra=None) -> str:
    """El valor limpio o ValueError con el motivo (en español, sin repetir el valor).
    `by_name`: los campos que acepta esta edición. `extra(name, valor)`: validación propia (devuelve el valor o ValueError)."""
    if name not in by_name:
        raise ValueError(f"{name} no se puede cambiar desde la app")
    v = value.strip()
    if not v:
        raise ValueError(f"{name} está vacío (para sacarla usá «quitar»)")
    if name == "TRANSFER_CBU_CVU":
        v = re.sub(r"[\s.-]", "", v)               # se suele pegar con espacios o guiones
    if name in FREE_TEXT:                           # nombres y bancos: con espacios y tildes, pero una sola línea limpia
        if len(v) > 80 or not v.isprintable() or "#" in v or '"' in v or "'" in v:
            raise ValueError(f"{name} tiene que ser una sola línea corta, sin comillas ni #")
    elif len(v) > MAX_LEN or not _ASCII_LINE.match(v):
        raise ValueError(f"{name} tiene espacios, saltos de línea o caracteres raros: copiala de nuevo, entera")
    if name == "META_MODE" and v.lower() not in ("mock", "real"):
        raise ValueError("el modo es mock o real")
    if name == "META_IG_HOST" and v not in ("graph.instagram.com", "graph.facebook.com"):
        raise ValueError("el servidor de Instagram es graph.instagram.com o graph.facebook.com")
    if name == "RAPHAEL_PUBLIC_URL" and not v.startswith("https://"):
        raise ValueError("la dirección pública empieza con https://")
    if name == "MP_MODE" and v.lower() not in ("mock", "real", "off"):
        raise ValueError("el modo de Mercado Pago es mock, real u off")
    if name == "TRANSFER_CBU_CVU":
        if not re.fullmatch(r"\d{22}", v):
            raise ValueError("el CBU o CVU tiene 22 dígitos")
    if name == "LOCAL_LLM_KIND" and v.lower() not in ("ollama", "lmstudio"):
        raise ValueError("es ollama o lmstudio")
    if name == "LOCAL_LLM_URL" and (urlparse(v).hostname or "") not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("el modelo local corre en esta PC: http://127.0.0.1:<puerto>")
    if extra is not None:
        return extra(name, v)
    return v.lower() if name in ("META_MODE", "MP_MODE", "LOCAL_LLM_KIND") else v


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
        permisos.restringir(tmp)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def apply(path: Path, environ: MutableMapping[str, str], set_: Mapping[str, str], clear: list[str],
          by_name: Mapping[str, Field] = BY_NAME, extra=None) -> list[str]:
    """Valida todo primero (si algo está mal no se cambia nada), guarda en el archivo y en el entorno del proceso.
    Devuelve los nombres que necesitan reiniciar para tener efecto."""
    changes: dict[str, str | None] = {}
    for name, value in set_.items():
        changes[name] = validate(name, str(value), by_name, extra)
    for name in clear:
        if name not in by_name:
            raise ValueError(f"{name} no se puede cambiar desde la app")
        changes[name] = None
    for name, v in changes.items():
        if v:
            environ[name] = v
        else:
            environ.pop(name, None)
    write_env_file(path, changes)
    return [n for n in changes if not by_name[n].live]


def file_values(path: Path) -> dict[str, str]:
    return parse_env(path.read_text(encoding="utf-8-sig", errors="replace")) if path.is_file() else {}
