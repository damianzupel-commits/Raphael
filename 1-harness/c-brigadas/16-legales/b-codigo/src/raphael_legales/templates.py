"""Plantillas de documentos con variables `{{variable}}`. Lo que falte sale como `[COMPLETAR: variable]` y se lista.

Son punto de partida redactado en lenguaje claro, NO texto validado por un abogado. No citan números de artículos ni
plazos que no estén verificados: donde hay que confirmar algo vigente dice `[VERIFICAR: ...]`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .disclaimer import DISCLAIMER

VAR = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")
# variables que salen de los datos del negocio (config / entorno)
BUSINESS_VARS = ("negocio_nombre", "cuit", "domicilio", "email", "telefono", "jurisdiccion", "proveedor_ia", "fecha")


@dataclass(frozen=True)
class Template:
    kind: str
    title: str
    norms: tuple[str, ...]
    body: str


T_PRIVACIDAD = """POLÍTICA DE PRIVACIDAD de {{negocio_nombre}}

Responsable: {{negocio_nombre}} (CUIT {{cuit}}), con domicilio en {{domicilio}}. Contacto: {{email}}.

1. Qué datos recopilamos. Los que nos das al escribirnos o al hacer un encargo: nombre, datos de contacto (teléfono, usuario de \
WhatsApp o Instagram), medidas y preferencias del pedido, y lo que nos cuentes en la conversación.
2. Para qué los usamos. Para responderte, armar tu presupuesto o encargo, coordinar turnos y entregas, avisarte del estado de tu \
pedido y cumplir obligaciones legales e impositivas. No usamos tus datos para otra finalidad sin pedirte permiso.
3. Mensajes automáticos y proveedores. Parte de la atención la asiste una herramienta de inteligencia artificial. Para eso, el \
texto de tus mensajes se procesa con {{proveedor_ia}}. Esa empresa es un tercero: [VERIFICAR: condiciones de retención y \
ubicación del tratamiento del proveedor vigente].
4. Consentimiento. Tratamos tus datos con tu consentimiento libre, expreso e informado, que podés retirar cuando quieras \
escribiéndonos.
5. Tus derechos. Podés pedir acceso, rectificación, actualización y supresión de tus datos escribiendo a {{email}}. \
[VERIFICAR: plazos de respuesta y autoridad de aplicación vigentes según la Ley 25.326].
6. Conservación y seguridad. Guardamos tus datos el tiempo necesario para la finalidad indicada y las obligaciones legales, con \
medidas razonables de seguridad.
7. Cambios. Si cambiamos esta política, publicamos la nueva versión con su fecha.

Fecha: {{fecha}}. Jurisdicción: {{jurisdiccion}}."""

T_TYC = """TÉRMINOS Y CONDICIONES de {{negocio_nombre}}

Proveedor: {{negocio_nombre}}, CUIT {{cuit}}, {{domicilio}}. Contacto y reclamos: {{email}}.

1. Qué ofrecemos. {{actividad}}.
2. Precios y formas de pago. Los precios se informan en pesos argentinos e incluyen los impuestos correspondientes salvo que se \
indique otra cosa. Medios de pago aceptados: {{medios_pago}}.
3. Encargos a medida. El precio y la seña se acuerdan por presupuesto antes de empezar. El encargo se confirma cuando recibimos y \
confirmamos la seña. Plazo estimado de entrega: {{plazo_entrega}}.
4. Cambios y devoluciones. {{politica_cambios}} [VERIFICAR: derecho de revocación en compras a distancia y su plazo, según la \
Ley 24.240 vigente].
5. Datos personales. Se tratan según nuestra Política de Privacidad.
6. Reclamos. Podés reclamar por {{email}}. [VERIFICAR: leyenda sobre defensa del consumidor y libro de quejas exigida por la \
normativa vigente de {{jurisdiccion}}].
7. Jurisdicción. {{jurisdiccion}}.

Fecha: {{fecha}}."""

T_PRESUPUESTO = """PRESUPUESTO de {{negocio_nombre}}
CUIT {{cuit}} · {{domicilio}} · {{email}}

Para: {{cliente}}
Fecha: {{fecha}}

Detalle: {{descripcion}}
Precio total: {{precio}}
Seña para confirmar: {{sena}}
Plazo estimado de entrega: {{plazo_entrega}}
Validez del presupuesto: {{validez_dias}} días corridos desde la fecha.

El encargo se confirma al recibir y confirmar la seña. Este presupuesto no es una factura."""

T_CONTRATO = """CONTRATO DE SERVICIO

Entre {{negocio_nombre}} (CUIT {{cuit}}, {{domicilio}}), en adelante "el Prestador", y {{cliente}}, en adelante "el Cliente", se \
acuerda:

1. Objeto. El Prestador realizará para el Cliente: {{servicio}}.
2. Precio y pago. {{precio}}. Forma de pago: {{forma_pago}}.
3. Plazo. {{plazo_entrega}}.
4. Obligaciones del Cliente. Brindar la información y medidas necesarias y retirar o recibir el trabajo en el plazo acordado.
5. Cambios y cancelación. {{politica_cambios}}
6. Datos personales. Se tratan según la Política de Privacidad del Prestador.
7. Jurisdicción. {{jurisdiccion}}. [VERIFICAR: cláusulas obligatorias para contratos con consumidores en la normativa vigente].

Firmas: ______________________   ______________________
Fecha: {{fecha}}"""

T_CARTA = """{{negocio_nombre}} · {{domicilio}}
{{fecha}}

{{destinatario}}:

Asunto: {{asunto}}

{{cuerpo}}

Saludamos atentamente,
{{negocio_nombre}}"""

TEMPLATES: dict[str, Template] = {t.kind: t for t in (
    Template("politica_privacidad", "Política de privacidad", ("ley-25326",), T_PRIVACIDAD),
    Template("terminos_condiciones", "Términos y condiciones", ("ley-24240", "ley-25326"), T_TYC),
    Template("presupuesto", "Presupuesto", ("arca-facturacion",), T_PRESUPUESTO),
    Template("contrato_servicio", "Contrato de servicio", ("ley-24240",), T_CONTRATO),
    Template("carta", "Carta", (), T_CARTA),
)}


def required_vars(kind: str) -> list[str]:
    seen: list[str] = []
    for v in VAR.findall(TEMPLATES[kind].body):
        if v not in seen:
            seen.append(v)
    return seen


def render(kind: str, values: dict[str, str]) -> tuple[str, list[str]]:
    """Devuelve (texto con encabezado de borrador, variables que faltaron)."""
    t = TEMPLATES[kind]
    missing: list[str] = []

    def sub(m: re.Match) -> str:
        name = m.group(1)
        val = str(values.get(name) or "").strip()
        if not val:
            if name not in missing:
                missing.append(name)
            return f"[COMPLETAR: {name}]"
        return val

    body = VAR.sub(sub, t.body)
    head = f"*** BORRADOR · {t.title} ***\n{DISCLAIMER}\n\n"
    return head + body, missing
