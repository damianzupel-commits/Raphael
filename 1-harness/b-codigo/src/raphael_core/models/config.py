"""Configuración de modelos (`modelos.yaml`): proveedores, escalones y el orden de escalones de cada rol.

Decidido el 21 nov 2026: tres escalones.
    pago    potente, cuesta plata (con tope mensual en dólares)
    gratis  rota entre proveedores gratis (si uno da "límite alcanzado", pasa al siguiente)
    local   corre en la PC: poca potencia, costo cero, lo único admitido para lo privado
Hoy los tres apuntan a NVIDIA (sin plata para pago ni modelo local todavía).

Las claves nunca van acá: cada proveedor nombra la variable de entorno que la tiene (`api_key_env`), y la
clave de un proveedor solo se le manda a ese proveedor.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

#: roles canónicos y los nombres viejos que se traducen a ellos
ROLES = ("mando", "voz", "ruteo", "jefe", "cocinero", "efimero")
DEFAULT_ALIASES = {
    "orquestador": "mando", "secretaria": "mando", "ayudante": "efimero",
    "intencion": "cocinero", "redaccion": "cocinero", "resumen": "cocinero",
}
LOOPBACK = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
DEFAULT_PATH = Path(__file__).with_name("modelos.yaml")


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProviderSpec(_Base):
    base_url: str = ""
    model: str = ""
    api_key_env: str = ""               # variable de entorno con la clave ("" = no hace falta, ej. local)
    api_key: str = ""                   # solo para compatibilidad con Empresas 0.4; no usar
    usd_per_million_in: float = Field(0.0, ge=0)
    usd_per_million_out: float = Field(0.0, ge=0)
    rpm: int | None = Field(None, gt=0)            # pedidos por minuto que acepta (None = sin control)
    tokens_per_day: int | None = Field(None, gt=0)  # cupo diario de tokens (None = sin control)
    extra: dict = Field(default_factory=dict)      # campos extra del cuerpo (ej. apagar el razonamiento)

    @property
    def usable(self) -> bool:
        return bool(self.base_url and self.model)

    @property
    def is_local(self) -> bool:
        """¿Corre en esta máquina? Se mira la dirección real, no el nombre del escalón."""
        return (urlparse(self.base_url).hostname or "") in LOOPBACK

    @property
    def free(self) -> bool:
        return self.usd_per_million_in == 0 and self.usd_per_million_out == 0


class ModelsConfig(_Base):
    providers: dict[str, ProviderSpec] = Field(default_factory=dict)
    tiers: dict[str, list[str]] = Field(default_factory=dict)       # escalón -> proveedores (en rotación)
    roles: dict[str, list[str]] = Field(default_factory=dict)       # rol -> escalones en orden
    aliases: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_ALIASES))
    overrides: dict[str, list[str]] = Field(default_factory=dict)   # "rol.id" (brigada o ayudante) -> escalones
    plans: dict[str, dict[str, list[str]]] = Field(default_factory=dict)  # plan -> rol -> escalones
    paid_tiers: list[str] = Field(default_factory=lambda: ["pago"])
    paid_cap_usd_month: float = Field(0.0, ge=0)   # 0 = en los escalones pagos solo se usan proveedores sin costo
    private: list[str] = Field(default_factory=list)  # brigadas o ayudantes privados: solo modelos locales
    cooldown_seconds: float = Field(60.0, ge=0)        # pausa de un proveedor que dio "límite alcanzado"
    local_retry_seconds: float = Field(3.0, ge=0)     # espera antes de reintentar UNA vez un modelo local que se cortó
    error_cooldown_seconds: float = Field(20.0, ge=0)  # pausa de un proveedor que falló por otra cosa

    @model_validator(mode="after")
    def _references(self) -> ModelsConfig:
        missing = sorted({p for ps in self.tiers.values() for p in ps if p not in self.providers})
        if missing:
            raise ValueError(f"escalones con proveedores que no existen: {missing}")
        chains = [*self.roles.values(), *self.overrides.values(), *(c for p in self.plans.values() for c in p.values())]
        unknown = sorted({t for c in chains for t in c if t not in self.tiers})
        if unknown:
            raise ValueError(f"roles que piden escalones que no existen: {unknown}")
        return self

    def canonical(self, role: str) -> str:
        return self.aliases.get(role, role)


def models_from(data: dict) -> ModelsConfig:
    return ModelsConfig.model_validate(data or {})


def load_models(path: str | Path | None = None) -> ModelsConfig:
    return models_from(yaml.safe_load(Path(path or DEFAULT_PATH).read_text(encoding="utf-8")) or {})
