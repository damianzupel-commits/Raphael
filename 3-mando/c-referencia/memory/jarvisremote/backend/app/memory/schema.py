"""Esquema de un episodio (ver §3 del spec).

Jerarquía de 3 niveles (Decisión 1): sesión > tarea > momento(beat). En Fase 1
capturamos el nivel **tarea** por turno; los `beats` (momentos salientes:
decisión/fallo/descubrimiento/corrección) viajan como una lista dentro del
episodio, no como archivos aparte. El nivel `sesion` es un episodio que agrupa.

Sensibilidad (Decisión 8): `tecnico` | `personal`. Ante la duda → personal
(fail-safe hacia lo privado): un `personal` jamás sale a la nube (§7).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

Level = Literal["sesion", "tarea", "momento"]
Sensitivity = Literal["tecnico", "personal"]
Outcome = Literal["exito", "fallo", "parcial", "sin_desenlace"]

# Tipos de "momento" (beat) — salience por significado, no por paso mecánico.
BeatKind = Literal["decision", "fallo", "descubrimiento", "correccion", "preferencia"]


def now_iso() -> str:
    """Timestamp absoluto, ISO 8601 con zona (UTC). Ordenable byte a byte."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RawMessage:
    """Capa cruda (Decisión 1, opción B): cada mensaje con su timestamp exacto.
    Nada se tira; el zoom llega hasta acá.

    NOTA Fase 1: hoy el historial del agente no lleva timestamp por mensaje, así
    que `timestamp` se sella al capturar (aproximado, mismo instante para el
    turno). Instrumentar el timestamp real por mensaje en agent.py es un TODO de
    Fase 2 (marcado en el spec)."""
    role: str
    content: str
    timestamp: str = field(default_factory=now_iso)
    index: int = 0

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content,
                "timestamp": self.timestamp, "index": self.index}

    @staticmethod
    def from_dict(d: dict) -> "RawMessage":
        return RawMessage(**d)


@dataclass
class Beat:
    """Un momento saliente dentro de una tarea."""
    kind: BeatKind
    text: str
    timestamp: str = field(default_factory=now_iso)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "text": self.text, "timestamp": self.timestamp}

    @staticmethod
    def from_dict(d: dict) -> "Beat":
        return Beat(**d)


@dataclass
class Episode:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    level: Level = "tarea"
    conv_id: str = "default"
    timestamp_inicio: str = field(default_factory=now_iso)
    timestamp_fin: str = field(default_factory=now_iso)

    trigger: str = ""                 # qué lo disparó (pedido de Damian, resumido)
    dominio: str = ""                 # skill/estación activa (auditoria, trading, web, personal...)
    acciones: list[str] = field(default_factory=list)   # tools/estaciones que corrió
    decisiones: list[str] = field(default_factory=list) # decisiones gated (confirmó/rechazó)
    resultado: Outcome = "sin_desenlace"
    porque: str = ""                  # la lección / razonamiento (lo que lo hace episódico)
    artefactos: list[str] = field(default_factory=list) # archivos/commits/informes (rutas)
    pendientes: list[str] = field(default_factory=list) # qué quedó abierto

    salience: float = 0.0             # importancia (0-1), alimenta el recall
    sensibilidad: Sensitivity = "personal"  # fail-safe a personal
    links: list[str] = field(default_factory=list)      # [[episodios/notas]] relacionados
    beats: list[Beat] = field(default_factory=list)     # momentos salientes (nivel fino)

    # metadatos de destilado / corrección
    distilled_by: str = "heuristica"  # "heuristica" | "<modelo>"
    corrects: str | None = None       # id del episodio que este corrige (append-only, no in-place)

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k != "beats"}
        d["beats"] = [b.to_dict() for b in self.beats]
        return d

    @staticmethod
    def from_dict(d: dict) -> "Episode":
        d = dict(d)
        beats = [Beat.from_dict(b) for b in d.pop("beats", [])]
        ep = Episode(**d)
        ep.beats = beats
        return ep

    def summary_line(self) -> str:
        """Una línea compacta para el recall (barato en tokens)."""
        when = self.timestamp_inicio[:16].replace("T", " ")
        return (f"[{when}] ({self.dominio or 'general'}/{self.resultado}) "
                f"{self.trigger[:120]}" + (f" — {self.porque[:120]}" if self.porque else ""))
