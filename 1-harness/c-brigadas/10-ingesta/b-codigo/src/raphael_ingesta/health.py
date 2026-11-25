"""Healthcheck (al montar y cada 5 minutos). Solo da mal por lo que de verdad la rompe: una config inválida o un vault
que no se puede escribir. Que falte yt-dlp o que no haya modelo NO es salud mala: se avisa en el detalle y se sigue
(YouTube dice por qué no puede; sin modelo se resume por reglas)."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from raphael_core import Health

from .config import SOURCES, settings_of


def _problem(config: dict) -> str:
    cfg = settings_of(config)
    if cfg.mode not in ("real", "simulado") or any(m not in ("real", "simulado") for m in cfg.modes.values()):
        return "modo inválido: usar 'real' o 'simulado'"
    if any(s not in SOURCES for s in cfg.modes):
        return f"fuente desconocida en 'modos' (válidas: {', '.join(SOURCES)})"
    if cfg.per_tick < 1 or cfg.check_every_min < 1 or cfg.max_per_list < 1:
        return "por_pasada, revisar_cada_min y max_por_lista tienen que ser 1 o más"
    return ""


def check(ctx) -> Health:
    bad = _problem(ctx.config)
    if bad:
        return Health(False, bad)
    cfg = settings_of(ctx.config)
    notes: list[str] = []
    if cfg.vault_dir:
        root = Path(cfg.vault_dir).expanduser()
        if root.exists() and not os.access(root, os.W_OK):
            return Health(False, f"no puedo escribir en el vault: {root}")
    else:
        notes.append("sin RAPHAEL_VAULT_DIR: las notas quedan solo en el almacén de la brigada")
    if cfg.mode_of("youtube") == "real" and importlib.util.find_spec("yt_dlp") is None:
        notes.append("falta yt-dlp: YouTube no va a andar")
    return Health(True, "ok" + (f" ({'; '.join(notes)})" if notes else ""))


def validate(ctx) -> None:
    """`setup` del manifiesto: con una config inválida la brigada no se monta, y el error dice qué pasa."""
    bad = _problem(ctx.config)
    if bad:
        raise ValueError(f"config de ingesta inválida: {bad}")
