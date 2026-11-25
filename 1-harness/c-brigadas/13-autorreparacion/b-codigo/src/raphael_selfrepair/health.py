"""Healthcheck de la brigada (al montar y cada 5 minutos). Tres malos seguidos y la brigada deja de recibir mensajes,
así que solo da mal por lo que de verdad la rompe: una config inválida. Que falte la raíz, git o el modelo NO es
salud mala: se avisa en el detalle y los comandos que lo necesitan dicen qué falta."""

from __future__ import annotations

from pydantic import ValidationError
from raphael_core import Health

from .config import ROOT_ENV, repair_config, resolve_root
from .fixer import is_git_repo


def _first_error(exc: ValidationError) -> str:
    first = exc.errors()[0]
    return f"{'.'.join(map(str, first['loc']))}: {first['msg']}"


def check(ctx) -> Health:
    try:
        cfg = repair_config(ctx.config)
    except ValidationError as exc:
        return Health(False, f"config inválida: {_first_error(exc)}")
    notes: list[str] = []
    root = resolve_root(cfg)
    if root is None:
        notes.append(f"sin raíz del proyecto: cargá {ROOT_ENV} para poder proponer y aplicar arreglos")
    elif not root.is_dir():
        notes.append(f"la raíz '{root}' no existe")
    elif cfg.git_commit and not is_git_repo(root):
        notes.append("la raíz no es un repo git: los arreglos no quedan en commits")
    if not cfg.verify_command:
        notes.append("sin comando de verificación: un arreglo no se deshace solo si rompe los tests")
    if not ctx.has_ai("cocinero"):
        notes.append("sin modelo: no redacto arreglos, solo aplico los que me das")
    return Health(True, "ok" + (f" (avisos: {'; '.join(notes)})" if notes else ""))


def validate(ctx) -> None:
    """`setup` del manifiesto: con una config inválida la brigada no se monta (y el error dice qué campo)."""
    try:
        repair_config(ctx.config)
    except ValidationError as exc:
        raise ValueError(f"config inválida: {_first_error(exc)}") from None
