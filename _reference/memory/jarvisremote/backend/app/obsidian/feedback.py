"""Crédito por resultado -- el lazo cerrado de aprendizaje (Etapa B, ver
`vision/ETAPAS-BCD-diseno.md`; principio #5, asignación de crédito).

Cierra el lazo *percibir → recordar → actuar → **aprender del resultado***. Al terminar
una tarea se deriva un `reward` de las señales disponibles (tests, error, corrección,
feedback explícito), y se acredita a las notas que se usaron (las del rastro de
activación de ese turno):
  - reward POSITIVO -> refuerzo (LTP): sube fuerza + aristas Hebbianas.
  - reward NEGATIVO -> **marcado aversivo** (LTD): valencia negativa en las notas +
    debilita la vía que llevó al error -- "no vuelvas por ahí". Con PISOS (homeostasis):
    asocia negativamente SIN suprimir ni desestabilizar. No es castigo que rompe, es la
    contraparte aversiva del refuerzo, igual que en el cerebro.

Reward por SITUACIÓN (decisión de Damian 2026-10-06): auto donde la señal es objetiva
(tests, fix verificado), explícito donde es subjetiva (conversación/consejo).

PROCESADOR: tier 0 -- reusa [[strength]] y [[hebbian]], sin modelo.
"""

from __future__ import annotations

from . import hebbian, strength

# Situaciones donde las señales IMPLÍCITAS (tests/error/corrección) son confiables y el
# crédito puede ser automático. En las demás (conversación/consejo) solo cuenta el
# feedback explícito -- la señal implícita es ruidosa.
_IMPLICIT_TRUSTED = {"codigo", "auditoria", "recall", "accion_externa", "ingesta"}


def reward_from_signals(signals: dict, situacion: str = "recall") -> float:
    """Combina las señales en un reward en [-1, 2]. `signals`: {tests_ok: bool|None,
    had_error: bool, corrected: bool, explicit: float|None}. El feedback explícito pesa
    fuerte; las implícitas solo cuentan en situaciones objetivas. PURA."""
    r = 0.0
    explicit = signals.get("explicit")
    if explicit is not None:
        r += float(explicit)
    if situacion in _IMPLICIT_TRUSTED:
        if signals.get("tests_ok") is True:
            r += 1.0
        elif signals.get("tests_ok") is False:
            r -= 1.0
        if signals.get("had_error"):
            r -= 0.5
        if signals.get("corrected"):
            r -= 0.5
    return max(-1.0, min(2.0, round(r, 3)))


def credit(note_ids: list[str], reward: float = 1.0) -> dict:
    """Aplica el crédito. reward>0 refuerza (LTP); reward<0 marca aversivo (LTD, con
    pisos); reward==0 no hace nada (el olvido natural se encarga)."""
    ids = [n for n in dict.fromkeys(note_ids) if n]
    if not ids or reward == 0:
        return {"tipo": "nada", "notas": 0, "aristas": 0, "reward": reward}
    if reward > 0:
        f = min(2.0, float(reward))
        return {
            "tipo": "refuerzo",
            "notas": strength.bump(ids, increment=0.5 * f),
            "aristas": hebbian.reforzar(ids, amount=0.5 * f),
            "reward": round(float(reward), 3),
        }
    mag = min(1.0, -float(reward))
    return {
        "tipo": "aversion",
        "notas": strength.bump(ids, increment=-0.5 * mag),  # valencia negativa (floored)
        "aristas": hebbian.debilitar(ids, amount=0.4 * mag),  # LTD en la vía (floored)
        "reward": round(float(reward), 3),
    }


def outcome(note_ids: list[str], signals: dict, situacion: str = "recall") -> dict:
    """Cierra una tarea: deriva el reward de las señales y lo acredita a las notas
    usadas. Es la acción que cierra el lazo."""
    reward = reward_from_signals(signals, situacion)
    out = credit(note_ids, reward)
    out["situacion"] = situacion
    return out
