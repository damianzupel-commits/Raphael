"""Políticas con la interfaz de v1 (`Politicas(perfil_politicas, brigadas)`, `.nivel`, `.tabla`, `.ignoradas`).

Cambió la regla (decidido el 21 nov 2026): ya no hay pisos. Lo que en v1 eran pisos globales ahora son niveles
de fábrica, y las acciones que gastan plata o no tienen vuelta atrás llevan su etiqueta: el perfil puede
bajarlas a automático solo con confirmación (y la confianza progresiva nunca las baja sola).
"""

from __future__ import annotations

from ...contract import Level
from ...installation import installation_from
from ...manifest import ActionSpec
from ...policy import PolicyEngine
from ...store import Store
from .contrato import Brigada, Nivel

#: niveles de fábrica de las acciones conocidas de Empresas (antes: pisos)
GLOBALES: dict[str, Nivel] = {
    "anotar_duda": Nivel.AUTO, "avisar_estado": Nivel.AUTO, "enviar_recordatorio": Nivel.AUTO,
    "registrar_dato": Nivel.AUTO, "enviar_presupuesto": Nivel.APROBACION, "confirmar_pago": Nivel.APROBACION,
    "confirmar_turno": Nivel.APROBACION, "aceptar_urgente": Nivel.APROBACION, "cancelar_pedido": Nivel.APROBACION,
    "derivar_humano": Nivel.HUMANO, "responder_duda": Nivel.HUMANO, "devolver_dinero": Nivel.HUMANO,
}
#: lo que gasta plata o no tiene vuelta atrás
ETIQUETAS: dict[str, set[str]] = {
    "confirmar_pago": {"spend"}, "devolver_dinero": {"spend", "irreversible"}, "cancelar_pedido": {"irreversible"},
    "enviar_presupuesto": {"external"}, "confirmar_turno": {"external"},
}
GLOBAL = "_v1"


def acciones_de(brigada: Brigada | None) -> dict[str, ActionSpec]:
    """Las acciones de una brigada v1 como manifiesto v2: lo que declara, con el nivel de fábrica como mínimo
    de partida (como en v1), más las acciones globales que no declara."""
    propias = dict(getattr(brigada, "acciones", {}) or {}) if brigada is not None else {}
    out: dict[str, ActionSpec] = {}
    for tipo in {*GLOBALES, *propias}:
        niveles = [n for n in (GLOBALES.get(tipo), propias.get(tipo)) if n is not None]
        nivel = max(niveles, key=lambda n: Nivel(n).peso)
        out[tipo] = ActionSpec(level=Level(Nivel(nivel).value), tags=frozenset(ETIQUETAS.get(tipo, set())))
    return out


class Politicas:
    def __init__(self, perfil_politicas: dict[str, str], brigadas: list[Brigada],
                 motor: PolicyEngine | None = None) -> None:
        if motor is None:
            inst = installation_from({"id": "v1", "edition": "cloud", "autonomy": dict(perfil_politicas or {})})
            motor = PolicyEngine(inst, Store().space("_trust"))
            for b in brigadas:
                motor.register(b.nombre, acciones_de(b))
        self._m = motor
        if self._m.spec(GLOBAL, "responder_duda") is None:
            self.ignoradas = self._m.register(GLOBAL, acciones_de(None))
        else:
            self.ignoradas = []

    def nivel(self, brigada: str, tipo: str) -> Nivel:
        b = brigada if self._m.spec(brigada, tipo) is not None else GLOBAL
        return Nivel(self._m.level(b, tipo).value)

    def tabla(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for row in self._m.table():
            actual = out.get(row["action"])
            if actual is None or Nivel(row["level"]).peso > Nivel(actual).peso:
                out[row["action"]] = row["level"]
        return dict(sorted(out.items()))
