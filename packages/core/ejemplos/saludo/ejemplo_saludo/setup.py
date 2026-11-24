"""Setup de la brigada de ejemplo: registra al montar la tool que no tiene `entry` en el manifiesto."""

from __future__ import annotations


def register(ctx) -> None:
    shared = ctx.shared   # los mismos datos que ve el cocinero en ctx.shared

    def contar_visitas() -> dict:
        """Cuántas veces escribió cada contacto."""
        return {d["contact"]: d["n"] for d in shared.list("visitas")}

    ctx.register_tool("contar_visitas", contar_visitas)
