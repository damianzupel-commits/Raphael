"""Cocinero Supervisor: el modo de operación (supervisado o autónomo), el estado y el registro de lo que se hizo.

Además le presta su modelo LOCAL al servicio para revisar los llamados de efecto antes de ejecutarlos (si
`supervisor: si` en la config). Falla abierto: sin modelo local o con una respuesta rara, no bloquea.
"""

from __future__ import annotations

from raphael_core import Health
from raphael_core.contract import ActionError

from ..modes import parse_mode
from ..registry import release
from ..setup import LOG_COLLECTION
from .base import OpsCook

MAX_LOG = 200


class SupervisorCook(OpsCook):
    name = "supervisor"
    version = "1.0.0"
    description = "Supervisa las operaciones: modo supervisado o autónomo, estado y registro de acciones."
    commands = {"estado": "cómo está Operaciones: modo, adaptadores, interruptores, celular, carpetas",
                "registro": "las últimas acciones que hizo Operaciones ({'n': cuántas})",
                "modo": "cambia el modo de operación {'modo': 'supervisado'|'autonomo'} (solo la persona)"}

    def start(self, ctx) -> None:
        ops = self.ops(ctx)
        # el modelo del supervisor es LOCAL: lo que revisa son pantallas, archivos y comandos (lo más sensible)
        ops.asker = lambda messages: ctx.ai("cocinero", messages, private=True, max_tokens=200, temperature=0)

    def command(self, name: str, data: dict, ctx):
        ops = self.ops(ctx)
        if name == "estado":
            return {**ops.status(), "ia_para_el_jefe": bool(ctx.has_ai("jefe"))}
        if name == "registro":
            n = max(1, min(int(data.get("n", 20) or 20), MAX_LOG))
            rows = sorted(ctx.shared.list(LOG_COLLECTION), key=lambda r: r.get("n", 0))
            return rows[-n:]
        if name == "modo":
            wanted, warn = parse_mode(str(data.get("modo", "")))
            if warn or not str(data.get("modo", "")).strip():
                raise ActionError("El modo tiene que ser 'supervisado' o 'autonomo'.")
            before = ops.mode.mode
            try:
                ops.set_mode(wanted)
            except PermissionError as exc:
                raise ActionError(str(exc)) from exc
            ctx.record("modo_cambiado", antes=before.value, ahora=wanted.value)
            return {"modo": ops.mode.mode.value, "antes": before.value, "raices": [str(r) for r in ops.sandbox.roots()]}
        return super().command(name, data, ctx)

    def health(self, ctx) -> Health:
        return Health(True, f"modo {self.ops(ctx).mode.mode.value}")

    async def stop(self, ctx) -> None:
        ops = release(ctx)
        if ops is not None:
            ops.asker = None
            await ops.aclose()

