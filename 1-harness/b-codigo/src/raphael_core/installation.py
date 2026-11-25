"""Configuración de una instalación (`installation.yaml`): qué edición es, qué brigadas monta y cómo decide.

Lo del negocio (precios, encargos, horarios) NO va acá: va en la config de cada brigada
(`brigades.<id>.config`), validada contra el `config_schema` de su manifiesto.

Autonomía (decidido 21 nov 2026):
- Sin pisos fijos en el código. La persona puede fijar el nivel de cualquier acción en `autonomy`.
- Dejar en `automatico` una acción con gasto o irreversible exige `confirmed_by` (queda auditado).
- Confianza progresiva (`trust`): una acción que se aprueba N veces seguidas sin cambios baja un escalón;
  un rechazo o una aprobación con cambios la sube. La baja automática nunca deja en `automatico` una
  acción con gasto o irreversible: la propone y espera confirmación.

    id: clienta-ropa
    edition: cloud
    plan: pro
    identity: {assistant: Raphael, user: Ana}
    brigades:
      empresas: {active: true, config: {...}}
      legales: {active: false}
    autonomy:
      empresas.enviar_presupuesto: aprobacion
      empresas.confirmar_turno: {level: automatico, confirmed_by: Ana, confirmed_at: "2026-11-21"}
    trust: {enabled: true, approvals_to_step_down: 10}
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .contract import Level

_KEY = re.compile(r"^(?:[a-z][a-z0-9-]{0,39}\.)?[a-z][a-z0-9_]{0,59}$")


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Identity(_Base):
    assistant: str = "Raphael"
    user: str = ""                 # cómo se nombra a la persona que decide


class BrigadeToggle(_Base):
    active: bool = True
    config: dict = Field(default_factory=dict)


class AutonomyRule(_Base):
    level: Level
    confirmed_by: str | None = None    # quién confirmó bajar a automatico una acción con gasto o irreversible
    confirmed_at: str | None = None
    reason: str = ""


class TrustSpec(_Base):
    """Confianza progresiva."""

    enabled: bool = True
    approvals_to_step_down: int = Field(10, ge=1, le=1000)   # aprobaciones seguidas sin cambios para bajar un escalón
    step_down_from_human: bool = False                       # ¿lo que es `humano` también puede bajar a `aprobacion`?
    third_party_step_up: bool = False                        # ¿lo disparado por contenido de terceros sube un escalón?


#: el deslizador global de autonomía (`RAPHAEL_AUTONOMIA`, pantalla de Configuración del panel). Por defecto, equilibrado.
#:   cauteloso    sin confianza progresiva y lo que el manifiesto deja en automático pasa a pedir aprobación
#:   equilibrado  lo de siempre (manifiesto + confianza progresiva con `trust.approvals_to_step_down`)
#:   confiado     la confianza progresiva baja con la mitad de aprobaciones seguidas (mínimo 2)
#: NO cambia la regla general: lo que sale al mundo, gasta o no tiene vuelta (`external`, `spend`, `irreversible`) pide
#: aprobación en los tres, y bajarlo a automático sigue exigiendo `confirmed_by` de la persona.
PROFILES = ("cauteloso", "equilibrado", "confiado")
DEFAULT_PROFILE = "equilibrado"


def profile_from(environ: Mapping[str, str] | None) -> str | None:
    """El perfil que pide el entorno (`RAPHAEL_AUTONOMIA`), o None si no está. Un valor desconocido es un error: mejor
    frenar que dejar la autonomía en un nivel que la persona no eligió."""
    raw = ((environ or {}).get("RAPHAEL_AUTONOMIA") or "").strip().lower()
    if not raw:
        return None
    if raw not in PROFILES:
        raise ValueError(f"RAPHAEL_AUTONOMIA: '{raw}' no existe (hay: {', '.join(PROFILES)})")
    return raw


class Limits(_Base):
    messages_month: int = Field(3000, gt=0)


class OrchestratorRef(_Base):
    """Qué orquestador monta esta instalación (2.1). `entry`: 'paquete.modulo:Clase' o el nombre de un entry point del
    grupo `raphael.orchestrators`. `config` se le pasa a `Orchestrator.configure` (modo, toggles, topes)."""

    entry: str = Field(min_length=1, max_length=200)
    config: dict = Field(default_factory=dict)


class Installation(_Base):
    id: str
    edition: Literal["personal", "cloud"]
    plan: str = "basico"
    identity: Identity = Identity()
    brigades: dict[str, BrigadeToggle] = Field(default_factory=dict)
    autonomy: dict[str, AutonomyRule] = Field(default_factory=dict)
    trust: TrustSpec = TrustSpec()
    profile: Literal["cauteloso", "equilibrado", "confiado"] = "equilibrado"   # deslizador global de autonomía
    limits: Limits = Limits()
    timezone: str = "America/Argentina/Buenos_Aires"
    orchestrator: OrchestratorRef | None = None   # None = el orden simple del harness (o el que se pase al Runtime)

    @field_validator("autonomy", mode="before")
    @classmethod
    def _autonomy(cls, v: dict) -> dict:
        out = {}
        for key, rule in (v or {}).items():
            if not _KEY.match(str(key)):
                raise ValueError(f"clave de autonomía inválida (se espera 'accion' o 'brigada.accion'): {key!r}")
            out[key] = {"level": rule} if isinstance(rule, (str, Level)) else rule
        return out

    def use_profile_from(self, environ: Mapping[str, str] | None) -> str:
        """Toma el perfil de `RAPHAEL_AUTONOMIA` si está en el entorno (si no, deja el de la instalación)."""
        wanted = profile_from(environ)
        if wanted is not None:
            self.profile = wanted
        return self.profile

    def active_brigades(self) -> list[str]:
        return [b for b, t in self.brigades.items() if t.active]

    def brigade_config(self, brigade: str) -> dict:
        t = self.brigades.get(brigade)
        return dict(t.config) if t else {}


def installation_from(data: dict) -> Installation:
    return Installation.model_validate(data)


def load_installation(path: str | Path) -> Installation:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return installation_from(data)


def save_installation(installation: Installation, path: str | Path) -> None:
    """Guarda la instalación (lo que el panel cambia: brigadas activas, autonomía). Escribe a un temporal y reemplaza,
    para no dejar un archivo a medias si se corta."""
    p = Path(path)
    data = installation.model_dump(mode="json", exclude_defaults=False)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    os.replace(tmp, p)
