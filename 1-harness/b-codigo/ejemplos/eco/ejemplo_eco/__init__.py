"""Brigada eco: la brigada mínima de ejemplo. No importa nada de otras brigadas (solo del núcleo)."""

from __future__ import annotations

from raphael_core import Cook, Message, Reply


class Echo(Cook):
    name = "repetidor"
    version = "1.0.0"

    def interest(self, msg: Message, ctx) -> float:
        return 0.8 if msg.text.lower().startswith("eco") else 0.0

    def handle(self, msg: Message, ctx) -> Reply | None:
        if not msg.text.lower().startswith("eco"):
            return None
        return Reply(msg.text[3:].strip() or "…")

    def on_event(self, event: str, data: dict, ctx) -> None:
        if event == "saludo.hecho":
            n = (ctx.shared.get("oidos", "saludos") or {}).get("n", 0)
            ctx.shared.put("oidos", "saludos", {"n": n + 1})
