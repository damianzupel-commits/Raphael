"""Tools de la brigada: lo que usan los efímeros del jefe. Las arma `validate` (el `setup` del manifiesto).

Todas SOLO LEEN: llaman al `command` del cocinero dueño del dato (mismo código, mismos resultados). Nada de esto le escribe a un
cliente, cambia un estado, da una seña por recibida ni cancela un pedido: confirmar turnos, mandar presupuestos y links de pago,
avisar estados, dar por recibido un pago y cancelar son acciones con aprobación de la dueña (o `humano`) que siguen pidiendo los
cocineros. Cambiar el estado de un encargo y sincronizar el catálogo tampoco son tools.
"""

from __future__ import annotations

from datetime import date, datetime

from raphael_core import ActionError

from .cooks.attention import Attention
from .cooks.notices import Notices
from .cooks.orders import Orders
from .cooks.schedule import Schedule
from .cooks.store import Store
from .cooks.tasks import TaskBoard


class _ToolCtx:
    """Lo que los cocineros de empresas usan del contexto para leer: la config y los datos comunes de la brigada."""

    def __init__(self, setup_ctx) -> None:
        self.config, self.shared = setup_ctx.config, setup_ctx.shared
        self.identity = None

    @staticmethod
    def now() -> datetime:
        return datetime.now()

    @staticmethod
    def today() -> date:
        return date.today()


def make_tools(ctx) -> dict:
    tc = _ToolCtx(ctx)
    orders, schedule, store, notices, attention, board = Orders(), Schedule(), Store(), Notices(), Attention(), TaskBoard()

    def _leer(cook, name: str, data: dict | None = None):
        try:
            return cook.command(name, data or {}, tc)
        except ActionError as exc:
            return {"ok": False, "motivo": str(exc)}

    def empresas_tareas() -> list[dict]:
        """Lo que la dueña tiene que mirar hoy: encargos por vencer, turnos de hoy y mañana, señas atrasadas y el catálogo."""
        return _leer(board, "owner_tasks", {"pending": []})

    def empresas_encargos(todos: bool = False) -> list[dict]:
        """Los encargos activos (presupuesto, confirmado, en confección, prueba, listo); con `todos` también los cerrados."""
        return _leer(orders, "listar", {"all": bool(todos)})

    def empresas_encargo(number: int) -> dict:
        """Un encargo por su número."""
        return _leer(orders, "ver", {"number": number})

    def empresas_turnos() -> list[dict]:
        """Los turnos confirmados desde hoy."""
        return _leer(schedule, "turnos")

    def empresas_calendario() -> dict:
        """Los turnos confirmados agrupados por fecha."""
        return _leer(schedule, "calendario")

    def empresas_senas_esperando() -> list[dict]:
        """Las señas que todavía no llegaron."""
        return tc.shared.list("deposits", status="esperando")

    def empresas_pagos_avisados() -> list[dict]:
        """Los pagos que avisaron los clientes y la dueña todavía no confirmó."""
        return tc.shared.list("deposits", status="avisado")

    def empresas_dudas(status: str = "") -> list[dict]:
        """Las preguntas de clientes que el bot no supo responder; filtra por estado."""
        return _leer(attention, "dudas", {"status": status or None})

    def empresas_avisos_enviados() -> list[dict]:
        """Los avisos de estado que ya se les mandaron a los clientes."""
        return _leer(notices, "enviados")

    def empresas_productos(q: str = "") -> list[dict]:
        """Los productos del catálogo de la tienda; con `q` busca por texto (hasta 50)."""
        q = str(q).strip()
        return store.search(q, tc, limit=50) if q else tc.shared.list("products")[:200]

    def empresas_catalogo() -> dict:
        """El estado del catálogo de la tienda: cuándo se leyó, cuántos productos y el último error."""
        return {**(tc.shared.get("catalog_state", "state") or {}), "productos": len(tc.shared.list("products"))}

    return {f.__name__: f for f in (
        empresas_tareas, empresas_encargos, empresas_encargo, empresas_turnos, empresas_calendario, empresas_senas_esperando,
        empresas_pagos_avisados, empresas_dudas, empresas_avisos_enviados, empresas_productos, empresas_catalogo)}
