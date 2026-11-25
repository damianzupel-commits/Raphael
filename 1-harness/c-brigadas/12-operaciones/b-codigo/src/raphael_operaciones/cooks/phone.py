"""Cocinero Celular: toca, desliza, escribe, saca fotos y lee la pantalla del celular de Damián."""

from __future__ import annotations

from raphael_core import Action
from raphael_core.contract import ActionError

from .base import OpsCook, short


class PhoneCook(OpsCook):
    name = "phone"
    version = "1.0.0"
    description = "Maneja el celular: abrir apps, leer la pantalla, sacar fotos."
    mine = {"celular_abrir_app": "abrir {package_name} en el celular", "leer_pantalla_celular": "leer la pantalla del celular",
            "sacar_foto": "sacar una foto con el celular"}
    commands = {"conectado": "si hay un celular conectado ahora"}

    async def execute(self, action: Action, ctx) -> str | None:
        ops = self.ops(ctx)
        data = action.data
        if action.type == "celular_abrir_app":
            return "Listo. " + _phone_text(await ops.phone_open_app(str(data.get("package_name", ""))))
        if action.type == "leer_pantalla_celular":
            return _phone_text(await ops.phone_read_screen())
        if action.type == "sacar_foto":
            return "Listo. " + _phone_text(await ops.phone_take_photo(str(data.get("camera", "back"))))
        raise ActionError(f"phone no sabe ejecutar '{action.type}'")

    def command(self, name: str, data: dict, ctx):
        if name == "conectado":
            return {"conectado": bool(self.ops(ctx).adapters.phone.connected)}
        return super().command(name, data, ctx)


def _phone_text(result) -> str:
    return short(result) if isinstance(result, dict) else str(result)[:600]
