"""Metacognición / confianza -- el "feeling of knowing" de Raphael (Fase 9 de la
estructura informacional, ver docs/SPEC-raphael-predictivo.md §principios 9+).

La confianza NO la emite un modelo: emerge del propio PROCESO de recuperación, igual
que en el cerebro el "sé que lo sé" es un subproducto de la dinámica de memoria, no un
juicio aparte. Señales (todas ya disponibles tras el spreading):
  - qué tan fuerte se activó una nota,
  - si fue un hit semántico DIRECTO (semilla) o una asociación de rebote,
  - su fuerza de recuperación (usada antes = más confiable),
  - para el recall entero: cuán CLARO fue el ganador (margen), qué tan bien matcheó
    algo (mejor semilla) y cuántas notas lo corroboran.

Con eso Raphael sabe cuándo CONFIAR en lo que trajo y cuándo VERIFICAR contra el crudo
firmado (provenance) o escalar -- el control metacognitivo. Más adelante, LAYA puede
entrar como estimador CALIBRADO encima de este piso estructural (ver
docs/EXPERIMENTO-JEV-motor-de-decisiones.md), validando su calibración con datos reales.

PROCESADOR: tier 0 -- cómputo PURO, sin modelo. Todo testeable.
"""

from __future__ import annotations


def note_confidence(score: float, max_score: float, is_seed: bool, fuerza: float = 1.0) -> float:
    """Confianza en UNA nota recuperada (0..1). Un hit semántico directo (semilla) vale
    más que una asociación de rebote; la fuerza de recuperación modula. Puro."""
    base = (score / max_score) if max_score else 0.0
    base *= 1.0 if is_seed else 0.75
    base *= min(1.2, max(0.6, fuerza))
    return round(min(1.0, base), 3)


def overall_confidence(scores: list[float], seed_strengths: list[float]) -> float:
    """Confianza en el recall ENTERO (0..1) -- el feeling-of-knowing. Combina:
    - mejor semilla (¿matcheó algo de verdad?) 45%,
    - margen del ganador sobre el segundo (¿hay un ganador claro o es parejo/ambiguo?) 35%,
    - corroboración (¿cuántas notas lo sostienen?) 20%. Puro."""
    if not scores:
        return 0.0
    top = scores[0] or 1e-9
    second = scores[1] if len(scores) > 1 else 0.0
    margin = max(0.0, (top - second) / top)
    best_seed = max(seed_strengths) if seed_strengths else 0.0
    corrob = min(1.0, len([s for s in scores if s >= 0.3 * top]) / 5.0)
    conf = 0.45 * min(1.0, best_seed) + 0.35 * margin + 0.20 * corrob
    return round(min(1.0, conf), 3)


def recommendation(conf: float, high: float = 0.6, low: float = 0.35) -> str:
    """Traduce la confianza a una acción metacognitiva:
    - 'alta'  -> confiá en la reconstrucción.
    - 'media' -> usable, pero con pinzas.
    - 'baja'  -> NO confíes: volvé al crudo firmado (provenance) o escalá al que razona."""
    if conf >= high:
        return "alta"
    if conf <= low:
        return "baja"
    return "media"
