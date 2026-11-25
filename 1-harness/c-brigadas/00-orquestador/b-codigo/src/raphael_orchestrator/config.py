"""Config del orquestador: lo que va en `installation.orchestrator.config` (o en un `orchestrator.yaml` aparte).

Reemplaza las más de 15 variables `ORQUESTADOR_*` de JarvisRemote. El proveedor de IA NO va acá: el orquestador pide
roles (`mando`, `voz`, `ruteo`) y la pasarela del harness resuelve plan -> rol -> escalones con `modelos.yaml`.

Dos modos, mismo código (DISENO §3.7):
  - `master`: Raphael personal. Punto de entrada único; trabajo conjunto prendido.
  - `secretary`: instalación de la clienta, sin maestro arriba. Trabajo conjunto apagado por defecto.

Ejemplo:
    mode: master
    voice:
      persona: ""            # vacío = la persona por defecto con los nombres de la instalación
      directives: "Respondeme corto."
      retries: 2
    memory: {max_turns: 8}
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

Mode = Literal["master", "secretary"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VoiceConfig(_Base):
    persona: str = Field("", max_length=4000)        # vacío = la de fábrica con los nombres de la instalación
    directives: str = Field("", max_length=4000)     # las directrices de la persona (forma, qué priorizar); editables
    retries: int = Field(2, ge=0, le=5)              # reintentos si el mensaje no es fiel al reporte
    chat_max_words: int = Field(60, ge=5, le=300)    # tope de la respuesta a charla social
    temperature: float = Field(0.3, ge=0, le=1.5)
    max_tokens: int | None = Field(None, ge=16, le=8000)


class MemoryConfig(_Base):
    enabled: bool = True
    max_turns: int = Field(8, ge=1, le=50)
    max_summary: int = Field(12, ge=0, le=100)
    max_request: int = Field(300, ge=40, le=4000)
    max_message: int = Field(500, ge=40, le=4000)


class RoutingConfig(_Base):
    """Ruteo (rol `ruteo`). Las señales de cada brigada están en SU manifiesto (`routing`), no acá."""

    classifier: bool = True              # consultar al modelo cuando las reglas empatan o no ven nada
    classifier_cloud: bool = True        # False = el clasificador solo usa modelos locales (decisión del 11 nov: True)
    min_words_for_classifier: int = Field(3, ge=0, le=50)   # hasta acá, un pedido sin señales va al destino seguro
    default_brigade: str | None = None   # destino seguro; None = la primera montada con `safe_default`
    fallback_cook: str | None = None     # mensajes de clientes: "brigada/cocinero" que queda siempre al final, como red


class WatchdogConfig(_Base):
    """Vigila las corridas de los jefes: lo que declara la brigada (`watch` de su spec) gana a estos defaults."""

    enabled: bool = True
    stall_seconds: float = Field(300, gt=0)
    max_repeats: int = Field(4, ge=2)
    max_errors: int = Field(5, ge=1)
    margin_seconds: float = Field(30, ge=0)
    chief_seconds: float = Field(600, ge=0)   # lo que puede tardar el modelo del jefe además de sus efímeros
    poll_seconds: float = Field(2, gt=0, le=60)
    keep: int = Field(50, ge=1, le=1000)      # intervenciones que se guardan


class JointConfig(_Base):
    """Trabajo conjunto (rol `mando` + DAG). `enabled: null` = prendido en `master`, apagado en `secretary`."""

    enabled: bool | None = None
    split_llm: bool = True          # el mando reparte con su modelo (si no, cada brigada recibe el pedido entero)
    conclusion_llm: bool = True     # el mando concluye sobre los reportes
    dag: bool = True                # aceptar dependencias entre brigadas (si no, todo en paralelo)
    max_brigades: int = Field(4, ge=2, le=12)
    max_levels: int = Field(3, ge=1, le=12)
    max_seconds: float = Field(1800, gt=0)


class ProactiveConfig(_Base):
    """Avisos proactivos (leen y avisan, nunca ejecutan)."""

    enabled: bool = True
    new_pending: Literal["human", "all", "none"] = "human"   # qué pendientes nuevos se avisan
    remind_after_hours: float = Field(24, ge=0)               # 0 = sin recordatorios
    warn_no_ai: bool = True                                   # avisar (una vez por día) si falta el modelo de algún rol


class SpeechConfig(_Base):
    """Voz hablada (oír y hablar). `auto` = local si están los paquetes y la voz, si no apagada y lo avisa; `mock` = simulada."""

    mode: Literal["auto", "local", "mock", "off"] = "auto"
    max_chars: int = Field(1200, ge=100, le=5000)    # lo más largo que se lee en voz alta


class OrchestratorConfig(_Base):
    mode: Mode = "master"
    voice: VoiceConfig = VoiceConfig()
    memory: MemoryConfig = MemoryConfig()
    routing: RoutingConfig = RoutingConfig()
    watchdog: WatchdogConfig = WatchdogConfig()
    joint: JointConfig = JointConfig()
    proactive: ProactiveConfig = ProactiveConfig()
    speech: SpeechConfig = SpeechConfig()
    chat_direct: bool = True        # saludo / gracias / chau los contesta el orquestador sin despertar a una brigada
    self_knowledge: bool = True     # "¿qué brigadas tenés?" lo contesta el orquestador con el catálogo
    drafts: bool | None = None      # comandos de brigadas por borrador; None = solo en la edición personal

    def joint_enabled(self) -> bool:
        return self.joint.enabled if self.joint.enabled is not None else self.mode == "master"

    def drafts_enabled(self, edition: str) -> bool:
        return self.drafts if self.drafts is not None else edition == "personal"


def config_from(data: dict | None) -> OrchestratorConfig:
    """Valida la config. Un campo desconocido o fuera de rango es un error (mejor fallar al montar que en un turno)."""
    return OrchestratorConfig.model_validate(data or {})


def load_config(path: str | Path) -> OrchestratorConfig:
    return config_from(yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {})
