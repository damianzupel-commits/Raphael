"""Lo que el harness le ofrece a cada pieza. Es TODO lo que una pieza puede tocar.

- `Context`: el de un cocinero. Ve sus datos (`data`, subespacio "brigada/cocinero"), los de su brigada
  (`shared`), la config de su brigada, el reloj, el bus (solo los eventos que su manifiesto publica) y las
  acciones (siempre por el Policy Engine). NO ve otras brigadas: no hay forma de pedir el contexto de otra.
- `OrchestratorContext`: el del orquestador. Lee de todas las brigadas (catálogo, comandos de lectura, pendientes,
  conversaciones), usa los modelos de sus roles (`mando`, `voz`, `ruteo`), tiene su propio espacio de datos y puede
  avisar a la persona. Todo queda auditado. Nunca ejecuta: para eso está `OwnerContext`.
- `OwnerContext`: el del orquestador cuando HABLA LA PERSONA. Además de leer, aprueba, rechaza, resuelve,
  ordena comandos y escribe a un contacto. Solo existe dentro de `Runtime.talk_to_owner`; los cocineros
  nunca lo reciben.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from .contract import Action, ActionError, Cook, Level, Message, Origin, Reply
from .store import Space

if TYPE_CHECKING:  # pragma: no cover
    from .runtime import Runtime


class Context:
    def __init__(self, runtime: Runtime, brigade: str, cook: str) -> None:
        self._rt = runtime
        self.brigade = brigade
        self.cook = cook

    @property
    def piece(self) -> str:
        return f"{self.brigade}/{self.cook}"

    # --- datos y entorno
    @property
    def data(self) -> Space:
        """Los datos de este cocinero."""
        return self._rt.store.space(f"{self._rt.space_of(self.brigade)}/{self.cook}")

    @property
    def shared(self) -> Space:
        """Los datos comunes de su brigada (los ven todos sus cocineros)."""
        return self._rt.store.space(self._rt.space_of(self.brigade))

    @property
    def config(self) -> dict:
        return self._rt.installation.brigade_config(self.brigade)

    @property
    def identity(self) -> Any:
        return self._rt.installation.identity

    def now(self) -> datetime:
        return self._rt.clock()

    def today(self) -> date:
        return self._rt.clock().date()

    def mounted(self, brigade: str) -> bool:
        """¿Hay otra brigada montada con ese id? (solo saberlo; hablarle es cosa del orquestador)."""
        return brigade in self._rt.brigades

    def has_cook(self, cook: str) -> bool:
        return cook in self._rt.brigades[self.brigade].cooks

    # --- comunicación (siempre por el harness)
    def publish(self, event: str, data: dict) -> None:
        """Publica en el bus. Solo eventos declarados en `events.publishes` del manifiesto."""
        publishes = self._rt.brigades[self.brigade].manifest.events.publishes
        if event not in publishes and "*" not in publishes:
            raise ActionError(f"la brigada '{self.brigade}' no declara que publica '{event}'")
        self._rt.audit.record("evento", who=self.piece, evento=event)
        self._rt.bus.publish(event, data, source=self.piece)

    def request(self, action: Action) -> dict:
        """Pide una acción desde código sync (evento, tick). Se procesa en el loop del harness."""
        return self._rt.schedule_action(self.brigade, self.cook, action)

    async def arequest(self, action: Action) -> dict:
        """Pide una acción y espera el resultado: {'state': 'executed'|'pending'|'error', ...}."""
        return await self._rt.action(self.brigade, self.cook, action)

    async def consult(self, cook: str, msg: Message) -> Reply | None:
        """Le pasa un mensaje a OTRO cocinero de la MISMA brigada y usa su respuesta (sus acciones se procesan)."""
        if not self.has_cook(cook):
            raise ActionError(f"la brigada '{self.brigade}' no tiene el cocinero '{cook}'")
        return await self._rt.consult(self.brigade, cook, msg, by=self.piece)

    def ai(self, role: str, messages: list[dict], **kw: Any) -> str | None:
        """Texto de la IA, o None (sin modelo, falla o tope): el cocinero sigue con sus reglas.
        Va con el id de su brigada, así se aplican sus overrides y, si es privada, solo modelos locales."""
        models = self._rt.models
        return models.complete(role, messages, target=self.brigade, **kw) if models is not None else None

    def has_ai(self, role: str) -> bool:
        models = self._rt.models
        return bool(models is not None and models.available(role, target=self.brigade))

    def action_level(self, action_type: str) -> Level:
        """El nivel de autonomía que rige HOY una acción de esta brigada (el de su manifiesto, lo fijado por la
        instalación o lo que bajó la confianza progresiva). Solo lectura: para que una pieza se niegue a ejecutar
        si alguien dejó en automático algo que no debe (ej. Trading)."""
        return self._rt.policy.level(self.brigade, action_type)

    def record(self, what: str, **data: Any) -> None:
        self._rt.audit.record(what, who=self.piece, **data)


#: los roles de modelo que puede pedir el orquestador (los demás son de jefes, cocineros y efímeros)
ORCHESTRATOR_ROLES = ("mando", "voz", "ruteo")
ORCHESTRATOR_SPACE = "_orchestrator"
ORCHESTRATOR_EVENTS = frozenset({"memoria.turno"})   # lo único que el orquestador puede publicar en el bus
ORCHESTRATOR_TARGET = "orquestador"   # el id con el que van sus pedidos a la pasarela (overrides "mando.orquestador")


@dataclass(frozen=True)
class QueryResult:
    """El resultado de un comando de lectura, con el motivo si falló (para que la voz lo pueda decir)."""

    ok: bool
    value: Any = None
    error: str = ""


class OrchestratorContext:
    """Lectura de todas las brigadas, auditada. El orquestador decide; no ejecuta."""

    def __init__(self, runtime: Runtime) -> None:
        self._rt = runtime

    def now(self) -> datetime:
        return self._rt.clock()

    # --- entorno (H-8)
    @property
    def edition(self) -> str:
        return self._rt.installation.edition

    @property
    def plan(self) -> str:
        return self._rt.installation.plan

    @property
    def identity(self) -> Any:
        return self._rt.installation.identity

    def usage(self) -> dict:
        """Uso del mes (mensajes, IA, tokens, costo) y si se pasó el tope del plan (`exceeded`)."""
        return self._rt.usage.summary()

    # --- su propio espacio de datos (H-5): propuestas por confirmar, conversación, sesiones
    @property
    def data(self) -> Space:
        return self._rt.store.space(ORCHESTRATOR_SPACE)

    # --- catálogo y privacidad (H-2, H-3)
    def catalog(self) -> list[dict]:
        """Las brigadas montadas (con acciones, comandos de lectura, ruteo, si están caídas y por qué) y las que se
        pueden montar pero no están montadas. Sin datos de clientes."""
        return self._rt.catalog()

    def is_private(self, brigade: str) -> bool:
        """¿Lo de esta brigada solo puede ir a modelos locales? Si un reporte viene de una privada, mando y voz llaman
        con `private=True`."""
        return self._rt.is_private(brigade)

    # --- modelos de sus roles (H-1)
    def _role(self, role: str) -> str:
        if role not in ORCHESTRATOR_ROLES:
            raise ActionError(f"el orquestador solo usa los roles {', '.join(ORCHESTRATOR_ROLES)}; pidió '{role}'")
        return role

    def ai(self, role: str, messages: list[dict], *, private: bool = False, **kw: Any) -> str | None:
        """Texto de la IA o None (sin modelo, falla o tope): el orquestador sigue con reglas y plantillas."""
        models = self._rt.models
        if models is None:
            return None
        return models.complete(self._role(role), messages, target=ORCHESTRATOR_TARGET, private=private, **kw)

    async def aai(self, role: str, messages: list[dict], *, private: bool = False, **kw: Any) -> str | None:
        models = self._rt.models
        if models is None:
            return None
        return await models.acomplete(self._role(role), messages, target=ORCHESTRATOR_TARGET, private=private, **kw)

    def has_ai(self, role: str, *, private: bool = False) -> bool:
        models = self._rt.models
        return bool(models is not None and models.available(self._role(role), target=ORCHESTRATOR_TARGET,
                                                            private=private))

    def ai_label(self, role: str, *, private: bool = False) -> str:
        """Qué modelo usaría (para mostrarlo en el feed). Sin claves."""
        models = self._rt.models
        if models is None:
            return "sin modelo"
        return models.label(self._role(role), target=ORCHESTRATOR_TARGET, private=private)

    # --- auditoría y tablero (para el watchdog y el ruteo del orquestador)
    def record(self, what: str, **data: Any) -> None:
        """Deja constancia en la auditoría, a nombre del orquestador (ruteo, reparto, cortes del watchdog)."""
        self._rt.audit.record(what, who=ORCHESTRATOR_TARGET, **data)

    def audit_entries(self, what: str | None = None, who: str | None = None, last: int | None = None) -> list[dict]:
        """Lee la auditoría (solo lectura, ya sin secretos): para exportar el registro de tools a la introspección y
        para que el orquestador explique qué pasó. Devuelve copias: no hay forma de editarla desde acá."""
        return [dict(e) for e in self._rt.audit.entries(what=what, who=who, last=last)]

    def publish(self, event: str, data: dict) -> None:
        """Publica en el bus un evento de la lista corta `ORCHESTRATOR_EVENTS` (hoy `memoria.turno`, que Memoria
        escucha). Cualquier otro evento se rechaza: el orquestador no puede hacerse pasar por una brigada."""
        if event not in ORCHESTRATOR_EVENTS:
            raise ActionError(f"el orquestador solo puede publicar {', '.join(sorted(ORCHESTRATOR_EVENTS))}; pidió '{event}'")
        self._rt.audit.record("evento", who=ORCHESTRATOR_TARGET, evento=event)
        self._rt.bus.publish(event, data, source=ORCHESTRATOR_TARGET)

    def mark_cut(self, brigade: str, reason: str) -> None:
        """Anota en el tablero de efímeros en vivo que el orquestador cortó la corrida de esa brigada, y por qué."""
        self._rt.live.mark_cut(brigade, reason)
        self.record("corte_orquestador", brigada=brigade, motivo=reason[:200])

    # --- avisos a la persona (open loops, H-7): no ejecuta nada
    def notify(self, text: str, **data: Any) -> dict:
        """Deja un aviso para la persona (lo muestra la app) y publica `orquestador.aviso`. No ejecuta nada."""
        return self._rt.notify(text, **data)

    def brigades(self) -> dict[str, list[str]]:
        return {b: list(m.cooks) for b, m in self._rt.brigades.items() if not self._rt.is_down(b)}

    def context_for(self, cook: Cook) -> Context:
        """El contexto de un cocinero, para preguntarle `interest` o `in_progress` al ordenar."""
        b, c = self._rt.locate(cook)
        return self._rt.context(b, c)

    def pending(self, brigade: str | None = None) -> list[dict]:
        return self._rt.approvals.list(brigade=brigade)

    def conversation(self, contact: str) -> list[dict]:
        return self._rt.conversation(contact)

    async def ask(self, brigade: str, request: str, *, on_event: Any = None, context: str = "") -> Any:
        """Le pasa un pedido al jefe de una brigada; devuelve su `InternalReport` (lo traduce el orquestador)."""
        return await self._rt.ask(brigade, request, on_event=on_event, context=context)

    async def query(self, brigade: str, cook: str, command: str, data: dict | None = None) -> Any:
        """Corre un comando de lectura de un cocinero. None si no existe o falla (queda auditado)."""
        return (await self.query_detail(brigade, cook, command, data)).value

    async def query_detail(self, brigade: str, cook: str, command: str, data: dict | None = None) -> QueryResult:
        """Como `query`, pero con el motivo si falla (no declarado, no es de lectura, brigada caída, error) (H-9)."""
        self._rt.audit.record("consulta_orquestador", who="orquestador", brigada=brigade, cocinero=cook,
                              comando=command)
        if brigade in self._rt.brigades and self._rt.is_down(brigade):
            return QueryResult(False, None, f"la brigada '{brigade}' está caída")
        try:
            return QueryResult(True, await self._rt.command(brigade, cook, command, data, who="orquestador"))
        except ActionError as exc:
            return QueryResult(False, None, str(exc) or type(exc).__name__)


class OwnerContext(OrchestratorContext):
    """Cuando habla la persona dueña: puede ordenar. Cada orden queda en la auditoría con su nombre."""

    def __init__(self, runtime: Runtime, who: str, *, session: str | None = None, channel: str | None = None,
                 on_event: Callable[[dict], Any] | None = None) -> None:
        super().__init__(runtime)
        self.who = who
        self.session = session or "default"   # una charla de la persona (app, WhatsApp de la dueña, voz)
        self.channel = channel                # por dónde habla, si se sabe
        self._on_event = on_event

    @property
    def drafts(self) -> Any:
        """El almacén de brigadas por borrador (H-15), si el cargador tiene uno; si no, None. SOLO existe acá, cuando habla
        la persona: activar un borrador es una orden suya sobre el hash que revisó, nunca algo que decide un modelo."""
        loader = getattr(self._rt, "loader", None)
        return getattr(loader, "drafts", None) if loader is not None else None

    async def emit(self, event: dict) -> None:
        """Manda un evento al feed de quien llamó (la app lo muestra en vivo). Sin feed no hace nada (H-6).
        Un feed que falla no corta la charla."""
        if self._on_event is None:
            return
        try:
            out = self._on_event(event)
            if inspect.isawaitable(out):
                await out
        except Exception as exc:  # noqa: BLE001 - el feed es de la app; la charla sigue
            self._rt.audit.record("feed_fallido", who="orquestador", error=repr(exc)[:200])

    async def approve(self, pid: int, changes: dict | None = None) -> dict:
        return await self._rt.approve(pid, changes, who=self.who)

    async def reject(self, pid: int, reason: str = "") -> dict:
        return await self._rt.reject(pid, reason, who=self.who)

    async def resolve(self, pid: int, reply: str | None = None) -> dict:
        return await self._rt.resolve(pid, reply, who=self.who)

    async def order(self, brigade: str, cook: str, command: str, data: dict | None = None) -> Any:
        return await self._rt.command(brigade, cook, command, data, who=self.who)

    async def act(self, brigade: str, cook: str, action: Action) -> dict:
        """Una acción que pide la persona: pasa por el Policy Engine con origen `owner`."""
        action.origin = Origin.OWNER
        return await self._rt.action(brigade, cook, action)

    def write(self, contact: str, text: str) -> None:
        self._rt.audit.record("orden_duena", who=self.who, orden="escribir", contacto=contact)
        self._rt.send(contact, text)
