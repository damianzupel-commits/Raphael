"""Perfil de empresa: lo único que cambia de un cliente a otro.

El código es el mismo para todas las empresas; cada una tiene su `perfil.yaml` con sus datos,
sus reglas, las brigadas que contrató y su plan. Ver `ejemplos/perfil-ropa-medida.yaml`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

NivelTexto = Literal["automatico", "aprobacion", "humano"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Empresa(_Base):
    nombre: str
    rubro: str = "encargos_ropa_medida"
    duena: str = ""
    tono: Literal["voseo_emojis", "voseo_formal", "usted"] = "voseo_emojis"
    zona_horaria: str = "America/Argentina/Buenos_Aires"


class PreguntaFrecuente(_Base):
    pregunta: str
    respuesta: str
    palabras: list[str] = []


class Informacion(_Base):
    """Lo único que el bot puede afirmar. Lo que no está acá, no lo dice."""

    horarios: str = ""
    envios: str = ""
    medios_pago: list[str] = []
    ubicacion: str = ""
    faq: list[PreguntaFrecuente] = []


class Cobros(_Base):
    sena_pct: float = Field(50, ge=0, le=100)
    alias: str = ""
    titular: str = ""


class Precio(_Base):
    prenda: str
    base: float = Field(gt=0)
    dias: int | None = None


class Recargo(_Base):
    palabra: str
    tipo: Literal["pct", "monto"]
    valor: float


PASOS_ENCARGO = ["prenda", "ocasion", "fecha", "detalles", "referencias", "medidas", "nombre"]


class Encargos(_Base):
    datos_obligatorios: list[str] = list(PASOS_ENCARGO)
    urgente_si_dias_menor_a: int = Field(15, ge=0)
    precios: list[Precio] = []
    recargos: list[Recargo] = []

    @field_validator("datos_obligatorios")
    @classmethod
    def _pasos_validos(cls, v: list[str]) -> list[str]:
        malos = [p for p in v if p not in PASOS_ENCARGO]
        if malos:
            raise ValueError(f"pasos desconocidos: {malos}. Válidos: {PASOS_ENCARGO}")
        if "nombre" not in v:
            v = [*v, "nombre"]                     # siempre se pide el nombre
        return v


class Agenda(_Base):
    recordatorio_dias_antes: int = Field(3, ge=0)
    franjas: list[str] = []


class Limites(_Base):
    mensajes_mes: int = Field(3000, gt=0)


class Perfil(_Base):
    empresa: Empresa
    plan: Literal["basico", "pro", "privado", "premium"] = "basico"
    brigadas: list[str] = ["atencion"]
    informacion: Informacion = Informacion()
    cobros: Cobros = Cobros()
    encargos: Encargos = Encargos()
    agenda: Agenda = Agenda()
    politicas: dict[str, NivelTexto] = {}
    limites: Limites = Limites()

    @property
    def negocio(self) -> str:
        return self.empresa.nombre

    @property
    def quien_decide(self) -> str:
        """Cómo se nombra a la persona que decide, en los mensajes a clientes."""
        return self.empresa.duena or self.empresa.nombre


def cargar_perfil(ruta: str | Path) -> Perfil:
    datos = yaml.safe_load(Path(ruta).read_text(encoding="utf-8")) or {}
    return Perfil.model_validate(datos)


def perfil_de(datos: dict) -> Perfil:
    return Perfil.model_validate(datos)
