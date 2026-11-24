"""Tool de auto-introspección (2026-10-13, ítem 6 — capa 1 de autoconciencia).

Raphael lee su PROPIO self-model: qué es, qué puede, qué tiene prendido/apagado, sus líneas
rojas y sus límites. Va en CORE (siempre disponible), como jarvis_reflect — es metacognición,
cross-cutting por diseño. La verdad sale de app/self_model.py (registro de tools, brigadas,
config), no de adivinar.
"""

from . import register_tool


@register_tool(
    name="raphael_self_model",
    description=(
        "Devuelve el modelo de vos mismo (Raphael): nombre y modelo, tus brigadas, TODAS tus tools, "
        "qué capacidades tenés prendidas/apagadas, los jobs de fondo activos, tus líneas rojas y tus "
        "límites honestos. Usalo para responder con la VERDAD sobre qué podés/no podés hacer y qué "
        "tenés configurado, en vez de adivinar o suponer."
    ),
    parameters={"type": "object", "properties": {}, "required": []},
)
def raphael_self_model() -> dict:
    from ..self_model import build

    return build()
