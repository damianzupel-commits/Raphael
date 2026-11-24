"""El jefe de la brigada de ejemplo y sus efímeros."""

from raphael_core.engine import BrigadeSpec, HelperSpec, RouteRule, Routing

SPEC = BrigadeSpec(
    id="saludo",
    name="Brigada de saludo",
    purpose="Ayudar a Damian a no olvidarse de saludar ni de los regalos.",
    prompt="Sos el jefe de la brigada de saludo de Raphael. Coordinás a tus efímeros y reportás con precisión.",
    helpers=(
        HelperSpec(mode="agenda", id="saludo-agenda", description="mira la agenda del día (solo lectura)",
                   prompt="Sos el efímero de agenda. Usá leer_agenda y contá lo que encontraste, tal cual.",
                   tools=frozenset({"leer_agenda", "contar_visitas"})),
        HelperSpec(mode="regalos", id="saludo-regalos", description="anota ideas de regalo (pide aprobación)",
                   prompt="Sos el efímero de regalos. Si te piden anotar un regalo usá anotar_regalo.",
                   tools=frozenset({"anotar_regalo"})),
    ),
    routing=Routing(rules=(RouteRule("regalos", r"\bregal"),), default="agenda"),
)
