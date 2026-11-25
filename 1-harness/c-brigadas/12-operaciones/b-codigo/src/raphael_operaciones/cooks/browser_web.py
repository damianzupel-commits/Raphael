"""Cocinero Navegador y web: abre el navegador automatizado y trae páginas."""

from __future__ import annotations

from raphael_core import Action
from raphael_core.contract import ActionError

from .base import OpsCook, short


class BrowserWebCook(OpsCook):
    name = "browser-web"
    version = "1.0.0"
    description = "Abre páginas en el navegador automatizado y trae contenido de la web."
    mine = {"abrir_url": "abrir {url} en el navegador"}
    commands = {"sitios": "sitios donde hay credencial cargada (sin contraseñas)"}

    async def execute(self, action: Action, ctx) -> str | None:
        if action.type == "abrir_url":
            return "Listo. " + short(await self.ops(ctx).browser_open(str(action.data.get("url", ""))))
        raise ActionError(f"browser-web no sabe ejecutar '{action.type}'")

    def command(self, name: str, data: dict, ctx):
        if name == "sitios":
            return self.ops(ctx).web_credential_list()
        return super().command(name, data, ctx)
