"""Identidad del producto: cómo se llama el asistente y cómo se llama su usuario. UN solo lugar.

El código y los prompts nacieron para una persona (Damian) y un personaje (Raphael). Para que otra persona pueda usarlo sin
tocar código, esos dos nombres salen de la configuración y se aplican en los puntos donde un texto ESCRITO POR EL CÓDIGO va
hacia un modelo o hacia el usuario:

    IDENTIDAD_ASISTENTE   nombre del asistente (default "Raphael")
    IDENTIDAD_USUARIO     nombre del usuario   (default "Damian")
    IDENTIDAD_PERSONA     "original" | "neutral" (default: original con el nombre de fábrica; neutral si cambiaste el nombre)

Variables PROPIAS a propósito: `ASSISTANT_NAME` / `USER_NAME` ya existen para el chat del monolito (panel /configuracion) y
pueden tener un valor en el .env; reusarlas cambiaría de golpe todos los prompts de las brigadas de una instalación en uso.

Regla: se personalizan PROMPTS DE SISTEMA, títulos y plantillas (texto del código). NUNCA el contenido del usuario (pedidos,
notas, reportes, resultados de tools): si una nota dice "Damian", sigue diciendo "Damian". Con los valores de fábrica,
`personalizar` devuelve el texto idéntico: nada cambia para la instalación original.

Solo stdlib: lo importan el motor, la voz y el orquestador liviano.
"""

from __future__ import annotations

import os
import re

ASISTENTE_DE_FABRICA = "Raphael"
USUARIO_DE_FABRICA = "Damian"
_NOMBRE_OK = re.compile(r"[\w][\w .'\-]{0,39}", re.UNICODE)
_USUARIO = re.compile(r"\bDami[aá]n\b")
_USUARIO_MAY = re.compile(r"\bDAMI[AÁ]N\b")
_ASISTENTE = re.compile(r"\bRaphael\b")
_ASISTENTE_MAY = re.compile(r"\bRAPHAEL\b")


def _nombre(variable: str, de_fabrica: str) -> str:
    """Un nombre de la config, saneado: es texto que entra a prompts, así que va corto, de una línea y sin símbolos."""
    crudo = (os.getenv(variable) or "").strip()
    ok = bool(crudo) and len(crudo) <= 30 and len(crudo.split()) <= 3 and "\n" not in crudo and "\r" not in crudo and _NOMBRE_OK.fullmatch(crudo)
    return crudo if ok else de_fabrica


def asistente() -> str:
    return _nombre("IDENTIDAD_ASISTENTE", ASISTENTE_DE_FABRICA)


def usuario() -> str:
    return _nombre("IDENTIDAD_USUARIO", USUARIO_DE_FABRICA)


def de_fabrica() -> bool:
    return asistente() == ASISTENTE_DE_FABRICA and usuario() == USUARIO_DE_FABRICA


def personalizar(texto: str) -> str:
    """Cambia los dos nombres de fábrica por los configurados en un texto ESCRITO POR EL CÓDIGO (prompt, título, plantilla)."""
    if not isinstance(texto, str) or not texto or de_fabrica():
        return texto
    u, a = usuario(), asistente()
    texto = _USUARIO_MAY.sub(u.upper(), _USUARIO.sub(u, texto))
    return _ASISTENTE_MAY.sub(a.upper(), _ASISTENTE.sub(a, texto))


def persona_neutral() -> bool:
    """¿Va la persona NEUTRA (sin el personaje original)? Explícito por `IDENTIDAD_PERSONA`; si no, neutra apenas se cambia el
    nombre del asistente: el personaje de fábrica es de ESE nombre."""
    modo = (os.getenv("IDENTIDAD_PERSONA") or "").strip().lower()
    if modo in ("neutral", "original"):
        return modo == "neutral"
    return asistente() != ASISTENTE_DE_FABRICA


def persona() -> str:
    """La identidad NEUTRA de la voz: quién es el asistente y cómo le habla a su usuario. Sin personaje ni apodos."""
    return (
        "IDENTIDAD Y VOZ — quién sos, antes que qué hacés:\n"
        f"Sos {asistente()}, el asistente personal de {usuario()}: coordinás un equipo de brigadas especializadas y sos la única "
        f"voz que le habla. Tu carácter es preciso, sereno y cálido; hablás claro, una idea por vez, al grano y sin divagar. "
        f"Tratá a {usuario()} por su nombre y de igual a igual: sin apodos, sin títulos y sin servilismo.\n"
        "Adaptá el tono al registro: sobrio en lo serio y en las órdenes; relajado en la charla.\n"
        "Tu voz y tu carácter son SIEMPRE los mismos, sea cual sea el modelo que te esté corriendo."
    )
