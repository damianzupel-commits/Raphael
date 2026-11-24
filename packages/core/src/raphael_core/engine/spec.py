"""El "brigade spec": lo común de una brigada declarado como DATO, para que lo ejecute el motor (`chief.py`).

Portado de JarvisRemote (`brigades/spec.py`). Declara:
  - identidad y propósito (id, nombre, para qué existe) y el prompt del jefe (su especialización);
  - los EFÍMEROS (`HelperSpec`): cada uno con su modo, su prompt y su caja de tools (menor privilegio);
  - las REGLAS DE RUTEO que acotan en cuáles delegar (toda brigada tiene al menos un efímero: el jefe nunca
    responde directo; decisión de Damián del 16 nov 2026);
  - las skills que expone, la escena de validación y lo que vigila el watchdog.

Cambio respecto de JarvisRemote: el MODELO de cada rol ya no va en el spec. Lo resuelve la pasarela de modelos por rol
y por id (`jefe.<brigada>`, `efimero.<ayudante>`), con los tres escalones. `private=True` = solo modelos que corren
en la PC (antes: "client local").
Liviano: solo dataclasses y biblioteca estándar.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

Prompt = "str | Callable[[], str]"


def _prompt(p: str | Callable[[], str]) -> str:
    return p() if callable(p) else p


# --- efímeros y ruteo ---------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class HelperSpec:
    """Un efímero del jefe: nace con el pedido y muere con la respuesta."""

    mode: str
    id: str
    description: str
    prompt: str | Callable[[], str] = ""
    tools: frozenset[str] = frozenset()   # su caja: el techo de lo que puede usar
    private: bool = False                 # solo modelos locales (lo que maneja datos personales)
    max_steps: int = 12                   # rondas modelo -> tool -> modelo como mucho

    def system_prompt(self) -> str:
        return _prompt(self.prompt)


@dataclass(frozen=True)
class RouteRule:
    """Si `pattern` (regex, sin distinguir mayúsculas) aparece en el pedido, se delega en `mode`."""

    mode: str
    pattern: str

    def matches(self, text: str) -> bool:
        return bool(re.search(self.pattern, text, re.IGNORECASE))


@dataclass(frozen=True)
class Routing:
    """Ruteo determinístico a propósito (sin modelo, sin costo, auditable): las reglas se evalúan EN ORDEN, gana la
    primera que matchea; si ninguna, `default`. El orden ES la prioridad (en Investigación, 'forense' va primero)."""

    rules: tuple[RouteRule, ...]
    default: str

    def classify(self, message: str) -> str:
        text = unicodedata.normalize("NFKC", message or "")
        for r in self.rules:
            if r.matches(text):
                return r.mode
        return self.default

    def candidates(self, message: str) -> tuple[str, ...]:
        """TODOS los modos cuyas reglas matchean, en orden de prioridad y sin repetir (vacío = va al `default`).
        Es la red de seguridad de la planificación: el modelo del jefe solo elige ENTRE estos, nunca agrega otro."""
        text = unicodedata.normalize("NFKC", message or "")
        out: list[str] = []
        for r in self.rules:
            if r.mode not in out and r.matches(text):
                out.append(r.mode)
        return tuple(out)


@dataclass(frozen=True)
class SkillSpec:
    id: str
    description: str
    tools: frozenset[str] = frozenset()


# --- escena de validación y vigilancia -------------------------------------------------------------------------------------
@dataclass(frozen=True)
class StepSpec:
    """Un paso de la validación. `runner` es 'modulo:funcion' (async def f(ctx) -> Step)."""

    id: str
    label: str
    runner: str
    gate: bool = False
    needs: tuple[str, ...] = ()
    prereq: str | None = None


@dataclass(frozen=True)
class Criterion:
    description: str
    pass_when: str = "all_steps"


@dataclass(frozen=True)
class ValidationSpec:
    title: str
    scene: dict[str, Any]
    steps: tuple[StepSpec, ...]
    criterion: Criterion
    baseline_keys: tuple[str, ...]
    facts: dict[str, Any] = field(default_factory=dict)
    prerequisites: tuple[str, ...] = ("local_stack",)
    isolate_settings: dict[str, str] = field(default_factory=dict)
    isolate_env: dict[str, str] = field(default_factory=dict)
    base_metrics: str | None = None
    banner: str | None = None
    teardown: str | None = None
    word_tolerance: float = 0.5

    @property
    def scene_hash(self) -> str:
        """Huella de la escena: si cambia algo de `scene`, el baseline deja de ser comparable."""
        raw = json.dumps(list(self.scene.values()), ensure_ascii=False)
        return hashlib.sha1(raw.encode()).hexdigest()[:12]


@dataclass(frozen=True)
class WatchSpec:
    """Cómo debería comportarse una corrida, para que el watchdog del orquestador la vigile. Todo opcional."""

    max_seconds: float | None = None
    stall_seconds: float | None = None
    max_repeats: int | None = None
    max_errors: int | None = None


# --- el spec de la brigada ------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class BrigadeSpec:
    id: str
    name: str
    purpose: str
    prompt: str | Callable[[], str]
    helpers: tuple[HelperSpec, ...] = ()
    routing: Routing | None = None
    tools: frozenset[str] | None = None        # techo del jefe; None = la unión de las de sus efímeros
    private: bool = False                      # jefe y efímeros solo con modelos locales
    skills: tuple[SkillSpec, ...] = ()
    helper_timeout: float | None = None        # segundos por efímero (None = el del motor)
    validation: ValidationSpec | None = None
    watch: WatchSpec | None = None

    def __post_init__(self) -> None:
        if not self.helpers:
            raise ValueError(f"brigada {self.id}: necesita al menos un efímero (el jefe coordina y sintetiza; "
                             "no hace el trabajo)")
        if self.routing is None:
            raise ValueError(f"brigada {self.id}: tiene efímeros pero no reglas de ruteo")
        modes = [h.mode for h in self.helpers]
        if len(modes) != len(set(modes)):
            raise ValueError(f"brigada {self.id}: modos de efímero repetidos")
        targets = {r.mode for r in self.routing.rules} | {self.routing.default}
        if not targets <= set(modes):
            raise ValueError(f"brigada {self.id}: el ruteo apunta a modos sin efímero: {sorted(targets - set(modes))}")
        if self.tools is not None:
            extra = set().union(*(h.tools for h in self.helpers)) - set(self.tools)
            if extra:
                raise ValueError(f"brigada {self.id}: efímeros con tools fuera del techo: {sorted(extra)}")

    def helper(self, mode: str) -> HelperSpec:
        for h in self.helpers:
            if h.mode == mode:
                return h
        raise KeyError(mode)

    def tool_names(self) -> frozenset[str]:
        """Techo de privilegio. Sin `tools` explícitas = la unión de sus efímeros."""
        if self.tools is None:
            out: frozenset[str] = frozenset()
            for h in self.helpers:
                out |= h.tools
            return out
        return self.tools

    def system_prompt(self) -> str:
        return _prompt(self.prompt)

    def describe_skills(self) -> list[dict]:
        """Skills para las vistas: una por efímero (toda brigada delega)."""
        return [{"mode": h.mode, "helper": h.id, "description": h.description, "ephemeral": True,
                 "tools": sorted(h.tools), "private": h.private or self.private} for h in self.helpers]
