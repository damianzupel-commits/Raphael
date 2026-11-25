"""Healthcheck y `setup` de la brigada. Tres chequeos malos seguidos y la brigada deja de recibir mensajes, así que SOLO
da mal por lo que de verdad la rompe: una config inválida o un vault que no se puede escribir. Que no estén prendidos
LM Studio u Ollama NO es salud mala: Cerebro sigue por palabra clave y por reglas, y lo dice en el detalle."""

from __future__ import annotations

from pydantic import ValidationError
from raphael_core import Health

from .brain import Brain
from .config import memoria_config, vault_path


def _config_error(exc: ValidationError) -> str:
    first = exc.errors()[0]
    return f"config de Memoria inválida: {'.'.join(map(str, first['loc']))}: {first['msg']}"


def check(ctx) -> Health:
    try:
        cfg = memoria_config(ctx.config)
    except ValidationError as exc:
        return Health(False, _config_error(exc))
    root = vault_path(cfg)
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".salud"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        return Health(False, f"no puedo escribir en el vault ({root}): {exc.strerror or type(exc).__name__}")
    brain = Brain.from_ctx(ctx)
    avisos = []
    if brain.embedder.name == "off" or brain.embedder.embed("prueba") is None:
        avisos.append("sin embeddings (" + (brain.embedder.last_error or "apagados") + "): busca por palabra clave")
    if not brain.has_model():
        avisos.append("sin modelo local: sintetiza y destila por reglas")
    return Health(True, "ok" + (" · " + "; ".join(avisos) if avisos else ""))


def validate(ctx) -> None:
    """`setup` del manifiesto: con una config inválida la brigada no se monta (y el error dice qué campo)."""
    try:
        memoria_config(ctx.config)
    except ValidationError as exc:
        raise ValueError(_config_error(exc)) from None
