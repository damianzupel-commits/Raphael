"""Config de la brigada (va en `installation.brigades.legales.config`) y datos del negocio.

    negocio: {nombre, cuit, domicilio, email, telefono, jurisdiccion}
    fuentes: {modo: real|mock|off, timeout: 10, dias_vigencia: 30, urls: {id_norma: https://...}}
    checklist: {respuestas: {id_item: cumple|pendiente|no_aplica}}
    riesgos: {palabras_extra: [{patron, mensaje, severidad}], ia: true}
    proveedor_ia: texto que se le dice al cliente sobre quién procesa sus mensajes

Los datos del negocio que falten se leen de variables de entorno `LEGALES_NEGOCIO_*` (ver `.env.plantilla`); lo que
siga faltando sale en los borradores como `[COMPLETAR: ...]` y en el healthcheck, sin romper nada.
"""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_IA_PROVIDER = "un proveedor externo de modelos de IA (OpenRouter)"
ENV_PREFIX = "LEGALES_NEGOCIO_"
BUSINESS_FIELDS = ("nombre", "cuit", "domicilio", "email", "telefono", "jurisdiccion")


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Negocio(_Base):
    nombre: str = Field("", max_length=120)
    cuit: str = Field("", max_length=20)
    domicilio: str = Field("", max_length=200)
    email: str = Field("", max_length=120)
    telefono: str = Field("", max_length=40)
    jurisdiccion: str = Field("Argentina", max_length=60)


class Fuentes(_Base):
    modo: Literal["real", "mock", "off"] = "real"
    timeout: float = Field(10.0, gt=0, le=60)
    dias_vigencia: int = Field(30, ge=1, le=365)     # pasado este plazo la verificación de una norma se considera vencida
    urls: dict[str, str] = {}                        # pisa la URL oficial de una norma (solo https)


class Checklist(_Base):
    respuestas: dict[str, Literal["cumple", "pendiente", "no_aplica"]] = {}


class ExtraRule(_Base):
    patron: str = Field(min_length=1, max_length=200)
    mensaje: str = Field(min_length=1, max_length=300)
    severidad: Literal["alta", "media", "baja"] = "media"


class Riesgos(_Base):
    palabras_extra: tuple[ExtraRule, ...] = ()
    ia: bool = True                                  # segunda lectura con modelo, si hay (nunca baja un veredicto)


class LegalesConfig(_Base):
    negocio: Negocio = Negocio()
    fuentes: Fuentes = Fuentes()
    checklist: Checklist = Checklist()
    riesgos: Riesgos = Riesgos()
    proveedor_ia: str = Field(DEFAULT_IA_PROVIDER, max_length=200)


def legales_config(raw: dict[str, Any] | None, env: dict[str, str] | None = None) -> LegalesConfig:
    """Valida la config y completa el negocio con las variables de entorno (lo del archivo gana)."""
    env = os.environ if env is None else env
    data = dict(raw or {})
    negocio = dict(data.get("negocio") or {})
    for f in BUSINESS_FIELDS:
        if not negocio.get(f) and env.get(ENV_PREFIX + f.upper()):
            negocio[f] = env[ENV_PREFIX + f.upper()]
    data["negocio"] = negocio
    fuentes = dict(data.get("fuentes") or {})
    if "modo" not in fuentes and env.get("LEGALES_FUENTES_MODO"):
        fuentes["modo"] = env["LEGALES_FUENTES_MODO"]
    if "timeout" not in fuentes and env.get("LEGALES_FUENTES_TIMEOUT"):
        fuentes["timeout"] = float(env["LEGALES_FUENTES_TIMEOUT"])
    data["fuentes"] = fuentes
    return LegalesConfig.model_validate(data)


def missing_business(cfg: LegalesConfig) -> list[str]:
    return [f for f in ("nombre", "cuit", "domicilio", "email") if not getattr(cfg.negocio, f)]
