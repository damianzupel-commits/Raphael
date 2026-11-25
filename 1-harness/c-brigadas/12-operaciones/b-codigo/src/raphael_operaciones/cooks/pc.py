"""Cocinero PC: comandos, escritorio y archivos de la PC de Damián. Ejecuta acciones ya aprobadas."""

from __future__ import annotations

from raphael_core import Action, Health
from raphael_core.contract import ActionError

from .base import OpsCook, short

MAX_ACTION_TIMEOUT = 45.0   # una acción ejecutada por el cocinero corre bajo el tope de tiempo del harness


class PcCook(OpsCook):
    name = "pc"
    version = "1.0.0"
    description = "Ejecuta comandos y maneja el escritorio de la PC: abrir apps, capturas, comandos de shell."
    mine = {"abrir_app": "abrir {app} en la PC", "ejecutar_comando": "ejecutar en la PC: {command}",
            "capturar_pantalla": "sacar una captura de la pantalla de la PC"}

    def execute(self, action: Action, ctx) -> str | None:
        ops = self.ops(ctx)
        data = action.data
        if action.type == "abrir_app":
            return "Listo. " + short(ops.desktop_launch_app(str(data.get("app", ""))))
        if action.type == "ejecutar_comando":
            return short(ops.pc_run_command(str(data.get("command", "")), str(data.get("cwd", ".")),
                                            min(float(data.get("timeout", MAX_ACTION_TIMEOUT)), MAX_ACTION_TIMEOUT)))
        if action.type == "capturar_pantalla":
            return "Listo. " + short(ops.desktop_screenshot())
        raise ActionError(f"pc no sabe ejecutar '{action.type}'")

    def health(self, ctx) -> Health:
        ops = self.ops(ctx)
        return Health(True, "PC real" if ops.config.real else "PC simulada")
