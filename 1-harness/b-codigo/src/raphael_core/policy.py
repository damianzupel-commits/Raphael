"""Policy Engine: decide si una acción se ejecuta sola, espera aprobación o la resuelve una persona.

Decidido el 21 nov 2026: sin pisos fijos en el código y autonomía ROTATIVA por confianza progresiva.

Nivel de partida (gana el más específico, no el más estricto):
    1. `autonomy` de la instalación por "brigada.accion"
    2. `autonomy` de la instalación por "accion"
    3. el nivel que declara el manifiesto de la brigada (obligatorio)
    4. acción no declarada: `aprobacion`
Dejar a mano en `automatico` una acción con gasto o irreversible exige `confirmed_by`; si falta, esa regla
se ignora con un aviso y se sigue con la capa siguiente.

Perfil global (`installation.profile`, deslizador `RAPHAEL_AUTONOMIA`): cauteloso apaga la confianza progresiva y pide
aprobación aun donde el manifiesto dice automático; confiado la baja con la mitad de aprobaciones. No toca la regla general:
lo externo, lo que gasta y lo irreversible no baja solo a automático en ningún perfil.

Confianza progresiva (por brigada y acción, guardada en el espacio `_trust`):
    - aprobar SIN cambios suma 1; a las `approvals_to_step_down` seguidas baja un escalón;
    - rechazar, aprobar CON cambios o corregir una acción automática sube un escalón;
    - una acción con gasto o irreversible NUNCA baja sola a `automatico`: se devuelve "propose" para que
      el harness le pregunte a la persona; solo baja si ella lo confirma;
    - lo `humano` no baja solo salvo `step_down_from_human`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .contract import Level, Origin
from .installation import Installation
from .manifest import ActionSpec
from .store import Space

_ORDER = (Level.AUTO, Level.APPROVAL, Level.HUMAN)
Hook = Callable[..., None]   # (qué, **datos) -> auditoría


@dataclass(frozen=True)
class Decision:
    level: Level          # el nivel con el que se trata la acción ahora
    base: Level           # el de partida (antes de la confianza)
    source: str           # de dónde salió el nivel de partida
    trust_steps: int      # escalones movidos por la confianza (negativo = bajó, positivo = subió)
    risky: bool           # gasta plata o es irreversible
    notes: tuple[str, ...] = ()

    def explain(self) -> str:
        mov = "" if not self.trust_steps else (
            f"; la confianza la {'bajó' if self.trust_steps < 0 else 'subió'} {abs(self.trust_steps)} escalón"
            f"{'es' if abs(self.trust_steps) > 1 else ''}")
        return f"{self.level.value} (partida: {self.base.value} por {self.source}{mov})"


class PolicyEngine:
    TRUST = "levels"

    def __init__(self, installation: Installation, trust_space: Space, on_change: Hook | None = None) -> None:
        self._inst = installation
        self._trust = trust_space
        self._actions: dict[str, dict[str, ActionSpec]] = {}
        self._on_change = on_change or (lambda *a, **k: None)

    # --- registro de las acciones que declara cada brigada ------------------------------------------------------------
    def register(self, brigade: str, actions: dict[str, ActionSpec]) -> list[str]:
        """Registra el manifiesto. Devuelve avisos de la config de autonomía que no se van a aplicar."""
        self._actions[brigade] = dict(actions)
        return [n for a in actions for n in self.decide(brigade, a).notes]

    def declare(self, brigade: str, action: str, spec: ActionSpec) -> None:
        """Agrega UNA acción a lo registrado (p. ej. una tool compartida la primera vez que la usa una brigada)."""
        self._actions.setdefault(brigade, {})[action] = spec

    def unregister(self, brigade: str) -> None:
        self._actions.pop(brigade, None)

    def spec(self, brigade: str, action: str) -> ActionSpec | None:
        return self._actions.get(brigade, {}).get(action)

    # --- decisión ------------------------------------------------------------------------------------------------------
    def _base(self, brigade: str, action: str) -> tuple[Level, str, list[str]]:
        spec = self.spec(brigade, action)
        risky = bool(spec and spec.risky)
        notes: list[str] = []
        for key, source in ((f"{brigade}.{action}", "la instalación (brigada.acción)"),
                            (action, "la instalación (acción)")):
            rule = self._inst.autonomy.get(key)
            if rule is None:
                continue
            if rule.level is Level.AUTO and risky and not rule.confirmed_by:
                notes.append(f"'{key}': automático sin confirmar en una acción con gasto o irreversible; se ignora")
                continue
            return rule.level, source, notes
        if spec is not None:
            if spec.level is Level.AUTO and self._inst.profile == "cauteloso":
                return Level.APPROVAL, "el manifiesto (perfil cauteloso)", notes
            return spec.level, "el manifiesto", notes
        return Level.APPROVAL, "acción no declarada", notes

    def _needed(self) -> int:
        """Aprobaciones seguidas sin cambios para bajar un escalón: las de la instalación; en confiado, la mitad (mínimo 2)."""
        n = self._inst.trust.approvals_to_step_down
        return max(2, n // 2) if self._inst.profile == "confiado" and n > 2 else n

    def _state(self, brigade: str, action: str) -> dict:
        return self._trust.get(self.TRUST, f"{brigade}.{action}") or \
            {"brigade": brigade, "action": action, "streak": 0, "steps": 0, "proposed": False}

    def _save(self, st: dict) -> None:
        self._trust.put(self.TRUST, f"{st['brigade']}.{st['action']}", st)

    def decide(self, brigade: str, action: str, origin: Origin = Origin.SYSTEM) -> Decision:
        base, source, notes = self._base(brigade, action)
        spec = self.spec(brigade, action)
        risky = bool(spec and spec.risky)
        steps = self._state(brigade, action)["steps"] if self._inst.trust.enabled else 0
        if self._inst.profile == "cauteloso":
            steps = max(steps, 0)            # cauteloso: la confianza nunca baja un nivel (sí puede subirlo)
        level = _ORDER[max(0, min(len(_ORDER) - 1, base.weight + steps))]
        if origin is Origin.THIRD_PARTY and self._inst.trust.third_party_step_up and steps >= 0 and level is not Level.HUMAN:
            level = level.higher()
            notes.append("disparada por contenido de terceros: sube un escalón")
        return Decision(level, base, source, steps, risky, tuple(notes))

    def level(self, brigade: str, action: str, origin: Origin = Origin.SYSTEM) -> Level:
        return self.decide(brigade, action, origin).level

    # --- confianza progresiva ------------------------------------------------------------------------------------------
    def record_approval(self, brigade: str, action: str, changed: bool = False, who: str = "") -> str | None:
        """La persona aprobó. Devuelve "lowered", "propose" (hay que preguntarle) o None."""
        if not self._inst.trust.enabled or self._inst.profile == "cauteloso":
            return None
        if changed:
            return self.record_correction(brigade, action, who=who, why="aprobó con cambios")
        d = self.decide(brigade, action)
        if d.level is Level.AUTO or (d.level is Level.HUMAN and not self._inst.trust.step_down_from_human):
            return None
        st = self._state(brigade, action)
        st["streak"] += 1
        if st["streak"] < self._needed():
            self._save(st)
            return None
        if d.level.lower() is Level.AUTO and d.risky:
            first = not st["proposed"]
            st["proposed"] = True
            self._save(st)
            return "propose" if first else None
        st.update(steps=st["steps"] - 1, streak=0, proposed=False)
        self._save(st)
        self._on_change("confianza_baja", who=who or "confianza", brigada=brigade, accion=action,
                        nivel=self.level(brigade, action).value,
                        why=f"{self._needed()} aprobaciones seguidas sin cambios")
        return "lowered"

    def record_correction(self, brigade: str, action: str, who: str = "", why: str = "") -> str | None:
        """Rechazo, aprobación con cambios o una acción automática que la persona corrigió: sube un escalón."""
        if not self._inst.trust.enabled:
            return None
        base, _, _ = self._base(brigade, action)
        st = self._state(brigade, action)
        before = self.level(brigade, action)
        st.update(steps=min(st["steps"] + 1, len(_ORDER) - 1 - base.weight), streak=0, proposed=False)
        self._save(st)
        after = self.level(brigade, action)
        if after is before:
            return None
        self._on_change("confianza_sube", who=who or "confianza", brigada=brigade, accion=action, nivel=after.value,
                        why=why or "corrección")
        return "raised"

    def confirm_step_down(self, brigade: str, action: str, who: str) -> Level:
        """La persona confirmó la propuesta: baja un escalón aunque gaste o sea irreversible."""
        st = self._state(brigade, action)
        before = self.level(brigade, action)
        if before is not Level.AUTO:
            st["steps"] -= 1
        st.update(streak=0, proposed=False)
        self._save(st)
        after = self.level(brigade, action)
        self._on_change("confianza_baja", who=who, brigada=brigade, accion=action, nivel=after.value,
                        why="la persona confirmó la propuesta")
        return after

    def decline_step_down(self, brigade: str, action: str, who: str) -> None:
        st = self._state(brigade, action)
        st.update(streak=0, proposed=False)
        self._save(st)
        self._on_change("confianza_propuesta_rechazada", who=who, brigada=brigade, accion=action)

    def reset(self, brigade: str, action: str, who: str) -> None:
        self._trust.delete(self.TRUST, f"{brigade}.{action}")
        self._on_change("confianza_reseteada", who=who, brigada=brigade, accion=action)

    # --- vistas --------------------------------------------------------------------------------------------------------
    def table(self) -> list[dict[str, Any]]:
        """Todas las acciones declaradas, con su nivel actual y el porqué (para el panel y el estado)."""
        out = []
        for brigade, actions in sorted(self._actions.items()):
            for action in sorted(actions):
                d = self.decide(brigade, action)
                st = self._state(brigade, action)
                out.append({"brigade": brigade, "action": action, "level": d.level.value, "base": d.base.value,
                            "source": d.source, "trust_steps": d.trust_steps, "streak": st["streak"],
                            "proposed": st["proposed"], "risky": d.risky, "why": d.explain()})
        return out
