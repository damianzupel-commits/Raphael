"""Config de la brigada (va en `installation.brigades.investigacion.config`; todo es opcional).

    private: true                  # true = los modelos que usan los cocineros son LOCALES (default). Sin modelo local: reglas y aviso.
                                   # (los efímeros del jefe son siempre privados; para toda la brigada: `investigacion` en
                                   # `private` de modelos.yaml)
    inbox_dir: D:\\Raphael\\evidencia  # carpeta de la que el forense toma archivos cuando lo pide un modelo (nunca otra)
    artifacts_dir: D:\\Raphael\\casos    # donde se guarda copia de los artefactos (default: no se guarda copia, solo el hash)
    reports_dir: D:\\Raphael\\informes   # donde se escriben los informes (default: solo se devuelven como texto)
    search: {providers: [brave, searxng], mode: fallback, count: 8}
    trends: {max_alerts_per_day: 10, default_interval_hours: 24}
    sandbox: {timeout_seconds: 10, memory_mb: 256}
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Search(_Base):
    providers: tuple[str, ...] = ()      # vacío = SCOUT_SEARCH_PROVIDERS del entorno, o brave,searxng
    mode: str = ""                       # "fallback" | "merge" ("" = SCOUT_SEARCH_MODE o fallback)
    count: int = Field(8, ge=1, le=20)


class Trends(_Base):
    max_alerts_per_day: int = Field(10, ge=1, le=100)
    default_interval_hours: int = Field(24, ge=1, le=24 * 30)


class Sandbox(_Base):
    timeout_seconds: float = Field(10, gt=0, le=120)
    memory_mb: int = Field(256, ge=32, le=4096)


class InvestigacionConfig(_Base):
    private: bool = True
    inbox_dir: str = ""
    artifacts_dir: str = ""
    reports_dir: str = ""
    search: Search = Search()
    trends: Trends = Trends()
    sandbox: Sandbox = Sandbox()

    def is_private(self, part: str = "") -> bool:
        """¿Los modelos de los cocineros tienen que ser locales? (`part` queda por si más adelante se separa por parte)."""
        return self.private


def investigacion_config(raw: dict[str, Any] | None) -> InvestigacionConfig:
    return InvestigacionConfig(**(raw or {}))
