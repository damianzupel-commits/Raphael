"""Registro de uso: mensajes recibidos y llamadas a la IA, por mes. Base del cobro, del tope por plan y del
tope en dólares del escalón pago. Portado de `raphael_harness.uso` (Empresas 0.4) con escalón y proveedor.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from ..store import Space


class Usage:
    def __init__(self, space: Space, messages_limit: int, clock: Callable[[], datetime]) -> None:
        self._s = space
        self.limit = messages_limit
        self._clock = clock

    def _month(self) -> str:
        return self._clock().strftime("%Y-%m")

    def _doc(self, month: str | None = None) -> dict:
        month = month or self._month()
        return self._s.get("months", month) or {"month": month, "messages": 0, "ai": {}, "tokens_in": 0, "tokens_out": 0,
                                                "cost_usd": 0.0, "ai_failures": 0, "tiers": {}}

    def record_message(self) -> None:
        d = self._doc()
        d["messages"] += 1
        self._s.put("months", d["month"], d)

    def record_ai(self, role: str, model: str, tokens_in: int, tokens_out: int, cost_usd: float, ok: bool,
                  tier: str = "", provider: str = "") -> None:
        d = self._doc()
        key = f"{role}:{model}"
        d["ai"][key] = d["ai"].get(key, 0) + 1
        d["tokens_in"] += tokens_in
        d["tokens_out"] += tokens_out
        d["cost_usd"] = round(d["cost_usd"] + cost_usd, 6)
        if tier:
            t = d.setdefault("tiers", {}).setdefault(tier, {"calls": 0, "cost_usd": 0.0})
            t["calls"] += 1
            t["cost_usd"] = round(t["cost_usd"] + cost_usd, 6)
        if not ok:
            d["ai_failures"] += 1
        self._s.put("months", d["month"], d)
        if provider and ok:
            day = self._clock().strftime("%Y-%m-%d")
            p = self._s.get("days", f"{day}:{provider}") or {"day": day, "provider": provider, "tokens": 0}
            p["tokens"] += tokens_in + tokens_out
            self._s.put("days", f"{day}:{provider}", p)

    def tokens_today(self, provider: str) -> int:
        doc = self._s.get("days", f"{self._clock().strftime('%Y-%m-%d')}:{provider}")
        return int(doc["tokens"]) if doc else 0

    def spent(self, tiers: list[str] | tuple[str, ...]) -> float:
        """Dólares gastados este mes en esos escalones."""
        d = self._doc()
        return round(sum(d.get("tiers", {}).get(t, {}).get("cost_usd", 0.0) for t in tiers), 6)

    def exceeded(self) -> bool:
        return self._doc()["messages"] > self.limit

    def summary(self, month: str | None = None) -> dict:
        d = self._doc(month)
        return {**d, "limit": self.limit, "exceeded": d["messages"] > self.limit}
