"""Config de la brigada (la trae la instalación en `brigades.autorreparacion.config`)."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

ROOT_ENV = "RAPHAEL_REPAIR_ROOT"


class RepairConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: carpeta del proyecto cuyo código se puede reparar. Vacía = variable de entorno RAPHAEL_REPAIR_ROOT
    root: str = ""
    #: fragmentos de ruta que se SUMAN a las líneas rojas de fábrica (nunca las reemplazan ni las sacan)
    extra_protected: list[str] = Field(default_factory=list)
    #: si la raíz es un repo git, cada arreglo queda en su propio commit (revertible)
    git_commit: bool = True
    #: comando (lista, sin shell) que corre después de aplicar; si falla, se deshace solo. Vacío = no verifica
    verify_command: list[str] = Field(default_factory=list)
    verify_timeout_seconds: int = Field(300, ge=1, le=3600)
    #: True = el modelo que redacta arreglos solo puede ser local (el código no sale de la PC)
    ai_private: bool = False
    #: archivo JSONL con el registro de tool calls del agente, para la introspección. Vacío = solo lo que se le pase
    audit_log_path: str = ""
    #: cada cuántos minutos analiza solo ese registro (0 = apagado)
    analyze_every_minutes: int = Field(0, ge=0, le=10080)
    #: cuántas repeticiones seguidas cuentan como un patrón
    min_repeats: int = Field(3, ge=2, le=100)


def repair_config(raw: dict | None) -> RepairConfig:
    return RepairConfig(**(raw or {}))


def resolve_root(cfg: RepairConfig) -> Path | None:
    """La raíz configurada (o la de la variable de entorno), o None si no hay ninguna."""
    text = cfg.root.strip() or os.environ.get(ROOT_ENV, "").strip()
    return Path(text).expanduser().resolve() if text else None
