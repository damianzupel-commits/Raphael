"""Model routing por tier (spec §6; esquema de 5 tiers, Damian 2026-10-06).

Cada agente/estación declara su `tier`; el harness le asigna el modelo correcto:
  0 = sin modelo (determinista) · 1 = local (jobs programados) · 2 = free/operativo ·
  3 = Sonnet (pesado) · 4 = especial (el más potente, hoy Opus).

El resolver soporta FALLBACK: si el modelo primario de un tier no está disponible
(proveedor caído, free rate-limiteado), cae al siguiente de la lista. La
"disponibilidad" se inyecta como callable para testear sin tocar proveedores reales.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from ..config import settings

# Mapa por defecto tier -> lista de modelos (primario primero, luego fallbacks).
# Diseño de 5 tiers (Damian 2026-10-06). El clasificador de endpoints
# (model_registry.endpoint_for_model) resuelve el endpoint de cada nombre: los
# slugs con "/" van a OpenRouter, los locales al Ollama local.
#   0 = SIN MODELO (determinista: cómputo/reglas/gates).
#   1 = LOCAL (jarvis-text-v2): tareas programadas que corren solas cada tanto
#       (consolidación/"sueño", destilado de memoria). Gratis, privado, puede ser
#       lento porque va de fondo. SIN fallback cloud a propósito: estos jobs tocan el
#       vault personal, así que si el local está caído, el job espera -- no manda data afuera.
#   2 = BARATO/OPERATIVO: modelos FREE rotativos de OpenRouter, para lo simple
#       (navegador, buscar archivos, orquestar tools que no necesitan cabeza). SOLO
#       contenido no sensible (ver settings.tier2_free_models).
#   3 = PESADO -> Sonnet 5.5 (razonamiento de verdad).
#   4 = ESPECIAL -> el modelo más potente que haya (hoy Opus 5.5). Lo más duro.
# Cada lista es primario→fallbacks: si el primero falla, se cae al siguiente.
_FREE = [m.strip() for m in str(settings.tier2_free_models).split(",") if m.strip()]
DEFAULT_TIER_MODELS: dict[int, list[str]] = {
    0: [],
    1: ["jarvis-text-v2"],
    2: _FREE or ["openrouter/free"],  # free rotativos; openrouter/free = auto-router de respaldo
    3: ["anthropic/claude-sonnet-5.5", "anthropic/claude-opus-5.5"],
    4: ["anthropic/claude-opus-5.5", "anthropic/claude-sonnet-5.5"],
}


class NoModelForTier(RuntimeError):
    """Ningún modelo disponible para el tier pedido (todos los fallbacks caídos)."""


def effective_tier(tier: int) -> int:
    """Tier real después del modo prueba. En modo prueba free-only, los tiers pagos
    (3 Sonnet / 4 Opus) caen a free (tier 2) para probar sin gastar crédito; 0/1/2 no se
    tocan (ya son gratis). Centralizado acá (2026-10-11) para que el resolver de modelo y
    el de endpoint coincidan: si en prueba usamos un modelo free, el endpoint también debe
    ser el free, nunca la API paga del tier 4."""
    from .. import testmode

    if testmode.is_on() and tier > 2:
        return 2
    return tier


def _tier_model_override(tier: int) -> str | None:
    """Modelo fijado a mano para este tier desde la config amigable (TIER{n}_MODEL).
    Vacío = usar la lista de DEFAULT_TIER_MODELS (comportamiento de siempre)."""
    val = str(getattr(settings, f"tier{tier}_model", "") or "").strip()
    return val or None


def resolve_model(
    tier: int,
    tier_models: dict[int, list[str]] | None = None,
    is_available: Callable[[str], bool] | None = None,
) -> str | None:
    """Devuelve el modelo a usar para `tier`, o None si el tier es determinista.

    Recorre la lista del tier (primario -> fallbacks) y devuelve el primero
    disponible. Si ninguno está disponible y el tier requiere modelo, levanta
    NoModelForTier (mejor fallar claro que correr con un cliente roto)."""
    tier = effective_tier(tier)
    # Override explícito del usuario (config amigable): gana sobre la lista del tier.
    # No se aplica en tier 2 de modo prueba (no existe TIER2_MODEL) -> sigue rotando free.
    override = _tier_model_override(tier)
    if override:
        return override
    models: Sequence[str] = (tier_models or DEFAULT_TIER_MODELS).get(tier, [])
    if not models:
        return None  # tier 0: sin modelo, a propósito
    check = is_available or (lambda _m: True)
    for model in models:
        if check(model):
            return model
    raise NoModelForTier(
        f"ningún modelo disponible para el tier {tier} (probé: {list(models)})"
    )
