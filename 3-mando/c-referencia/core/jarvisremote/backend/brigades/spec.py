"""Esquema del "brigade spec": lo estructuralmente común de una brigada, declarado como DATO.

Una brigada deja de ser una clase escrita a mano y pasa a ser un `BrigadeSpec` que el motor
genérico (`brigades/engine.py`) ejecuta. El spec declara:

  - identidad y propósito (id, nombre, para qué existe),
  - el jefe (prompt, tools = techo de privilegio, dónde corre su modelo, persistencia),
  - los AYUDANTES efímeros (cada uno con su prompt, sus tools y su modelo) y las REGLAS DE RUTEO
    que acotan en cuáles delegar un pedido (toda brigada tiene al menos uno: el jefe nunca responde directo),
  - las skills que expone (para la vista de la Suite),
  - la ESCENA DE VALIDACIÓN: datos semilla, pasos, criterio de éxito, prerrequisitos y aislamiento.

Es solo esquema: sin imports pesados (las tools, el LLM y el vault se resuelven perezosamente
desde los callables y los nombres con puntos), así que importar un spec es barato.
Doc del método: docs/PLAYBOOK-brigadas.md. Decisión de diseño: Etapa 1 del "método de brigadas".
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:  # liviano: importar un spec NO debe cargar el registro de tools (ver slim_tools)
    from .chief import ChiefConfig


# --- ayudantes y ruteo --------------------------------------------------------
@dataclass(frozen=True)
class AyudanteSpec:
    """Un ayudante efímero del jefe: nace con el pedido y muere con la respuesta (blueprint §2)."""

    modo: str
    id: str
    descripcion: str
    donde: str  # dónde corre su modelo (informativo, para la vista de skills)
    config: Callable[[], ChiefConfig]
    client_model: Callable[[], tuple]  # el modelo DECLARADO del ayudante (ej. el BYOM de Scout); ver `resolve_client_model`
    tool_names: Callable[[], frozenset[str]]

    def resolve_client_model(self) -> tuple:
        """(cliente, modelo) EFECTIVO del ayudante: su override por config (`AYUDANTE_<ID>_LLM_*`) y, si no hay, el
        declarado. Cada rol tiene su propio LLM, siempre intercambiable sin tocar código (brigades/config.py)."""
        from .config import resolve_role_model

        return resolve_role_model("ayudante", helper_id=self.id, declarado=self.client_model)


@dataclass(frozen=True)
class RouteRule:
    """Si `patron` (regex, sin distinguir mayúsculas) aparece en el pedido, se delega en `modo`."""

    modo: str
    patron: str

    def matches(self, text: str) -> bool:
        return bool(re.search(self.patron, text, re.IGNORECASE))


@dataclass(frozen=True)
class Routing:
    """Ruteo determinístico a propósito (sin LLM, sin costo, auditable): las reglas se evalúan EN ORDEN,
    gana la primera que matchea; si ninguna matchea, `default`. El orden ES la prioridad: ante una
    señal ambigua gana la regla más arriba (en Investigación, 'forense' va primero por privacidad)."""

    reglas: tuple[RouteRule, ...]
    default: str

    def clasificar(self, message: str) -> str:
        text = unicodedata.normalize("NFKC", message or "")
        for r in self.reglas:
            if r.matches(text):
                return r.modo
        return self.default

    def coincidencias(self, message: str) -> tuple[str, ...]:
        """TODOS los modos cuyas reglas matchean, en orden de prioridad y sin repetir (vacío = ninguna: va al `default`).
        Es la red de seguridad de la planificación del jefe: su LLM solo elige ENTRE estos candidatos, nunca agrega otro."""
        text = unicodedata.normalize("NFKC", message or "")
        out: list[str] = []
        for r in self.reglas:
            if r.modo not in out and r.matches(text):
                out.append(r.modo)
        return tuple(out)


@dataclass(frozen=True)
class SkillSpec:
    """Una capacidad que la brigada expone (para la vista de la Suite)."""

    id: str
    descripcion: str
    tool_names: frozenset[str] = frozenset()


# --- escena de validación -----------------------------------------------------
@dataclass(frozen=True)
class StepSpec:
    """Un paso de la validación. `runner` es 'modulo:funcion' (se resuelve perezosamente): una
    `async def f(ctx) -> Step`. Declarativo = qué pasos hay, en qué orden y de qué dependen."""

    id: str
    label: str            # nombre corto para el RESUMEN
    runner: str
    gate: bool = False    # si este paso no pasa, los siguientes NO corren (ej. sembrar)
    needs: tuple[str, ...] = ()  # claves de ctx.shared que deben existir; si no, el paso "no corrió"
    prereq: str | None = None    # 'modulo:funcion' async -> list[str] de problemas; con problemas => SIN VALIDAR


@dataclass(frozen=True)
class Criterion:
    """Criterio de éxito de la brigada. Hoy una sola regla: PASA si TODOS los pasos pasan y no se
    tocó nada real. Un paso SIN VALIDAR (falta un prerrequisito suyo) no es un fallo, pero deja la
    corrida INCOMPLETA (nunca verde)."""

    descripcion: str
    pass_when: str = "all_steps"


@dataclass(frozen=True)
class ValidationSpec:
    """La escena de validación de una brigada: todo lo que el framework necesita para correrla."""

    title: str
    scene: dict[str, Any]                  # datos FIJOS (siembra, pedidos, directriz); su hash versiona el baseline
    steps: tuple[StepSpec, ...]
    criterion: Criterion
    baseline_keys: tuple[str, ...]
    facts: dict[str, Any] = field(default_factory=dict)       # constantes de la escena que NO entran al hash
    prerequisites: tuple[str, ...] = ("local_stack",)         # ver validation/framework.py:PREREQUISITES
    isolate_settings: dict[str, str] = field(default_factory=dict)  # atributo de settings -> subcarpeta temporal
    isolate_env: dict[str, str] = field(default_factory=dict)       # variable de entorno -> subcarpeta temporal
    base_metrics: str | None = None        # 'modulo:funcion' () -> dict con las métricas base (modelos usados)
    banner: str | None = None              # 'modulo:funcion' (env, metrics) -> list[str] de líneas de cabecera
    teardown: str | None = None            # 'modulo:funcion' async () -> None, siempre al terminar
    word_tolerance: float = 0.5

    @property
    def scene_hash(self) -> str:
        """Huella de la escena: si cambia algo de `scene`, el baseline deja de ser comparable."""
        raw = json.dumps(list(self.scene.values()), ensure_ascii=False)
        return hashlib.sha1(raw.encode()).hexdigest()[:12]


# --- lo que el spec declara para la vigilancia (watchdog del orquestador) -------
@dataclass(frozen=True)
class WatchSpec:
    """Cómo debería comportarse una corrida de la brigada, para que el watchdog del orquestador la vigile contra
    lo que el spec declara. Todo opcional: lo que falta lo pone el default global (env `WATCHDOG_*`).

    max_seconds     duración esperada máxima de un turno (default: el timeout de ayudante de la brigada + margen)
    stall_seconds   cuánto sin NINGÚN evento nuevo en el feed se considera sin progreso (deadlock/colgado)
    max_repeats     cuántas veces la misma llamada idéntica (tool + argumentos) en la ventana cuenta como loop
    max_errors      cuántas tools fallidas seguidas se toleran
    """

    max_seconds: float | None = None
    stall_seconds: float | None = None
    max_repeats: int | None = None
    max_errors: int | None = None


# --- el spec de la brigada ----------------------------------------------------
@dataclass(frozen=True)
class BrigadeSpec:
    id: str
    name: str
    purpose: str
    prompt: "str | Callable[[], str]"
    client: str = "local"                  # tipo de modelo del JEFE: 'local' (tier 1) | 'shared' (modelo compartido de los jefes)
    client_model: "Callable[[], tuple] | None" = None  # modelo DECLARADO del jefe (opcional; gana sobre el default de su tipo)
    tools: "frozenset[str] | Callable[[], frozenset[str]] | None" = None  # None = unión de las de sus ayudantes
    vault_path: str | None = None
    persistent: bool = True
    ayudantes: tuple[AyudanteSpec, ...] = ()
    routing: Routing | None = None
    skills: tuple[SkillSpec, ...] = ()
    helper_timeout: Callable[[], float] | None = None
    # Módulos de `app.tools` que registran las tools de esta brigada y que el arranque liviano NO carga
    # (ej. los de pentest, que traen `phone_link`/scapy). Se importan recién al instanciar el jefe, así que
    # el orquestador liviano arranca igual de rápido y solo paga ese costo si alguien usa esta brigada.
    tool_modules: tuple[str, ...] = ()
    validation: ValidationSpec | None = None
    watch: WatchSpec | None = None         # expectativas de ejecución que vigila el watchdog (None = defaults globales)

    def __post_init__(self) -> None:
        # Decisión de Damian (2026-11-16): el jefe nunca responde directo. No existe la brigada "directa".
        if not self.ayudantes:
            raise ValueError(f"brigada {self.id}: necesita al menos un ayudante (el jefe coordina y sintetiza; no hace el trabajo)")
        if self.ayudantes and self.routing is None:
            raise ValueError(f"brigada {self.id}: tiene ayudantes pero no reglas de ruteo")
        if self.routing is not None:
            modos = {a.modo for a in self.ayudantes}
            targets = {r.modo for r in self.routing.reglas} | {self.routing.default}
            if not targets <= modos:
                raise ValueError(f"brigada {self.id}: el ruteo apunta a modos sin ayudante: {sorted(targets - modos)}")
        if self.client not in ("local", "shared"):
            raise ValueError(f"brigada {self.id}: client debe ser 'local' o 'shared' (es {self.client!r})")

    @property
    def delegating(self) -> bool:
        """Siempre True (toda brigada delega). Se conserva porque validaciones y vistas lo consultan."""
        return bool(self.ayudantes)

    def ayudante(self, modo: str) -> AyudanteSpec:
        for a in self.ayudantes:
            if a.modo == modo:
                return a
        raise KeyError(modo)

    def ensure_tool_modules(self) -> None:
        """Registra las tools de la brigada (idempotente: si ya estaban cargadas, no hace nada)."""
        for name in self.tool_modules:
            importlib.import_module(f"app.tools.{name}")

    def tool_names(self) -> frozenset[str]:
        """Techo de privilegio del jefe. Sin `tools` explícitas = la unión de sus ayudantes."""
        if self.tools is None:
            out: frozenset[str] = frozenset()
            for a in self.ayudantes:
                out |= a.tool_names()
            return out
        return self.tools() if callable(self.tools) else self.tools

    def chief_config(self) -> ChiefConfig:
        from .chief import ChiefConfig

        return ChiefConfig(
            id=self.id,
            name=self.name,
            tool_names=self.tool_names(),
            system_prompt=self.prompt,
            vault_path=self.vault_path,
            persistent=self.persistent,
        )

    @staticmethod
    def _modelo_efectivo(a: "AyudanteSpec") -> str:
        """Modelo real + proveedor del ayudante (no la etiqueta fija `donde`); si no se resuelve, cae a `donde`."""
        from .config import effective_label

        label = effective_label(a.resolve_client_model)
        return a.donde if label.startswith("modelo sin resolver") else label

    def describe_skills(self) -> list[dict]:
        """Skills para la vista de la Suite: una por ayudante (toda brigada delega)."""
        return [
            {
                "modo": a.modo,
                "ayudante": a.id,
                "descripcion": a.descripcion,
                "modelo": self._modelo_efectivo(a),
                "efimero": True,
                "tools": sorted(a.tool_names()),
            }
            for a in self.ayudantes
        ]

    def load_client_model(self) -> tuple:
        """(cliente, modelo) del JEFE: su LLM propio (planifica y sintetiza), intercambiable por config
        (`BRIGADE_<ID>_LLM_*` > modelo declarado > default de su tipo > global). Ver brigades/config.py."""
        from . import config

        return config.resolve_role_model("jefe", self.id, tipo=self.client, declarado=self.client_model)


def resolve(dotted: str) -> Callable:
    """'paquete.modulo:funcion' -> la función (import perezoso)."""
    mod, _, name = dotted.partition(":")
    return getattr(importlib.import_module(mod), name)
