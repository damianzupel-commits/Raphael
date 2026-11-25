"""Puentes entre las variables que carga Damián y lo que leen las piezas.

Dos piezas nombraron distinto las mismas claves de Mercado Pago (Cuentas y APIs: `MP_*`; la brigada Empresas:
`MERCADOPAGO_*`). Acá se aceptan los dos nombres. Y los datos de la cuenta para transferencias (`TRANSFER_*`) y el modo de
Mercado Pago (`MP_MODE`) se vuelcan a la config de cobros de la brigada antes de arrancar, en una copia de la instalación
(`installation.efectiva.yaml`, en la carpeta de datos). La instalación original no se toca. Cambiarlos pide reiniciar.
"""

from __future__ import annotations

import re
from collections.abc import MutableMapping
from pathlib import Path

import yaml

#: nombre de la brigada -> nombre de Cuentas y APIs (el que se carga en pantalla)
ALIASES = {"MERCADOPAGO_ACCESS_TOKEN": "MP_ACCESS_TOKEN", "MERCADOPAGO_WEBHOOK_SECRET": "MP_WEBHOOK_SECRET"}


def apply_aliases(environ: MutableMapping[str, str]) -> None:
    """Si está uno de los dos nombres, el otro queda igual. El que se cargó explícito no se pisa."""
    for brigade_name, shown in ALIASES.items():
        if environ.get(shown) and not environ.get(brigade_name):
            environ[brigade_name] = environ[shown]
        elif environ.get(brigade_name) and not environ.get(shown):
            environ[shown] = environ[brigade_name]


def efectiva(src: str | Path, dst: str | Path, environ: MutableMapping[str, str], brigade: str = "empresas") -> Path:
    """Copia `src` a `dst` con los cobros de `environ` ya puestos. Devuelve `dst`."""
    data = yaml.safe_load(Path(src).read_text(encoding="utf-8")) or {}
    cfg = data.setdefault("brigades", {}).setdefault(brigade, {"active": True}).setdefault("config", {})
    pay = cfg.setdefault("payments", {})
    for var, key in (("TRANSFER_TITULAR", "holder"), ("TRANSFER_ALIAS", "alias"), ("TRANSFER_BANCO", "bank")):
        if environ.get(var, "").strip():
            pay[key] = environ[var].strip()
    cbu = re.sub(r"\s", "", environ.get("TRANSFER_CBU_CVU", ""))
    if re.fullmatch(r"\d{22}", cbu):
        pay["cbu"] = cbu
    mp: dict = {}
    mode = environ.get("MP_MODE", "").strip().lower()
    if mode in ("mock", "real", "off"):
        mp["mode"] = mode
    elif environ.get("MP_ACCESS_TOKEN") and not (pay.get("mercadopago") or {}).get("mode"):
        mp["mode"] = "real"            # cargó la clave y no dijo nada más: se entiende que la quiere usar
    pub = environ.get("RAPHAEL_PUBLIC_URL", "").rstrip("/")
    has_url = (pay.get("mercadopago") or {}).get("notification_url")
    if pub.startswith("https://") and mp.get("mode") in ("real", "mock") and not has_url:
        mp["notification_url"] = pub + "/webhook/mercadopago"
    if mp:
        pay.setdefault("mercadopago", {}).update(mp)
    if not pay:
        cfg.pop("payments", None)
    Path(dst).write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return Path(dst)
