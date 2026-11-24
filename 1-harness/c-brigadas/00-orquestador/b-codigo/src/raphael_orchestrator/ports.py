"""El puente entre el orquestador y el harness: arma los modelos de sus roles y los ajustes de la voz desde el contexto.

Todo lo que el orquestador usa del harness pasa por `OrchestratorContext` / `OwnerContext` (raphael_core 2.1). Acá no
hay proveedores, claves ni URLs: solo roles.
"""

from __future__ import annotations

from typing import Any

from .config import OrchestratorConfig
from .voice import LLM, VoiceSettings


def role_llm(ctx: Any, role: str, *, private: bool = False, temperature: float = 0.2,
             max_tokens: int | None = None) -> LLM:
    """El modelo de un rol del orquestador como función async. Devuelve None si no hay modelo (quien llama sigue con
    reglas o plantilla). `private=True`: solo modelos locales (lo pide quien tiene datos de una brigada privada)."""
    kw: dict[str, Any] = {"temperature": temperature}
    if max_tokens:
        kw["max_tokens"] = max_tokens

    async def call(messages: list[dict]) -> str | None:
        return await ctx.aai(role, messages, private=private, **kw)

    return call


def voice_llm(ctx: Any, cfg: OrchestratorConfig, *, private: bool = False) -> LLM:
    return role_llm(ctx, "voz", private=private, temperature=cfg.voice.temperature,
                    max_tokens=cfg.voice.max_tokens or 800)


def routing_llm(ctx: Any, cfg: OrchestratorConfig) -> LLM | None:
    """El clasificador del ruteo, o None si está apagado. `classifier_cloud=False`: solo modelos locales."""
    if not cfg.routing.classifier:
        return None
    return role_llm(ctx, "ruteo", private=not cfg.routing.classifier_cloud, temperature=0.0, max_tokens=256)


def voice_settings(ctx: Any, cfg: OrchestratorConfig, *, directives: str | None = None) -> VoiceSettings:
    """Los ajustes de la voz: la persona y las directrices de la config (o las vivas, si se pasan) y los nombres de la
    identidad de la instalación."""
    ident = getattr(ctx, "identity", None)
    return VoiceSettings(persona=cfg.voice.persona, user=getattr(ident, "user", "") or "",
                         assistant=getattr(ident, "assistant", "") or "Raphael",
                         directives=cfg.voice.directives if directives is None else directives,
                         retries=cfg.voice.retries, chat_max_words=cfg.voice.chat_max_words)


def any_private(ctx: Any, brigades: list[str] | tuple[str, ...]) -> bool:
    """¿Alguna de estas brigadas es privada? Entonces mando y voz trabajan solo con modelos locales."""
    return any(ctx.is_private(b) for b in brigades)
