"""Router de dificultad del chat (2026-10-06, pedido de Damian).

Visión: Raphael como asistente diario (free/local para lo simple) que ESCALA a
Claude (tier 3 Sonnet / tier 4 Opus) solo cuando la tarea supera lo que un modelo
barato hace bien. Este módulo clasifica el mensaje del usuario en un TIER de
dificultad; el harness después resuelve el modelo de ese tier.

PURO y determinista (tier 0): sin modelo, sin red, 100% testeable. Clasifica por
heurística (palabras clave de complejidad + largo del mensaje), no por LLM, para
no gastar un modelo solo para decidir qué modelo usar.

Gating (pedido de Damian "construilo pero ahora no lo usaremos"): se aplica SOLO
si settings.difficulty_router_enabled está en True (default OFF). Además, en modo
prueba NO aplica -- ahí todo cae a free igual. Así queda construido y con su
interruptor, listo para cuando lo quiera prender.

Tiers (esquema de 5, ver harness/routing.py):
  2 = simple/operativo (free rotativo) -- el default.
  3 = pesado -> Sonnet 5.5 (razonamiento de verdad).
  4 = lo más difícil -> Opus.
"""

from __future__ import annotations

import unicodedata


def _norm(s: str) -> str:
    """Minúsculas sin acentos, para que 'auditá'/'audita'/'AUDITÁ' matcheen igual."""
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# Señales de tarea PESADA (-> tier 3). Guardadas ya normalizadas (sin acentos).
_HARD = (
    "audita", "auditar", "auditoria", "pentest", "vulnerabilidad", "exploit",
    "refactor", "arquitectura", "disena", "disenar", "diseno de",
    "analiza a fondo", "analisis profundo", "en profundidad", "a fondo",
    "optimiz", "debugge", "depurar", "demostr", "proba que", "probar que",
    "explica por que", "explica como funciona", "razona", "razonamiento",
    "plan detallado", "estrategia", "escribi el codigo", "implementa",
    "code review", "revisa el codigo", "compara en detalle", "evalua a fondo",
)
# Señales de tarea MUY difícil (-> tier 4).
_VERY_HARD = (
    "demostracion formal", "prueba matematica", "prueba formal", "teorema",
    "lo mas dificil", "usa el mejor modelo", "maxima capacidad", "el modelo mas potente",
    "problema muy complejo", "muy dificil",
)
# Un mensaje MUY largo suele ser una tarea pesada aunque no tenga keywords.
_LONG_CHARS = 1200


def classify(text: str, base_tier: int = 2) -> int:
    """Devuelve el tier sugerido para `text`. `base_tier` es el piso (lo simple)."""
    t = _norm(text)
    if not t.strip():
        return base_tier
    if any(k in t for k in _VERY_HARD):
        return 4
    if any(k in t for k in _HARD) or len(t) >= _LONG_CHARS:
        return 3
    return base_tier
