"""Modelo de entidades del forense: nodos y aristas tipados, con id determinístico donde hay clave natural.

- Archivo (sha256 del contenido), Cuenta (plataforma + handle) y Host (ip o dominio) resuelven SIEMPRE al mismo id:
  reingestar el mismo artefacto no duplica nada.
- Persona, Organización, Evento y Transacción no tienen una clave natural confiable entre fuentes: nacen con id propio
  del parser (estable dentro de su artefacto) y la identidad entre fuentes se resuelve a mano con `mismo_que`,
  nunca por parecido de nombre.
- Nada se borra: un nodo o una arista se RETRACTA (queda en el historial con su motivo).
"""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Any


class NodeType(StrEnum):
    PERSONA = "Persona"
    CUENTA = "Cuenta"
    DISPOSITIVO = "Dispositivo"
    HOST = "Host"
    ARCHIVO = "Archivo"
    TRANSACCION = "Transacción"
    EVENTO = "Evento"
    ORGANIZACION = "Organización"


class EdgeType(StrEnum):
    USA = "usa"
    CONTROLA = "controla"
    COMUNICA_CON = "comunica_con"
    TRANSFIERE_A = "transfiere_a"
    APARECE_EN = "aparece_en"
    CO_OCURRE_CON = "co-ocurre_con"
    MISMO_QUE = "mismo_que"


class Origin(StrEnum):
    PARSER = "parser"      # lo extrajo código determinístico de un artefacto
    MODELO = "modelo"      # lo propuso un modelo (siempre pasó por una confirmación)
    MANUAL = "manual"      # lo cargó la persona


REQUIRED_FIELDS: dict[NodeType, frozenset[str]] = {
    NodeType.PERSONA: frozenset({"etiqueta", "alias", "confianza"}),
    NodeType.CUENTA: frozenset({"plataforma", "handle"}),
    NodeType.DISPOSITIVO: frozenset({"tipo_dispositivo", "identificadores"}),
    NodeType.HOST: frozenset({"ip_o_dominio"}),
    NodeType.ARCHIVO: frozenset({"nombre", "sha256", "tamano", "mime"}),
    NodeType.TRANSACCION: frozenset({"tipo_transaccion", "monto", "timestamp", "contraparte"}),
    NodeType.EVENTO: frozenset({"timestamp_utc", "descripcion", "fuente"}),
    NodeType.ORGANIZACION: frozenset({"nombre", "identificadores"}),
}

#: tipos que un modelo o las reglas pueden PROPONER. Archivo nunca: su sha256 sale de bytes reales, no de un texto.
PROPOSABLE = tuple(t for t in NodeType if t is not NodeType.ARCHIVO)


def stable_id(tipo: NodeType, natural_key: str) -> str:
    """Mismo (tipo, clave) -> mismo id, siempre."""
    digest = hashlib.sha256(f"{tipo.value}:{natural_key}".encode()).hexdigest()[:24]
    return f"{_slug(tipo.value)}-{digest}"


def _slug(text: str) -> str:
    return text.lower().replace("ó", "o").replace("í", "i")


def validate_fields(tipo: NodeType, campos: dict[str, Any]) -> dict[str, Any]:
    missing = REQUIRED_FIELDS[tipo] - campos.keys()
    if missing:
        raise ValueError(f"faltan campos requeridos para {tipo.value}: {sorted(missing)}")
    conf = campos.get("confianza")
    if conf is not None and not (isinstance(conf, int | float) and 0 <= conf <= 1):
        raise ValueError(f"confianza debe estar entre 0 y 1, vino {conf!r}")
    return campos


def natural_key(tipo: NodeType, campos: dict[str, Any]) -> str | None:
    """La clave natural de los tipos que la tienen (para el id determinístico)."""
    if tipo is NodeType.ARCHIVO:
        return str(campos["sha256"])
    if tipo is NodeType.CUENTA:
        return f"{str(campos['plataforma']).lower()}:{str(campos['handle']).lower()}"
    if tipo is NodeType.HOST:
        return str(campos["ip_o_dominio"]).lower()
    return None


def make_node(tipo: NodeType, campos: dict[str, Any], *, key: str | None = None) -> dict[str, Any]:
    """Un nodo listo para guardar. `key` fuerza una clave (para ids estables dentro de un artefacto)."""
    validate_fields(tipo, campos)
    nk = key if key is not None else natural_key(tipo, campos)
    if nk is None:
        raise ValueError(f"{tipo.value} necesita una clave: pasá `key` (un id estable dentro de su artefacto)")
    return {"id": stable_id(tipo, nk), "tipo": tipo.value, "campos": campos, "retracted": False}


def make_edge(tipo: EdgeType, src: str, dst: str, *, artefacto_origen: str, origen: Origin = Origin.PARSER,
              confianza: float = 1.0, detalle: str = "") -> dict[str, Any]:
    if not artefacto_origen:
        raise ValueError("toda arista necesita artefacto_origen (un sha256, 'manual' o 'fusion_analisis')")
    if not (0 <= confianza <= 1):
        raise ValueError(f"confianza debe estar entre 0 y 1, vino {confianza!r}")
    digest = hashlib.sha256(f"{tipo.value}|{src}|{dst}|{artefacto_origen}".encode()).hexdigest()[:24]
    return {"id": f"arista-{digest}", "tipo": tipo.value, "src": src, "dst": dst, "artefacto_origen": artefacto_origen,
            "origen": origen.value, "confianza": confianza, "detalle": detalle, "retracted": False}
