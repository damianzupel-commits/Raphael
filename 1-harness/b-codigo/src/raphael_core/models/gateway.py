"""Pasarela de modelos: elige la IA por rol y escalón, rota entre proveedores y nunca rompe al que la llama.

Para un pedido arma la lista de candidatos: el orden de escalones del rol (override "rol.id" > plan > rol),
y dentro de cada escalón sus proveedores en rotación. Saltea los que:
    - no tienen base_url/model, o les falta la clave en el entorno;
    - están en pausa (dieron "límite alcanzado" o fallaron hace poco);
    - se pasaron de sus pedidos por minuto o de su cupo diario de tokens;
    - cuestan plata y el escalón pago ya llegó a su tope del mes (con tope 0, solo los gratis);
    - son el escalón local en la edición nube;
    - no corren en la PC y el pedido es privado.
Prueba en orden; si todos fallan o no hay ninguno, devuelve None y el cocinero sigue con sus reglas.
Habla con cualquier endpoint OpenAI-compatible (/chat/completions). El transporte se inyecta en las pruebas.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .config import ModelsConfig, ProviderSpec
from .usage import Usage

Transport = Callable[[str, dict, dict], dict]


@dataclass(frozen=True)
class Candidate:
    tier: str
    name: str
    spec: ProviderSpec


def _http(timeout: float) -> Transport:
    def send(url: str, body: dict, headers: dict) -> dict[str, Any]:
        import httpx

        r = httpx.post(url, json=body, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.json()
    return send


def _is_rate_limit(exc: BaseException) -> bool:
    status = getattr(getattr(exc, "response", None), "status_code", None) or getattr(exc, "status_code", None)
    return status == 429 or "429" in str(exc)[:60]


class ModelGateway:
    def __init__(self, config: ModelsConfig, usage: Usage, *, plan: str = "", edition: str = "personal",
                 env: dict[str, str] | None = None, transport: Transport | None = None, timeout: float = 30.0,
                 monotonic: Callable[[], float] = time.monotonic) -> None:
        self.config = config
        self.usage = usage
        self.plan = plan
        self.edition = edition
        self._env = env if env is not None else dict(os.environ)
        self._transport = transport or _http(timeout)
        self._now = monotonic
        self._paused: dict[str, float] = {}
        self._calls: dict[str, deque[float]] = defaultdict(deque)
        self._turn: dict[str, int] = defaultdict(int)

    def set_env(self, env: dict[str, str]) -> None:
        """Cambia las claves en caliente (la pantalla de Configuración). Se copia: el gateway no comparte el diccionario."""
        self._env = dict(env)

    # --- elección -------------------------------------------------------------------------------------------------------
    def chain(self, role: str, *, target: str | None = None, prefer: str | None = None) -> list[str]:
        """Escalones en orden para ese rol (y esa brigada o ayudante, si tiene override)."""
        role = self.config.canonical(role)
        chain: list[str] | None = None
        if target:
            chain = self.config.overrides.get(f"{role}.{target}")
        if chain is None and self.plan:
            chain = self.config.plans.get(self.plan, {}).get(role)
        if chain is None:
            chain = self.config.roles.get(role, [])
        chain = list(chain)
        if prefer and prefer in self.config.tiers:
            chain = [prefer, *[t for t in chain if t != prefer]]
        return chain

    def _key(self, spec: ProviderSpec) -> str | None:
        if spec.api_key:
            return spec.api_key
        return self._env.get(spec.api_key_env) if spec.api_key_env else ""

    def _skip(self, tier: str, name: str, spec: ProviderSpec, private: bool) -> str | None:
        """Por qué no se puede usar este proveedor ahora (None = se puede)."""
        if not spec.usable:
            return "sin base_url o modelo"
        if self._key(spec) is None:
            return f"falta la clave en {spec.api_key_env}"
        if tier == "local" and self.edition == "cloud":
            return "el escalón local no existe en la nube"
        if private and not spec.is_local:
            return "pedido privado y el proveedor no corre en la PC"
        if self._paused.get(name, 0.0) > self._now():
            return "en pausa"
        if spec.rpm:
            window = self._calls[name]
            while window and window[0] < self._now() - 60:
                window.popleft()
            if len(window) >= spec.rpm:
                return "llegó a sus pedidos por minuto"
        if spec.tokens_per_day and self.usage.tokens_today(name) >= spec.tokens_per_day:
            return "se quedó sin cupo diario"
        if tier in self.config.paid_tiers and not spec.free:
            if self.usage.spent(self.config.paid_tiers) >= self.config.paid_cap_usd_month:
                return "el escalón pago llegó a su tope del mes"
        return None

    def candidates(self, role: str, *, target: str | None = None, private: bool = False,
                   prefer: str | None = None) -> list[Candidate]:
        private = private or bool(target and target in self.config.private)
        out: list[Candidate] = []
        seen: set[tuple[str, str]] = set()
        for tier in self.chain(role, target=target, prefer=prefer):
            names = self.config.tiers.get(tier, [])
            if not names:
                continue
            start = self._turn[tier] % len(names)
            for name in names[start:] + names[:start]:   # rotación dentro del escalón
                spec = self.config.providers[name]
                if (tier, name) in seen or self._skip(tier, name, spec, private) is not None:
                    continue
                seen.add((tier, name))
                out.append(Candidate(tier, name, spec))
        return out

    def available(self, role: str, *, target: str | None = None, private: bool = False) -> bool:
        return not self.usage.exceeded() and bool(self.candidates(role, target=target, private=private))

    def explain(self, role: str, *, target: str | None = None, private: bool = False) -> list[dict]:
        """Para el panel: cada escalón y proveedor del rol, y si se puede usar o por qué no. Sin claves."""
        private = private or bool(target and target in self.config.private)
        rows = []
        for tier in self.chain(role, target=target):
            for name in self.config.tiers.get(tier, []):
                spec = self.config.providers[name]
                why = self._skip(tier, name, spec, private)
                rows.append({"tier": tier, "provider": name, "model": spec.model, "ok": why is None, "why": why or ""})
        return rows

    # --- llamada --------------------------------------------------------------------------------------------------------
    def label(self, role: str, *, target: str | None = None, private: bool = False) -> str:
        """Qué modelo atendería ahora este rol ('nvidia: nemotron…'), para las vistas. 'sin modelo' si no hay ninguno."""
        c = next(iter(self.candidates(role, target=target, private=private)), None)
        return f"{c.name}: {c.spec.model}" if c else "sin modelo"

    def _send(self, role: str, messages: list[dict], accept: Callable[[dict], Any], *, target: str | None,
              private: bool, prefer: str | None, body: dict) -> Any:
        """Recorre los candidatos hasta que uno devuelva un mensaje que `accept` acepte (no None). Registra el uso."""
        if self.usage.exceeded():
            return None
        for c in self.candidates(role, target=target, private=private, prefer=prefer):
            headers = {"Content-Type": "application/json"}
            key = self._key(c.spec)
            if key:
                headers["Authorization"] = f"Bearer {key}"   # la clave de ESTE proveedor, solo a él
            self._calls[c.name].append(self._now())
            try:
                data = self._transport(f"{c.spec.base_url.rstrip('/')}/chat/completions",
                                       {"model": c.spec.model, "messages": messages, **body, **c.spec.extra}, headers)
                out = accept(data["choices"][0]["message"] or {})
            except Exception as exc:  # noqa: BLE001 - cualquier falla pasa al siguiente candidato
                self.usage.record_ai(role, c.spec.model, 0, 0, 0.0, False, tier=c.tier, provider=c.name)
                rate = _is_rate_limit(exc)
                self._paused[c.name] = self._now() + (self.config.cooldown_seconds if rate
                                                      else self.config.error_cooldown_seconds)
                self._turn[c.tier] += 1
                continue
            u = data.get("usage") or {}
            tin, tout = int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))
            cost = tin / 1e6 * c.spec.usd_per_million_in + tout / 1e6 * c.spec.usd_per_million_out
            self.usage.record_ai(role, c.spec.model, tin, tout, cost, True, tier=c.tier, provider=c.name)
            self._turn[c.tier] += 1          # el próximo pedido arranca por el siguiente del escalón
            if out is not None:
                return out
        return None

    def complete(self, role: str, messages: list[dict], *, target: str | None = None, private: bool = False,
                 prefer: str | None = None, max_tokens: int = 300, temperature: float = 0.2) -> str | None:
        """Texto de la IA o None (sin modelo, todos fallaron, o el plan pasó su tope de mensajes)."""
        def accept(msg: dict) -> str | None:
            return (msg.get("content") or "").strip() or None

        return self._send(role, messages, accept, target=target, private=private, prefer=prefer,
                          body={"max_tokens": max_tokens, "temperature": temperature})

    async def acomplete(self, role: str, messages: list[dict], **kw: Any) -> str | None:
        """Lo mismo, desde código async (corre en un hilo para no trabar el loop)."""
        return await asyncio.to_thread(self.complete, role, messages, **kw)

    def chat(self, role: str, messages: list[dict], *, tools: list[dict] | None = None, target: str | None = None,
             private: bool = False, prefer: str | None = None, max_tokens: int = 1200,
             temperature: float = 0.1) -> dict | None:
        """Una vuelta de chat con tools (formato OpenAI). Devuelve {"content", "tool_calls"} o None.

        Un mensaje vacío (sin texto ni tool_calls) cuenta como falla de ese proveedor y se prueba el siguiente."""
        def accept(msg: dict) -> dict | None:
            calls = [tc for tc in (msg.get("tool_calls") or []) if isinstance(tc, dict)]
            content = msg.get("content") or ""
            if not calls and not content.strip():
                return None
            return {"content": content, "tool_calls": calls}

        body: dict[str, Any] = {"max_tokens": max_tokens, "temperature": temperature}
        if tools:
            body |= {"tools": tools, "tool_choice": "auto"}
        return self._send(role, messages, accept, target=target, private=private, prefer=prefer, body=body)

    async def achat(self, role: str, messages: list[dict], **kw: Any) -> dict | None:
        return await asyncio.to_thread(self.chat, role, messages, **kw)
