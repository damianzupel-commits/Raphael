"""Policy Engine: decide si una acción se ejecuta sola, espera aprobación o pasa a una persona.

Nivel efectivo = el MÁS estricto entre: el nivel global conocido, el que declara la brigada y
el que pide el perfil. El perfil puede endurecer, nunca relajar.
"""

from __future__ import annotations

from .contrato import Brigada, Nivel

#: niveles globales de las acciones conocidas (sección 6 del contexto del producto)
GLOBALES: dict[str, Nivel] = {
    "anotar_duda": Nivel.AUTO,
    "avisar_estado": Nivel.AUTO,
    "enviar_recordatorio": Nivel.AUTO,
    "registrar_dato": Nivel.AUTO,
    "enviar_presupuesto": Nivel.APROBACION,
    "confirmar_pago": Nivel.APROBACION,
    "confirmar_turno": Nivel.APROBACION,
    "aceptar_urgente": Nivel.APROBACION,
    "cancelar_pedido": Nivel.APROBACION,
    "derivar_humano": Nivel.HUMANO,
    "responder_duda": Nivel.HUMANO,
    "devolver_dinero": Nivel.HUMANO,
}
#: acción desconocida para todos: por seguridad, se aprueba
DESCONOCIDA = Nivel.APROBACION


def _max(*niveles: Nivel | None) -> Nivel:
    return max((n for n in niveles if n is not None), key=lambda n: n.peso)


class Politicas:
    def __init__(self, perfil_politicas: dict[str, str], brigadas: list[Brigada]) -> None:
        self._perfil = {k: Nivel(v) for k, v in perfil_politicas.items()}
        self._brigadas = {b.nombre: dict(b.acciones) for b in brigadas}
        self.ignoradas: list[str] = []
        for tipo, pedido in self._perfil.items():
            base = self._base(tipo)
            if pedido.peso < base.peso:
                self.ignoradas.append(f"'{tipo}': el perfil pide {pedido.value} pero el mínimo es {base.value}")

    def _base(self, tipo: str, brigada: str | None = None) -> Nivel:
        declarados = [self._brigadas.get(brigada, {}).get(tipo)] if brigada else [a.get(tipo) for a in self._brigadas.values()]
        conocidos = [GLOBALES.get(tipo), *declarados]
        if all(n is None for n in conocidos):
            return DESCONOCIDA
        return _max(*conocidos)

    def nivel(self, brigada: str, tipo: str) -> Nivel:
        return _max(self._base(tipo, brigada), self._perfil.get(tipo))

    def tabla(self) -> dict[str, str]:
        tipos = set(GLOBALES) | {t for a in self._brigadas.values() for t in a} | set(self._perfil)
        return {t: _max(self._base(t), self._perfil.get(t)).value for t in sorted(tipos)}
