"""Lo común de los cocineros de Operaciones: el servicio compartido, la lectura de pedidos y la respuesta al dueño."""

from __future__ import annotations

from raphael_core import Action, Cook, Message, Reply
from raphael_core.contract import Origin, Trust

from ..registry import ops_for
from ..service import Operations
from . import rules


class OpsCook(Cook):
    """Un cocinero de Operaciones. `mine` es lo que sabe pedir por reglas: {acción: resumen en español}."""

    mine: dict[str, str] = {}

    def ops(self, ctx) -> Operations:
        return ops_for(ctx)

    def _parsed(self, msg: Message) -> tuple[str, str, dict] | None:
        """Solo órdenes de Damián (de confianza) y que sean de este cocinero. El contenido de terceros es dato."""
        if msg.trust is not Trust.TRUSTED:
            return None
        found = rules.parse(msg.text)
        return found if found and found[0] == self.name and found[1] in self.mine else None

    def interest(self, msg: Message, ctx) -> float:
        return 0.9 if self._parsed(msg) else 0.0

    def handle(self, msg: Message, ctx) -> Reply | None:
        found = self._parsed(msg)
        if found is None:
            return None
        _, action, data = found
        summary = self.mine[action].format(**data)
        return Reply(f"Entendido: {summary}. Queda pendiente de tu aprobación.",
                     [Action(action, data, summary=summary, target=msg.contact, origin=Origin.OWNER)])


def short(result: dict, limit: int = 600) -> str:
    """Un resultado de tool, resumido para contárselo a Damián."""
    if "stdout" in result:
        out = (result.get("stdout") or "").strip()
        err = (result.get("stderr") or "").strip()
        slow = " (se pasó del tiempo y lo corté)" if result.get("timed_out") else ""
        slow = " (se pasó del tiempo y lo corté)" if result.get("timed_out") else ""
        head = f"Código de salida {result.get('exit_code')}{slow}"
        body = out or err or "sin salida"
        return f"{head}:\n{body[:limit]}" + ("…" if len(body) > limit else "")
    keys = ("launched", "focused", "window_title", "url", "title", "screenshot_path", "warning", "logged_in", "message")
    parts = [f"{k}: {result[k]}" for k in keys if result.get(k) not in (None, "")]
    return "; ".join(parts)[:limit] or "listo"
