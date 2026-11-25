"""Lee los archivos de claves y arma el chequeo de lo cargado, sin mostrar nunca un valor secreto completo."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from .catalogo import CUENTAS, Cuenta, Var


def parse_env(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
            v = v[1:-1]
        out[k.strip().removeprefix("export ").strip()] = v
    return out


def cargar(archivos: Iterable[str | Path] = (), environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Archivos primero; el entorno del sistema gana sobre el archivo (igual que el servidor)."""
    env: dict[str, str] = {}
    for a in archivos:
        p = Path(a)
        if p.is_file():
            env.update(parse_env(p.read_text(encoding="utf-8", errors="replace")))
    env.update({k: v for k, v in (os.environ if environ is None else environ).items() if k in _NOMBRES})
    return env


_NOMBRES = {v.nombre for c in CUENTAS for v in c.vars}


def cargada(valor: str | None) -> bool:
    v = (valor or "").strip()
    return bool(v) and not (v.startswith("<") or v.lower() in {"pegar_aca", "xxxx", "cambiar"})


def mascara(var: Var, valor: str | None) -> str:
    if not cargada(valor):
        return "—"
    if not var.secreta:
        return valor.strip()  # type: ignore[union-attr]
    return "cargada (…" + valor.strip()[-4:] + ")" if len(valor.strip()) > 8 else "cargada"


@dataclass(frozen=True)
class Estado:
    cuenta: Cuenta
    estado: str                      # "lista", "parcial", "falta" o "sin_variables"
    faltan: tuple[str, ...]
    problemas: tuple[str, ...]


def _formato(c: Cuenta, env: Mapping[str, str]) -> list[str]:
    out: list[str] = []
    cbu = env.get("TRANSFER_CBU_CVU", "")
    if c.id == "transferencia" and cargada(cbu) and not re.fullmatch(r"\d{22}", cbu.strip()):
        out.append("TRANSFER_CBU_CVU debe tener 22 dígitos")
    dom = env.get("DUCKDNS_DOMAIN", "")
    if c.id == "duckdns" and cargada(dom) and not re.fullmatch(r"[a-z0-9-]+", dom.strip().lower()):
        out.append("DUCKDNS_DOMAIN va sin .duckdns.org y sin símbolos")
    url = env.get("RAPHAEL_PUBLIC_URL", "")
    if c.id == "tailscale" and cargada(url) and not re.fullmatch(r"https://[^/\s]+", url.strip()):
        out.append("RAPHAEL_PUBLIC_URL debe empezar con https:// y no llevar barra al final")
    key = env.get("OPENROUTER_API_KEY", "")
    if c.id == "openrouter" and cargada(key) and not key.strip().startswith("sk-or-"):
        out.append("OPENROUTER_API_KEY debería empezar con sk-or-")
    for modo in ("META_MODE", "MP_MODE"):
        if modo in {v.nombre for v in c.vars} and cargada(env.get(modo)) and env[modo].strip() not in {"mock", "real"}:
            out.append(f"{modo} debe ser mock o real")
    return out


def estado_de(c: Cuenta, env: Mapping[str, str]) -> Estado:
    obligatorias = c.obligatorias()
    if not obligatorias:
        return Estado(c, "sin_variables", (), ())
    faltan = tuple(v.nombre for v in obligatorias if not cargada(env.get(v.nombre)))
    problemas = tuple(_formato(c, env))
    if len(faltan) == len(obligatorias):
        st = "falta"
    elif faltan or problemas:
        st = "parcial"
    else:
        st = "lista"
    return Estado(c, st, faltan, problemas)


def chequear(env: Mapping[str, str], edicion: str = "ambas") -> list[Estado]:
    return [estado_de(c, env) for c in CUENTAS if edicion == "ambas" or c.edicion in (edicion, "ambas")]


def codigo_salida(estados: list[Estado], *, estricto: bool = False) -> int:
    """0 si las cuentas requeridas están listas. Sin `estricto`, que falten solo avisa (Raphael degrada); 2 si hay un
    problema de formato. Con `estricto`, falta lo requerido también da 2."""
    if any(e.problemas for e in estados):
        return 2
    if estricto and any(e.cuenta.requerida and e.estado in {"falta", "parcial"} for e in estados):
        return 2
    return 0


ICONO = {"lista": "OK   ", "parcial": "PARC ", "falta": "FALTA", "sin_variables": "—    "}


def render(estados: list[Estado], env: Mapping[str, str]) -> str:
    lineas: list[str] = []
    for e in estados:
        opc = "" if e.cuenta.requerida else " (opcional)"
        lineas.append(f"{ICONO[e.estado]} {e.cuenta.nombre}{opc}")
        for v in e.cuenta.vars:
            lineas.append(f"        {v.nombre:<22} {mascara(v, env.get(v.nombre))}")
        if e.faltan:
            lineas.append(f"        → falta: {', '.join(e.faltan)}. Si no la cargás: {e.cuenta.sin_clave}")
        for p in e.problemas:
            lineas.append(f"        ! {p}")
    return "\n".join(lineas)
