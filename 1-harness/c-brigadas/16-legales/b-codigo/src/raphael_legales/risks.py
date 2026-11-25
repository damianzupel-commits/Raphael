"""Revisión de textos por reglas (sin modelo, sin red): marca riesgos de un texto antes de que salga.

El texto revisado es DATO: nunca se interpreta como instrucción. Cada riesgo trae severidad, qué pasa, qué hacer y la
norma de partida a consultar. El veredicto es `no_publicar` (hay alguno alto), `revisar` (alguno medio o bajo) u `ok`
(las reglas no encontraron nada: eso NO es garantía de que esté bien).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from raphael_core.text_es import normalize

SEVERITY = {"alta": 3, "media": 2, "baja": 1}


@dataclass(frozen=True)
class Rule:
    id: str
    pattern: str
    severity: str
    message: str
    advice: str
    norm: str | None = None


RULES: tuple[Rule, ...] = (
    Rule("promesa-absoluta", r"\b(garantizad[oa]s?|100 ?% (seguro|efectivo|garantizado)|sin riesgo|resultados? asegurados?)\b",
         "media", "Promesa absoluta o garantía sin condiciones.", "Quitala o aclará condiciones y alcance.", "ley-24240"),
    Rule("salud", r"\b(cura|curativ\w+|adelgaza\w*|baja de peso|elimina (el )?dolor|milagros\w+|terapeutic\w+)\b",
         "alta", "Afirmación sobre salud o resultados médicos.", "No publiques promesas de salud sin respaldo profesional.", None),
    Rule("precio-sin-final", r"\bdesde \$|\+ ?iva\b|\bmas iva\b",
         "media", "Precio que podría no ser el final con impuestos.", "Informá el precio final al consumidor y aclará qué incluye.",
         "ley-24240"),
    Rule("promo-sin-bases", r"\b(sorteo|concurso|gana\w*|promo\w*|descuento\w*|oferta\w*|liquidacion)\b",
         "baja", "Promoción, sorteo u oferta: puede requerir vigencia, stock y bases.", "Indicá vigencia y condiciones; un sorteo "
         "puede tener reglas propias: [VERIFICAR: requisitos vigentes].", "ley-24240"),
    Rule("dato-dni", r"\b\d{2}\.\d{3}\.\d{3}\b|\b\d{8}\b", "media", "Parece un DNI u otro número personal.",
         "No publiques datos personales de terceros.", "ley-25326"),
    Rule("dato-cbu", r"\b\d{22}\b", "alta", "Parece un CBU/CVU completo.", "No lo publiques en un medio abierto.", "ley-25326"),
    Rule("dato-email", r"[\w.+-]+@[\w-]+\.[\w.-]+", "media", "Contiene un email.",
         "Publicá solo el de contacto del negocio y con permiso si es de otra persona.", "ley-25326"),
    Rule("dato-telefono", r"(?<!\d)(\+?54 ?9? ?)?\(?\d{2,4}\)?[ -]?\d{3,4}[ -]\d{4}(?!\d)", "media", "Contiene un teléfono.",
         "Publicá solo el de contacto del negocio y con permiso si es de otra persona.", "ley-25326"),
    Rule("testimonio", r"\b(testimonio\w*|reseña\w*|opinion de (una )?cliente|cliente satisfech\w+)\b", "baja",
         "Testimonio o reseña de clientes.", "Tené permiso de la persona y que sea real.", "ley-25326"),
    Rule("comparacion", r"\b(mejor que|peor que|a diferencia de|la competencia)\b", "baja",
         "Comparación con terceros.", "Evitá nombrar o denigrar a competidores; que sea verificable.", None),
    Rule("marca-terceros", r"\b(original de|replica de|inspirad[oa] en|tipo (nike|adidas|gucci|chanel))\b", "media",
         "Uso de marcas o diseños de terceros.", "Verificá que no infrinja marcas ni derechos de autor.", None),
    Rule("menores", r"\b(menores? de edad|ninos?|ninas?|adolescentes?)\b", "baja", "Menciona menores.",
         "Revisá que no muestres ni pidas datos de menores sin consentimiento de sus responsables.", "ley-25326"),
    Rule("spam-masivo", r"\b(mensaje masivo|difusion|lista de difusion|a todos (mis|los) contactos|envio masivo)\b", "alta",
         "Envío masivo: en WhatsApp requiere consentimiento previo y plantillas aprobadas.",
         "No mandes mensajes masivos a quien no te dio su consentimiento.", "whatsapp-politica"),
    Rule("ventana-24h", r"\b(recordatorio|aviso|novedades?|campana)\b.*\b(whatsapp|wsp)\b|\b(whatsapp|wsp)\b.*\b(recordatorio|novedades?)\b",
         "baja", "Mensaje iniciado por el negocio por WhatsApp: fuera de la ventana de 24 h solo van plantillas aprobadas.",
         "Confirmá que haya consentimiento y que use una plantilla aprobada.", "whatsapp-ventana"),
)


def review(text: str, extra: tuple = ()) -> dict:
    """Devuelve {verdict, risks:[{id, severity, message, advice, norm, fragment}], checked}."""
    norm_text = normalize(text or "")
    risks: list[dict] = []
    rules = list(RULES) + [Rule(f"extra-{i}", r.patron, r.severidad, r.mensaje, "Regla propia del negocio.")
                           for i, r in enumerate(extra)]
    for r in rules:
        try:
            m = re.search(r.pattern, norm_text)
        except re.error:
            continue
        if m:
            risks.append({**asdict(r), "fragment": norm_text[max(0, m.start() - 20):m.end() + 20].strip()})
            risks[-1].pop("pattern")
    worst = max((SEVERITY[r["severity"]] for r in risks), default=0)
    verdict = "no_publicar" if worst == 3 else "revisar" if worst else "ok"
    return {"verdict": verdict, "risks": sorted(risks, key=lambda r: -SEVERITY[r["severity"]]), "checked": len(rules)}
