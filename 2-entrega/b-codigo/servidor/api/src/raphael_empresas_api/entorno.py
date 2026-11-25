"""Claves y chequeo de arranque: qué cargó Damián y qué falta, sin mostrar jamás un valor.

Las claves viven en un archivo de entorno (`raphael.env`, o `meta.env` en el VPS) que nunca va a git. Este módulo lo lee
(formato `NOMBRE=valor`, como el `.env` de siempre), lo suma al entorno del proceso y arma el informe de arranque:
cada ítem dice si está listo, qué pasa si falta (el sistema degrada, no se rompe) y dónde se consigue.

Reglas: las variables que ya están en el entorno del sistema ganan sobre las del archivo; los valores no se imprimen ni
se loguean (solo "cargada" o "falta"); sin clave de IA se responde por reglas, sin Meta real el canal queda en `mock`.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable, Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: nombres de archivo que se buscan en la carpeta de datos, en este orden (todos los que existan se suman)
ENV_FILES = ("raphael.env", "meta.env", "tienda.env")
_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def parse_env(text: str) -> dict[str, str]:
    """`NOMBRE=valor` por línea. Acepta `export`, comillas, comentarios con `#` y finales de línea de Windows."""
    out: dict[str, str] = {}
    for raw in text.lstrip("﻿").splitlines():
        m = _LINE.match(raw)
        if not m or raw.lstrip().startswith("#"):
            continue
        key, val = m.group(1), m.group(2)
        if val and val[0] in "\"'" and val.count(val[0]) >= 2:
            val = val[1:val.index(val[0], 1)]
        else:
            val = re.split(r"\s+#", val, maxsplit=1)[0].strip()
        out[key] = val
    return out


def load_env(data_dir: str | Path, extra: Iterable[str | Path] = (), environ: MutableMapping[str, str] | None = None
             ) -> list[str]:
    """Suma al entorno lo que traen los archivos (sin pisar lo que ya esté). Devuelve los nombres de archivo leídos."""
    environ = os.environ if environ is None else environ
    paths = [Path(p) for p in extra] + [Path(data_dir) / n for n in ENV_FILES]
    read: list[str] = []
    for p in paths:
        if not p.is_file():
            continue
        for k, v in parse_env(p.read_text(encoding="utf-8-sig", errors="replace")).items():
            if v and not environ.get(k):
                environ[k] = v
        read.append(p.name)
    return read


@dataclass(frozen=True)
class Item:
    area: str
    status: str          # ok | falta | aviso | info
    text: str
    fix: str = ""        # qué hacer / dónde se consigue

    @property
    def blocking(self) -> bool:
        return self.status == "falta"


MARK = {"ok": "[ok]   ", "falta": "[FALTA]", "aviso": "[aviso]", "info": "[info] "}


def _placeholder(v: str) -> bool:
    return not v or v.lower() in {"xxx", "pegar-aca", "pegar_aca", "completar", "changeme", "tu-clave"} or v.startswith("<")


def check(*, env: Mapping[str, str], installation: Any, models: Any, meta: Any, app_key_set: bool,
          env_files: Iterable[str] = (), public_url: str = "") -> list[Item]:
    """El informe de arranque. `models` es el `ModelGateway` (o None), `meta` los `MetaSettings`."""
    items: list[Item] = []
    add = lambda *a, **k: items.append(Item(*a, **k))  # noqa: E731
    files = ", ".join(env_files)
    add("Claves", "ok" if files else "aviso", f"archivo de claves leído: {files}" if files else
        "no hay archivo de claves (raphael.env): se usa solo el entorno del sistema",
        "" if files else "copiá raphael.env.plantilla a raphael.env en la carpeta de datos y completalo")

    # --- IA ---
    key = env.get("OPENROUTER_API_KEY", "")
    if models is None:
        add("IA", "aviso", "sin configuración de modelos: todo responde por reglas", "revisar modelos.yaml")
    elif _placeholder(key):
        add("IA", "aviso", "falta OPENROUTER_API_KEY: la voz de la Secretaria y el ruteo responden por reglas",
            "openrouter.ai → Keys → crear clave; pegarla en raphael.env como OPENROUTER_API_KEY")
    else:
        roles = {r: models.label(r) for r in ("mando", "voz", "ruteo", "cocinero")}
        sin = [r for r, lab in roles.items() if lab == "sin modelo"]
        if sin:
            add("IA", "aviso", f"clave cargada pero sin modelo disponible para: {', '.join(sin)} (tope del mes o pausa)",
                "revisar saldo y paid_cap_usd_month en modelos.yaml")
        else:
            add("IA", "ok", f"OpenRouter cargada · voz: {roles['voz']} · escalón gratis para roles chicos")
        if not key.startswith("sk-or-"):
            add("IA", "aviso", "OPENROUTER_API_KEY no tiene la forma habitual (sk-or-…): puede estar mal copiada",
                "volver a copiarla entera desde openrouter.ai")
    if env.get("NVIDIA_API_KEY"):
        add("IA", "info", "NVIDIA_API_KEY cargada: solo sirve para pruebas; ningún escalón la usa por defecto")

    # --- Meta ---
    if not meta.real:
        add("Meta", "aviso", "modo mock: no sale ningún mensaje a WhatsApp ni a Instagram (lo que saldría queda registrado)",
            "con las claves de Meta cargadas, poner META_MODE=real")
    for p in meta.problems():
        add("Meta", "falta", p, "ver QUE-CARGAR.md, sección Meta")
    if meta.real and not meta.problems():
        chans = [n for n, ok in (("WhatsApp", meta.wa_token and meta.wa_phone_id), ("Instagram", meta.ig_token)) if ok]
        add("Meta", "ok", f"modo real · canales: {', '.join(chans)}")
    if not meta.real:
        add("Meta", "info", "WhatsApp: " + ("token e id cargados" if meta.wa_token and meta.wa_phone_id else "sin cargar")
            + " · Instagram: " + ("token cargado" if meta.ig_token else "sin cargar")
            + " · firma de webhook: " + ("lista" if meta.app_secret else "sin META_APP_SECRET"))
    if public_url:
        add("Meta", "info", f"webhook para pegar en la app de Meta: {public_url.rstrip('/')}/webhook/meta")
    else:
        add("Meta", "info", "RAPHAEL_PUBLIC_URL sin definir: ahí iría la URL pública (túnel o dominio) para el webhook")

    # --- Tienda ---
    src = _store_source(installation)
    if src is not None and src.kind in ("tiendanube", "shopify", "woocommerce"):
        names = {"tiendanube": [src.token_env or "TIENDANUBE_TOKEN"], "shopify": [src.token_env or "SHOPIFY_TOKEN"],
                 "woocommerce": [src.token_env or "WOO_KEY", src.secret_env or "WOO_SECRET"]}[src.kind]
        lost = [n for n in names if _placeholder(env.get(n, ""))]
        add("Tienda", "falta" if lost else "ok", f"{src.kind}: falta {', '.join(lost)}" if lost else f"{src.kind}: token cargado",
            "cargarlo en raphael.env" if lost else "")
    elif src is not None:
        add("Tienda", "info", "sin catálogo de tienda conectado (store.source.kind = " + src.kind + ")")

    # --- Negocio y app ---
    name = _business_name(installation)
    if name in ("Taller Ejemplo", ""):
        add("Perfil", "aviso", "la instalación tiene los datos de EJEMPLO (Taller Ejemplo)",
            "falta el perfil real de la clienta: perfil_a_instalacion.py, después de la entrevista")
    else:
        add("Perfil", "ok", f"negocio: {name}")
    add("App", "ok" if app_key_set else "falta", "clave de la app puesta" if app_key_set else
        "no hay clave de la app: la dueña no puede entrar", "python -m raphael_empresas_api clave --instalacion … --datos …")
    return items


def _brigade_config(installation: Any) -> dict:
    t = (getattr(installation, "brigades", None) or {}).get("empresas")
    cfg = getattr(t, "config", None) if t is not None else None
    return cfg if isinstance(cfg, dict) else {}


def _business_name(installation: Any) -> str:
    return str((_brigade_config(installation).get("business") or {}).get("name", ""))


def _store_source(installation: Any) -> Any:
    store = _brigade_config(installation).get("store")
    if store is None:
        return None
    from raphael_empresas.config import Store

    try:
        return Store.model_validate(store).source
    except Exception:  # noqa: BLE001 - config inválida: la reporta el cargador
        return None


def render(items: list[Item]) -> str:
    lines = []
    for i in items:
        lines.append(f"{MARK[i.status]} {i.area}: {i.text}")
        if i.fix and i.status in ("falta", "aviso"):
            lines.append(f"          → {i.fix}")
    falta = [i for i in items if i.status == "falta"]
    avisos = [i for i in items if i.status == "aviso"]
    if falta:
        verdict = f"Falta lo imprescindible ({len(falta)})."
    elif avisos:
        verdict = f"Arranca, con {len(avisos)} aviso(s): lo que falta degrada a reglas o a mock, no rompe."
    else:
        verdict = "Todo cargado: listo para clientes reales."
    return "\n".join([*lines, "", verdict])


def exit_code(items: list[Item], *, real: bool = False) -> int:
    """0 si puede arrancar; 2 si falta algo imprescindible. Con `real`, los avisos de IA y Meta también cuentan."""
    if any(i.blocking for i in items):
        return 2
    if real and any(i.status == "aviso" and i.area in ("IA", "Meta", "Perfil") for i in items):
        return 2
    return 0
