"""Lo común de los cocineros: armar el servicio desde el contexto y contestar errores esperados con un mensaje claro."""

from __future__ import annotations

import re

from raphael_core import ActionError, Cook, Message

from ..casefile import CaseError
from ..env import env_from_context
from ..service import Investigacion
from ..web import WebError


class InvCook(Cook):
    interest_pattern: re.Pattern[str] | None = None

    def inv(self, ctx) -> Investigacion:
        return Investigacion(env_from_context(ctx))

    def interest(self, msg: Message, ctx) -> float:
        return 0.6 if self.interest_pattern and self.interest_pattern.search(msg.text.lower()) else 0.0

    def command(self, name, data, ctx):
        try:
            return self.run_command(name, data or {}, ctx)
        except (CaseError, WebError) as exc:
            raise ActionError(str(exc)) from None

    def execute(self, action, ctx):
        try:
            return self.run_action(action, ctx)
        except (CaseError, WebError) as exc:
            raise ActionError(str(exc)) from None

    def run_command(self, name: str, data: dict, ctx):
        return super().command(name, data, ctx)

    def run_action(self, action, ctx):
        return super().execute(action, ctx)
