"""Healthcheck y setup. La brigada no depende de nada externo para estar sana: lo que falta se avisa, no la tumba."""

from __future__ import annotations

from raphael_core import Health

from .settings import Settings, validate_config
from .tools import make_tools


def _notes(ctx) -> list[str]:
    s = Settings.build(ctx.config)
    out = []
    if not s.repos:
        out.append("sin repos autorizados para auditar (config repos o SEGURIDAD_REPOS)")
    if (s.env.get("SEGURIDAD_ADVISORIES") or "off") == "off":
        out.append("dependencias sin revisar (SEGURIDAD_ADVISORIES=off)")
    return out


def check(ctx) -> Health:
    bad = validate_config(ctx.config)
    if bad:
        return Health(False, f"config inválida: {bad}")
    notes = _notes(ctx)
    return Health(True, "ok" + (f" (falta: {'; '.join(notes)})" if notes else ""))


def validate(ctx) -> None:
    """`setup`: valida la config, anota la edición para los cocineros y registra las tools (las de escaneo activo no se cargan en la nube)."""
    bad = validate_config(ctx.config)
    if bad:
        raise ValueError(f"config de seguridad inválida: {bad}")
    ctx.shared.put("estado", "modo", {"edition": ctx.edition, "pasivo": ctx.edition != "personal"})
    for name, fn in make_tools(ctx.edition, Settings.build(ctx.config)).items():
        ctx.register_tool(name, fn)
