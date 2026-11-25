"""El harness v2 en marcha: el único camino entre las brigadas y el mundo.

- Los mensajes entran por `receive`: el orquestador (o el orden simple) decide qué cocineros los ven y el
  primero que responde se queda con el mensaje. Un cocinero que falla NO tumba el mensaje: pasa al siguiente.
- Toda acción pasa por el Policy Engine (`automatico` se ejecuta; `aprobacion` y `humano` quedan pendientes).
- Aprobar, rechazar y resolver alimentan la confianza progresiva.
- Montar y desmontar brigadas en caliente (`mount` / `unmount`). El cargador que las descubre por
  manifiesto llega en H5; acá se les pasan los cocineros ya instanciados.
- Todo queda en la auditoría. `status()` no muestra datos de clientes.

Async por dentro; los cocineros pueden ser sync o async. Para código sync (tests, scripts) está `run()`.
Portado de `raphael_harness.harness` (Empresas 0.4), con aislamiento de fallos y sin pisos.
"""

from __future__ import annotations

import asyncio
import contextvars
import inspect
import re
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any, Protocol, TypeVar

from . import __version__
from .approvals import Approvals
from .audit import AuditLog
from .context import Context, OrchestratorContext, OwnerContext
from .contract import (
    CONTRACT_VERSION,
    Action,
    ActionError,
    Cook,
    Level,
    Message,
    Orchestrator,
    Origin,
    OwnerReply,
    Reply,
    Trust,
)
from .engine import BrigadeSpec, Chief, ChiefSettings, Helper, InternalReport, LiveBoard
from .engine import reports as _reports
from .events import EventBus
from .installation import Installation
from .isolation import Guard
from .manifest import ActionSpec, CookSpec, Manifest
from .models import ModelGateway, Usage
from .policy import PolicyEngine
from .store import Space, Store
from .text_es import clean
from .tools import Tool, ToolRegistry, parameters_of

HARNESS = "_harness"
T = TypeVar("T")
_capture: contextvars.ContextVar[tuple[str, list[str]] | None] = contextvars.ContextVar("raphael_capture",
                                                                                         default=None)
#: pendientes que abre la compuerta de tools durante un `ask` (para atar las propuestas del reporte a ids reales, H-4)
_asked: contextvars.ContextVar[list[dict] | None] = contextvars.ContextVar("raphael_asked", default=None)
#: la charla en curso (sesión de quien le habla al orquestador): la auditoría de tools la guarda como `conv_id`
_conversation: contextvars.ContextVar[str | None] = contextvars.ContextVar("raphael_conversation", default=None)
ORCH = "orquestador"


class MountError(RuntimeError):
    """La brigada no se puede montar así (contrato, edición, cocineros que no coinciden)."""


#: decisiones del 22 nov 2026 (Damián)
CHIEF_MAX_FAILURES = 5                 # errores seguidos del jefe (no reportes degradados) -> jefe caído; vuelve a mano
HEALTH_EVERY = timedelta(minutes=5)    # el healthcheck del manifiesto corre al montar y cada 5 min (con el tick)
HEALTH_DOWN_AFTER = 3                  # chequeos malos seguidos -> la brigada deja de recibir; vuelve sola al dar bien
HEALTH_TIMEOUT = 30.0


class Connector(Protocol):
    """Canal de salida (WhatsApp, Instagram, panel…)."""

    def send(self, recipient: str, text: str) -> None: ...


@dataclass
class Mounted:
    manifest: Manifest
    cooks: dict[str, Cook]
    specs: dict[str, CookSpec]
    chief: Chief | None = None
    chief_failures: int = 0
    chief_down: str | None = None
    health_fn: Callable[..., Any] | None = None
    health: dict = field(default_factory=lambda: {"ok": None, "detail": "", "fails": 0, "down": False, "at": None})
    health_last: datetime | None = None


class SetupContext:
    """Lo que recibe la función `setup` del manifiesto al montar: registrar las tools que no tienen `entry`."""

    def __init__(self, runtime: Runtime, manifest: Manifest, notes: list[str]) -> None:
        self._rt, self.manifest, self._notes = runtime, manifest, notes
        self.registered: list[str] = []

    @property
    def edition(self) -> str:
        return self._rt.installation.edition

    @property
    def config(self) -> dict:
        return self._rt.installation.brigade_config(self.manifest.id)

    @property
    def shared(self) -> Space:
        """Los datos comunes de la brigada (los mismos que ven sus cocineros en `ctx.shared`)."""
        return self._rt.store.space(self.manifest.space)

    def register_tool(self, name: str, fn: Callable[..., Any], description: str = "",
                      parameters: dict | None = None) -> bool:
        """Registra una tool de la brigada. True si quedó cargada.

        Declarada en el manifiesto: toma de ahí su nivel y etiquetas. NO declarada (decisión del 22 nov): se acepta con
        aviso y pide aprobación en cada uso; en la nube se rechaza, porque no se puede saber si es peligrosa."""
        bid = self.manifest.id
        if not isinstance(name, str) or not re.match(r"^[a-z][a-z0-9_]{0,59}$", name) or not callable(fn):
            raise MountError(f"{bid}: setup quiso registrar una tool inválida: {name!r}")
        spec = next((t for t in self.manifest.tools if t.name == name), None)
        if spec is not None and spec.entry is not None:
            raise MountError(f"{bid}: la tool '{name}' ya se carga por su entry; setup no la puede registrar de nuevo")
        if spec is not None and spec not in self.manifest.tools_for(self.edition):
            self._notes.append(f"{bid}: la tool '{name}' no se carga en la edición {self.edition}")
            return False
        if spec is None and self.edition == "cloud":
            self._notes.append(f"{bid}: setup quiso registrar '{name}', que no está en el manifiesto: en la nube se "
                               "rechaza")
            return False
        prev = self._rt.tools.get(name)
        if prev is not None and prev.owner != bid:
            raise MountError(f"{bid}: ya hay una tool '{name}' de {prev.owner or 'uso compartido'}")
        self._rt.tools.register(Tool(name, fn, description or (spec.description if spec else "")
                                     or (inspect.getdoc(fn) or "").split("\n")[0],
                                     parameters if parameters is not None else parameters_of(fn), spec=spec, owner=bid))
        if spec is None:
            self._notes.append(f"{bid}: la tool '{name}' no está declarada en el manifiesto: se cargó y pide aprobación "
                               "en cada uso")
        self.registered.append(name)
        return True


class Runtime:
    def __init__(self, installation: Installation, *, store: Store | None = None,
                 clock: Callable[[], datetime] | None = None, orchestrator: Orchestrator | None = None,
                 connectors: dict[str, Connector] | None = None, models: ModelGateway | None = None,
                 max_failures: int = 3, timeout: float = 60.0, tools: ToolRegistry | None = None,
                 chief_settings: ChiefSettings | None = None) -> None:
        self.installation = installation
        self.clock = clock or datetime.now
        self.store = store or Store(":memory:", clock=self.clock)
        self.audit = AuditLog(self.store.space("_audit"), self.clock)
        self._sys = self.store.space(HARNESS)
        self.approvals = Approvals(self._sys, self.clock)
        self.policy = PolicyEngine(installation, self.store.space("_trust"),
                                   on_change=lambda what, **d: self.audit.record(what, **d))
        self.bus = EventBus(on_error=lambda owner, ev, exc: self.audit.record(
            "evento_fallido", who=owner, evento=ev, error=repr(exc)[:200]))
        self.guard = Guard(max_failures=max_failures, default_timeout=timeout, passthrough=(ActionError,),
                           on_down=lambda piece, why: self.audit.record("pieza_caida", who=piece, why=why))
        self.orchestrator: Orchestrator | None = None
        self.loader: Any = None   # lo engancha el Loader: el catálogo suma lo que se puede montar y no está montado
        self.connectors = connectors or {}
        self.usage = models.usage if models is not None else Usage(
            self.store.space("_uso"), installation.limits.messages_month, self.clock)
        self.models = models
        self.tools = tools or ToolRegistry(installation.edition)
        self.chief_settings = chief_settings or ChiefSettings()
        self.live = LiveBoard()
        self.brigades: dict[str, Mounted] = {}
        self.warnings: list[str] = []
        self._contexts: dict[tuple[str, str], Context] = {}
        self._index: dict[int, tuple[str, str]] = {}
        self._tasks: set[asyncio.Task] = set()
        self.audit.record("inicio", core=__version__, contrato=CONTRACT_VERSION, edicion=installation.edition)
        if orchestrator is not None:
            self.set_orchestrator(orchestrator)

    # --- el orquestador (H-7, H-12) --------------------------------------------------------------------------------------
    def set_orchestrator(self, orchestrator: Orchestrator | None, config: dict | None = None) -> None:
        """Pone (o saca, con None) el orquestador: le pasa su config y lo suscribe a los eventos que nombra `consumes`.
        Los eventos `orquestador.*` (los suyos) no le llegan, para que no se escuche a sí mismo."""
        self.bus.unsubscribe(ORCH)
        self.orchestrator = orchestrator
        if orchestrator is None:
            self.audit.record("orquestador_quitado", who="harness")
            return
        if config is not None:
            orchestrator.configure(dict(config))
        for ev in getattr(orchestrator, "consumes", ()) or ():
            self.bus.subscribe(ev, self._orchestrator_handler, owner=ORCH)
        self.audit.record("orquestador_montado", who="harness", nombre=orchestrator.name, version=orchestrator.version,
                          escucha=list(getattr(orchestrator, "consumes", ()) or ()))

    async def _call_orchestrator(self, method: str, *args: Any) -> Any:
        fn = getattr(self.orchestrator, method, None)
        if fn is None:
            return None
        try:
            out = fn(*args)
            if inspect.isawaitable(out):
                out = await out
            return out
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - un orquestador roto no tumba al harness
            self.audit.record("orquestador_fallido", who=ORCH, metodo=method, error=repr(exc)[:200])
            return None

    async def _orchestrator_handler(self, event: str, data: dict) -> None:
        if event.startswith(ORCH + ".") or self.orchestrator is None:
            return
        await self._call_orchestrator("on_event", event, data, OrchestratorContext(self))

    def notify(self, text: str, **data: Any) -> dict:
        """Un aviso del orquestador para la persona. Queda guardado (la app lo muestra), auditado y publicado."""
        sp = self.store.space("_orchestrator")
        n = sp.next("notices")
        doc = sp.put("notices", n, {"id": n, "text": clean(text, 600), "data": data,
                                    "when": self.clock().isoformat(timespec="seconds"), "seen": False})
        self.audit.record("aviso_orquestador", who=ORCH, id=n, texto=clean(text, 200))
        self.bus.publish("orquestador.aviso", {"id": n, "text": doc["text"]}, source=ORCH)
        return doc

    def notices(self, unseen_only: bool = False) -> list[dict]:
        out = self.store.space("_orchestrator").list("notices")
        return [x for x in out if not (unseen_only and x.get("seen"))]

    # --- catálogo y privacidad (H-2, H-3) -------------------------------------------------------------------------------
    def is_private(self, brigade: str) -> bool:
        m = self.brigades.get(brigade)
        if m is not None and m.chief is not None and m.chief.spec.private:
            return True
        return bool(self.models is not None and brigade in self.models.config.private)

    def down_reason(self, brigade: str) -> str | None:
        """Por qué una brigada montada no atiende, o None si atiende."""
        m = self.brigades.get(brigade)
        if m is None:
            return "no está montada"
        if m.health["down"]:
            return f"su chequeo de salud dio mal {m.health['fails']} veces seguidas ({m.health['detail'][:120]})"
        if not m.cooks:
            if m.chief is None:
                return "no tiene cocineros ni jefe"
            return f"el jefe está caído ({m.chief_down[:140]})" if m.chief_down else None
        if all(self.guard.is_down(f"{brigade}/{c}") for c in m.cooks):
            return "todos sus cocineros están caídos"
        return None

    @staticmethod
    def _cooks_for(m: Mounted, command: str) -> list[str]:
        """Qué cocineros atienden un comando: los que lo nombran en su `commands`; si ninguno lo nombra, todos."""
        named = [cid for cid, cook in m.cooks.items() if command in (getattr(cook, "commands", None) or {})]
        return named or list(m.cooks)

    def _watch_of(self, m: Mounted) -> dict | None:
        """Lo que el watchdog del orquestador tiene que saber de un jefe: su `WatchSpec` y el timeout de sus efímeros."""
        if m.chief is None:
            return None
        w = m.chief.spec.watch
        return {"helper_timeout": float(m.chief.spec.helper_timeout or self.chief_settings.helper_timeout),
                "max_seconds": w.max_seconds if w else None, "stall_seconds": w.stall_seconds if w else None,
                "max_repeats": w.max_repeats if w else None, "max_errors": w.max_errors if w else None}

    def catalog(self) -> list[dict]:
        """Lo que el orquestador necesita saber de cada brigada, sin datos de clientes: montadas primero, después las
        que se pueden montar (si hay un Loader enganchado)."""
        out = []
        for bid, m in sorted(self.brigades.items()):
            mf = m.manifest
            reason = self.down_reason(bid)
            out.append({
                "id": bid, "name": mf.name, "description": mf.description, "version": mf.version, "mounted": True,
                "chief": m.chief is not None, "chief_purpose": m.chief.spec.purpose if m.chief else "",
                "cooks": {c: ("caído" if self.guard.is_down(f"{bid}/{c}") else "ok") for c in m.cooks},
                "actions": {a: {"level": spec.level.value, "tags": sorted(spec.tags), "description": spec.description}
                            for a, spec in sorted(mf.actions.items())},
                "read_commands": {c: spec.description for c, spec in sorted(mf.commands.items()) if spec.read},
                "commands": {c: {"read": spec.read, "description": spec.description, "cooks": self._cooks_for(m, c)}
                             for c, spec in sorted(mf.commands.items())},
                "routing": mf.routing.model_dump(mode="json"),
                "private": self.is_private(bid), "down": reason is not None, "down_reason": reason,
                "watch": self._watch_of(m),
            })
        if self.loader is not None:
            try:
                for f in self.loader.catalog():
                    if not f["mounted"]:
                        out.append({"id": f["id"], "name": f["name"], "description": f["description"],
                                    "version": f["version"], "mounted": False, "active": f["active"],
                                    "chief": f["chief"], "error": f.get("error")})
            except Exception as exc:  # noqa: BLE001 - sin el catálogo del cargador, quedan las montadas
                self.audit.record("catalogo_fallido", who="harness", error=repr(exc)[:200])
        return out

    # --- utilidades ----------------------------------------------------------------------------------------------------
    @staticmethod
    def run(coro: Coroutine[Any, Any, T]) -> T:
        """Corre una operación async desde código sync (tests, scripts). No usar dentro de un loop."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        coro.close()
        raise RuntimeError("Runtime.run() no se usa dentro de un loop: hacé `await` directamente")

    def context(self, brigade: str, cook: str) -> Context:
        key = (brigade, cook)
        if key not in self._contexts:
            self._contexts[key] = Context(self, brigade, cook)
        return self._contexts[key]

    def space_of(self, brigade: str) -> str:
        return self.brigades[brigade].manifest.space

    def locate(self, cook: Cook) -> tuple[str, str]:
        return self._index[id(cook)]

    def is_down(self, brigade: str) -> bool:
        m = self.brigades.get(brigade)
        if m is None or m.health["down"]:
            return True
        if not m.cooks:
            return m.chief is None or m.chief_down is not None
        return all(self.guard.is_down(f"{brigade}/{c}") for c in m.cooks)

    def _call(self, brigade: str, cook: str, method: str, *args: Any, timeout: float | None = None):
        m = self.brigades[brigade]
        fn = getattr(m.cooks[cook], method)
        return self.guard.call(f"{brigade}/{cook}", fn, *args, timeout=timeout, blocking=m.specs[cook].blocking,
                               label=method)

    def _is_sync(self, brigade: str, cook: str, method: str) -> bool:
        m = self.brigades[brigade]
        fn = getattr(m.cooks[cook], method)
        return not inspect.iscoroutinefunction(fn) and not m.specs[cook].blocking

    def _call_sync(self, brigade: str, cook: str, method: str, *args: Any):
        fn = getattr(self.brigades[brigade].cooks[cook], method)
        return self.guard.call_sync(f"{brigade}/{cook}", fn, *args, label=method)

    async def _settle(self) -> None:
        """Espera las acciones agendadas desde código sync y los eventos async, y las que esas agenden."""
        while self._tasks or self.bus._pending:  # noqa: SLF001
            if self._tasks:
                await asyncio.gather(*list(self._tasks))
            await self.bus.drain()

    # --- montar y desmontar --------------------------------------------------------------------------------------------
    async def mount(self, manifest: Manifest, cooks: dict[str, Cook] | None = None, *, chief: BrigadeSpec | None = None,
                    tools: list[Tool] | tuple[Tool, ...] = (), setup: Callable[..., Any] | None = None,
                    health: Callable[..., Any] | None = None) -> list[str]:
        """Monta una brigada con sus cocineros ya instanciados, su jefe (BrigadeSpec) y sus tools.

        Devuelve avisos (config de autonomía que no se aplica, tools que no entran en esta edición, efímeros con tools
        sin cargar)."""
        cooks = cooks or {}
        bid = manifest.id
        if bid in self.brigades:
            raise MountError(f"la brigada '{bid}' ya está montada")
        if not manifest.supports_contract():
            raise MountError(f"la brigada '{bid}' pide el contrato {manifest.contract}; el núcleo es {CONTRACT_VERSION}")
        if self.installation.edition not in manifest.editions:
            raise MountError(f"la brigada '{bid}' no corre en la edición {self.installation.edition}")
        declared = {c.id for c in manifest.cooks}
        if set(cooks) != declared:
            raise MountError(f"la brigada '{bid}': cocineros declarados {sorted(declared)}, recibidos {sorted(cooks)}")
        if (manifest.chief is None) != (chief is None):
            raise MountError(f"la brigada '{bid}': el manifiesto {'declara' if manifest.chief else 'no declara'} jefe y "
                             f"{'no ' if chief is None else ''}se pasó su BrigadeSpec")
        if chief is not None and chief.id != bid:
            raise MountError(f"la brigada '{bid}': el BrigadeSpec es de '{chief.id}'")
        tool_specs = {t.name: t for t in manifest.tools}
        allowed = {t.name for t in manifest.tools_for(self.installation.edition)}
        notes: list[str] = []
        to_register: list[Tool] = []
        for t in tools:
            if t.name not in tool_specs:
                raise MountError(f"la brigada '{bid}': la tool '{t.name}' no está declarada en el manifiesto")
            if t.name not in allowed:
                notes.append(f"{bid}: la tool '{t.name}' no se carga en la edición {self.installation.edition}")
                continue
            prev = self.tools.get(t.name)
            if prev is not None and prev.owner != bid:
                raise MountError(f"la brigada '{bid}': ya hay una tool '{t.name}' de {prev.owner or 'uso compartido'}")
            to_register.append(replace(t, spec=tool_specs[t.name], owner=bid))
        m = Mounted(manifest, dict(cooks), {c.id: c for c in manifest.cooks}, health_fn=health)
        self.brigades[bid] = m
        for t in to_register:
            self.tools.register(t)
        for cid, cook in m.cooks.items():
            self._index[id(cook)] = (bid, cid)
        if setup is not None:
            try:
                res = setup(SetupContext(self, manifest, notes))
                if inspect.isawaitable(res):
                    await res
            except Exception as exc:  # noqa: BLE001 - sin sus tools la brigada no queda a medias: no se monta
                self.tools.unregister_owner(bid)
                for cook in m.cooks.values():
                    self._index.pop(id(cook), None)
                del self.brigades[bid]
                raise MountError(f"la brigada '{bid}': su setup falló: {type(exc).__name__}: {exc}") from exc
        missing_declared = sorted(t.name for t in manifest.tools_for(self.installation.edition)
                                  if self.tools.get(t.name) is None)
        if missing_declared:
            notes.append(f"{bid}: tools declaradas que nadie cargó: {', '.join(missing_declared)}")
        actions = {**manifest.actions, **{f"tool_{t.name}": ActionSpec(level=t.level, tags=t.tags, description=t.description)
                                          for t in manifest.tools}}
        notes += self.policy.register(bid, actions)
        if chief is not None:
            m.chief = self._make_chief(chief, manifest)
            for h in chief.helpers:
                missing = sorted(n for n in h.tools if self.tools.get(n) is None)
                if missing:
                    notes.append(f"{bid}: el efímero {h.id} tiene tools sin cargar: {', '.join(missing)}")
        self.warnings += notes
        for cid in m.cooks:
            for ev in manifest.events.consumes:
                self.bus.subscribe(ev, self._event_handler(bid, cid), owner=f"{bid}/{cid}")
        for cid in m.cooks:
            out = await self._call(bid, cid, "start", self.context(bid, cid))
            if not out.ok:
                self.guard.mark_down(f"{bid}/{cid}", f"no arrancó: {out.reason}")
        if health is not None:
            await self.check_health(bid)
        self.audit.record("brigada_montada", who="harness", brigada=bid, version=manifest.version,
                          cocineros=sorted(m.cooks), avisos=notes)
        await self.bus.apublish("brigada.montada", {"brigade": bid}, source="harness")
        await self._settle()
        return notes

    async def unmount(self, brigade: str, export: bool = True) -> dict:
        """Desmonta: para sus cocineros, saca sus suscripciones, exporta y purga lo que diga su manifiesto."""
        m = self.brigades.get(brigade)
        if m is None:
            raise MountError(f"la brigada '{brigade}' no está montada")
        for cid in m.cooks:
            await self._call(brigade, cid, "stop", self.context(brigade, cid))
            self.bus.unsubscribe(f"{brigade}/{cid}")
            self.guard.forget(f"{brigade}/{cid}")
        space = self.store.space(m.manifest.space)
        wanted = m.manifest.uninstall.export
        exported = space.export(list(wanted) if wanted else None) if export else {}
        purged = space.purge(list(m.manifest.uninstall.delete)) if m.manifest.uninstall.delete else 0
        self.policy.unregister(brigade)
        self.tools.unregister_owner(brigade)
        for cook in m.cooks.values():
            self._index.pop(id(cook), None)
        for key in [k for k in self._contexts if k[0] == brigade]:
            del self._contexts[key]
        del self.brigades[brigade]
        self.audit.record("brigada_desmontada", who="harness", brigada=brigade, exportado=bool(exported),
                          borrados=purged)
        await self.bus.apublish("brigada.desmontada", {"brigade": brigade}, source="harness")
        await self._settle()
        return exported

    def _event_handler(self, brigade: str, cook: str) -> Callable[[str, dict], Any]:
        if self._is_sync(brigade, cook, "on_event"):
            def sync_handler(event: str, data: dict) -> None:   # entrega inmediata, como en Empresas
                if brigade not in self.brigades:
                    return
                out = self._call_sync(brigade, cook, "on_event", event, data, self.context(brigade, cook))
                if not out.ok and not out.skipped:
                    self.audit.record("evento_fallido", who=f"{brigade}/{cook}", evento=event, error=out.reason[:200])
            return sync_handler

        async def handler(event: str, data: dict) -> None:
            if brigade not in self.brigades:
                return
            out = await self._call(brigade, cook, "on_event", event, data, self.context(brigade, cook))
            if not out.ok and not out.skipped:
                self.audit.record("evento_fallido", who=f"{brigade}/{cook}", evento=event, error=out.reason[:200])
        return handler

    # --- jefes, efímeros y tools ----------------------------------------------------------------------------------------
    CHIEF_COOK = "_jefe"   # el "cocinero" que figura en los pendientes que abre una tool de un efímero

    def _label(self, spec: BrigadeSpec, role: str, target: str | None) -> str:
        if self.models is None:
            return "sin modelo"
        private = spec.private
        if role != "jefe" and target:
            private = private or any(h.private for h in spec.helpers if h.id == target)
        return self.models.label(role, target=target, private=private)

    def _make_chief(self, spec: BrigadeSpec, manifest: Manifest) -> Chief:
        models = self.models
        identity = self.installation.identity.model_dump()

        async def think(messages: list[dict], phase: str) -> str | None:
            if models is None:
                return None
            return await models.acomplete("jefe", messages, target=spec.id, private=spec.private, max_tokens=1500,
                                          temperature=0.1)

        def spawn(hs) -> Helper:
            async def chat(messages: list[dict], tools: list[dict] | None) -> dict | None:
                if models is None:
                    return None
                return await models.achat("efimero", messages, tools=tools, target=hs.id,
                                          private=spec.private or hs.private)
            box = self.tools.box(hs.tools, brigade=spec.id, gate=self._tool_gate(spec.id))
            return Helper(hs, spec, chat=chat, toolbox=box, identity=identity)

        return Chief(spec, think=think, spawn=spawn, memory=self.store.space(manifest.space), live=self.live,
                     labels=lambda role, target: self._label(spec, role, target), settings=self.chief_settings)

    def _tool_gate(self, brigade: str):
        async def gate(tool: Tool, args: dict) -> dict | None:
            key = f"tool_{tool.name}"
            if self.policy.spec(brigade, key) is None and tool.spec is not None:   # tool compartida con nivel declarado
                self.policy.declare(brigade, key, ActionSpec(level=tool.spec.level, tags=tool.spec.tags))
            decision = self.policy.decide(brigade, key)
            if decision.level is Level.AUTO:
                self.audit.record("tool", who=brigade, tool=tool.name, arguments=dict(args), conv_id=_conversation.get())
                return None
            action = Action(type=key, data=dict(args), summary=f"Usar la tool {tool.name}")
            p = self._new_pending(brigade, self.CHIEF_COOK, decision.level, action.summary, action, decision.explain(),
                                  kind="tool", data={"tool": tool.name, "conv_id": _conversation.get()})
            asked = _asked.get()
            if asked is not None:
                asked.append(p)
            who = self.installation.identity.user or "una persona"
            return {"status": "pending_approval", "pending_id": p["id"], "level": decision.level.value,
                    "message": f"No se ejecutó: queda pendiente #{p['id']} hasta que lo apruebe {who}."}
        return gate

    async def _run_tool(self, p: dict, action: Action) -> dict:
        name = p["data"].get("tool", "")
        tool = self.tools.get(name)
        if tool is None:
            return {"state": "error", "error": f"la tool {name} ya no está cargada"}
        conv = p["data"].get("conv_id")
        m = self.brigades.get(p["brigade"])        # lo aprobado también se ve «en curso» mientras corre (puede tardar minutos)
        args = ", ".join(f"{k}={v}" for k, v in list(action.data.items())[:3])
        token = self.live.start(p["brigade"], m.manifest.name if m else p["brigade"], f"tool:{name}", "tool", "",
                                f"#{p['id']} {name} {args}".strip())
        try:
            result = await tool.run(dict(action.data))
        except Exception as exc:  # noqa: BLE001 - la falla vuelve como resultado; el pendiente sigue abierto
            self.live.finish(token, "error", str(exc)[:160])
            self.audit.record("tool_fallida", who=p["brigade"], tool=name, error=repr(exc)[:200],
                              arguments=dict(action.data), conv_id=conv)
            return {"state": "error", "error": str(exc) or type(exc).__name__}
        self.live.finish(token, "ok")
        self.audit.record("tool", who=p["brigade"], tool=name, arguments=dict(action.data), conv_id=conv)
        await self.bus.apublish("tool.ejecutada", {"id": p["id"], "tool": name, "brigade": p["brigade"]}, source="harness")
        return {"state": "executed", "result": result}

    async def ask(self, brigade: str, request: str, *, on_event: Callable[[dict], Any] | None = None,
                  context: str = "") -> InternalReport:
        """Le pasa un pedido al JEFE de una brigada y devuelve su reporte interno (nunca un mensaje para la persona).

        Un jefe que revienta no tumba al runtime: vuelve un reporte degradado que lo dice."""
        m = self.brigades.get(brigade)
        if m is None or m.chief is None:
            raise ActionError(f"la brigada '{brigade}' no está montada o no tiene jefe")
        self.audit.record("pedido_brigada", who="orquestador", brigada=brigade, pedido=request[:200])
        if m.health["down"]:
            return _reports.degraded_report(brigade, [], "la brigada está caída por su chequeo de salud ("
                                            f"{m.health['detail'][:120]}); vuelve sola cuando dé bien")
        if m.chief_down:
            return _reports.degraded_report(brigade, [], f"el jefe está caído ({m.chief_down[:140]}); revivilo desde "
                                            "el panel o volvé a montar la brigada")
        token = _asked.set([])
        try:
            report = await m.chief.run(request, on_event=on_event, context=context)
            m.chief_failures = 0
        except asyncio.CancelledError:
            _asked.reset(token)
            raise
        except Exception as exc:  # noqa: BLE001
            m.chief_failures += 1
            self.audit.record("jefe_fallido", who=brigade, error=repr(exc)[:200], seguidas=m.chief_failures)
            report = _reports.degraded_report(brigade, [], f"el jefe falló ({type(exc).__name__}: {str(exc)[:120]})")
            if m.chief_failures >= CHIEF_MAX_FAILURES:
                m.chief_down = f"{m.chief_failures} errores seguidos; el último: {type(exc).__name__}: {str(exc)[:120]}"
                self.audit.record("pieza_caida", who=f"{brigade}/jefe", why=m.chief_down)
                await self.bus.apublish("brigada.jefe_caido", {"brigade": brigade, "why": m.chief_down},
                                        source="harness")
        opened = [p for p in (_asked.get() or []) if p.get("brigade") == brigade]
        _asked.reset(token)
        report = _reports.attach_pending(report, opened)   # las propuestas llevan el número REAL del pendiente
        self.audit.record("reporte_brigada", who=brigade, degradado=report.degraded, confianza=report.confidence)
        await self.bus.apublish("brigada.reporte", {"brigade": brigade, "summary": report.summary,
                                                     "degraded": report.degraded}, source="harness")
        await self._settle()
        return report

    def revive_chief(self, brigade: str) -> None:
        """Vuelve a habilitar un jefe caído (lo hace la persona desde el panel; también se resetea al re-montar)."""
        m = self.brigades.get(brigade)
        if m is None or m.chief is None:
            raise ActionError(f"la brigada '{brigade}' no está montada o no tiene jefe")
        m.chief_failures, m.chief_down = 0, None
        self.audit.record("pieza_revivida", who=f"{brigade}/jefe")

    # --- salud ------------------------------------------------------------------------------------------------------------
    async def check_health(self, brigade: str) -> dict:
        """Corre el healthcheck del manifiesto. 3 malos seguidos -> la brigada deja de recibir; vuelve al dar bien."""
        m = self.brigades.get(brigade)
        if m is None or m.health_fn is None:
            return {}
        ctx = self.context(brigade, next(iter(m.cooks), "_brigada"))
        try:
            res = m.health_fn(ctx)
            if inspect.isawaitable(res):
                res = await asyncio.wait_for(res, timeout=HEALTH_TIMEOUT)
            ok, detail = bool(getattr(res, "ok", res)), str(getattr(res, "detail", "") or "")
        except Exception as exc:  # noqa: BLE001 - un healthcheck que explota es un chequeo malo
            ok, detail = False, f"{type(exc).__name__}: {exc}"[:300]
        h = m.health
        m.health_last = self.clock()
        h.update(ok=ok, detail=detail, at=m.health_last.isoformat(timespec="seconds"))
        if ok:
            if h["down"]:
                self.audit.record("brigada_sana", who=brigade, why=detail or "el chequeo volvió a dar bien")
                await self.bus.apublish("brigada.salud", {"brigade": brigade, "ok": True, "down": False}, source="harness")
            h.update(fails=0, down=False)
            return dict(h)
        h["fails"] += 1
        self.audit.record("salud_mala", who=brigade, why=detail, seguidas=h["fails"])
        if h["fails"] >= HEALTH_DOWN_AFTER and not h["down"]:
            h["down"] = True
            self.audit.record("pieza_caida", who=brigade, why=f"{h['fails']} chequeos de salud malos seguidos: {detail}")
            await self.bus.apublish("brigada.salud", {"brigade": brigade, "ok": False, "down": True}, source="harness")
        return dict(h)

    # --- mensajes -------------------------------------------------------------------------------------------------------
    def _live_cooks(self) -> list[tuple[str, str]]:
        return [(b, c) for b, m in self.brigades.items() if not m.health["down"] for c in m.cooks
                if not self.guard.is_down(f"{b}/{c}")]

    async def _route(self, msg: Message) -> list[tuple[str, str]]:
        live = self._live_cooks()
        if self.orchestrator is not None:
            try:
                chosen = self.orchestrator.route(msg, OrchestratorContext(self),
                                                 [self.brigades[b].cooks[c] for b, c in live])
                if inspect.isawaitable(chosen):
                    chosen = await chosen
                return [self.locate(cook) for cook in chosen]
            except Exception as exc:  # noqa: BLE001 - un orquestador roto no deja a nadie sin respuesta
                self.audit.record("orquestador_fallido", who="orquestador", error=repr(exc)[:200])
        open_, rest = [], []
        for b, c in live:
            out = await self._call(b, c, "in_progress", msg, self.context(b, c))
            if out.ok and out.value:
                open_.append((b, c))
                continue
            score = await self._call(b, c, "interest", msg, self.context(b, c))
            rest.append((float(score.value or 0) if score.ok else 0.0, (b, c)))
        rest.sort(key=lambda x: -x[0])
        return open_ + [bc for _, bc in rest]

    async def receive(self, channel: str, sender: str, text: str, name: str = "", attachment: bool = False,
                      trust: Trust = Trust.UNTRUSTED) -> list[str]:
        """Un mensaje que llega por un canal. Devuelve los textos que se le mandaron de vuelta."""
        msg = Message(channel, sender, text, name, attachment, self.clock(), trust)
        self.note_incoming(channel, sender, text, name)
        self.usage.record_message()
        self.audit.record("mensaje", who=msg.contact, texto=clean(text, 300))
        self._warn_cap()
        token = _capture.set((msg.contact, []))
        try:
            for b, c in await self._route(msg):
                out = await self._call(b, c, "handle", msg, self.context(b, c))
                if not out.ok:
                    continue  # falló: que lo vea el siguiente
                if out.value is None:
                    continue
                self.audit.record("atendio", who=f"{b}/{c}", contacto=msg.contact)
                await self._process(b, c, out.value, msg)
                break
            else:
                self._new_pending(HARNESS, "harness", Level.HUMAN, f"Nadie supo responder: «{clean(text, 120)}»",
                                  Action("responder_duda", {"pregunta": clean(text, 300)}, target=msg.contact),
                                  "ningún cocinero tomó el mensaje")
                who = self.installation.identity.user or "la persona a cargo"
                self.send(msg.contact, f"¡Gracias por escribir! 😊 En un rato te responde {who}.")
            await self._settle()
            return list(_capture.get()[1])
        finally:
            _capture.reset(token)

    async def _process(self, brigade: str, cook: str, reply: Reply, msg: Message) -> None:
        if reply.text:
            self.send(msg.contact, reply.text)
        for a in reply.actions:
            if a.target is None:
                a.target = msg.contact
            if msg.trust is Trust.UNTRUSTED and a.origin is Origin.SYSTEM:
                a.origin = Origin.THIRD_PARTY
            await self.action(brigade, cook, a)

    async def consult(self, brigade: str, cook: str, msg: Message, by: str) -> Reply | None:
        out = await self._call(brigade, cook, "handle", msg, self.context(brigade, cook))
        if not out.ok or out.value is None:
            return None
        self.audit.record("consulta", who=by, a=f"{brigade}/{cook}", contacto=msg.contact)
        for a in out.value.actions:
            if a.target is None:
                a.target = msg.contact
            await self.action(brigade, cook, a)
        return Reply(text=out.value.text)

    # --- acciones -------------------------------------------------------------------------------------------------------
    def _new_pending(self, brigade: str, cook: str, level: Level, summary: str, action: Action | None,
                     reason: str, kind: str = "action", data: dict | None = None) -> dict:
        p = self.approvals.create(brigade=brigade, cook=cook, level=level, summary=summary, action=action, kind=kind,
                                  reason=reason, data=data)
        self.bus.publish("pendiente.creado", {"id": p["id"], "type": action.type if action else kind,
                                              "level": level.value, "brigade": brigade, "cook": cook,
                                              "target": action.target if action else None}, source="harness")
        return p

    def _decide(self, brigade: str, cook: str, action: Action) -> dict | None:
        """Decide el nivel. Devuelve el resultado si NO hay que ejecutar ahora (pendiente o error); None si sí."""
        if brigade not in self.brigades or cook not in self.brigades[brigade].cooks:
            return {"state": "error", "error": f"'{brigade}/{cook}' no está montado"}
        d = self.policy.decide(brigade, action.type, action.origin)
        self.audit.record("accion", who=f"{brigade}/{cook}", tipo=action.type, nivel=d.level.value, why=d.explain(),
                          destino=action.target, origen=action.origin.value)
        if d.level is Level.AUTO:
            return None
        p = self._new_pending(brigade, cook, d.level, action.summary or action.type, action, d.explain())
        return {"state": "pending", "id": p["id"], "level": d.level.value}

    async def action(self, brigade: str, cook: str, action: Action) -> dict:
        res = self._decide(brigade, cook, action)
        return res if res is not None else await self._execute(brigade, cook, action)

    def action_sync(self, brigade: str, cook: str, action: Action) -> dict:
        """Para cocineros sync: misma política, ejecución en el acto (sin loop de por medio)."""
        res = self._decide(brigade, cook, action)
        if res is not None:
            return res
        return self._finish(brigade, cook, action, self._call_sync(brigade, cook, "execute", action,
                                                                    self.context(brigade, cook)))

    def schedule_action(self, brigade: str, cook: str, action: Action) -> dict:
        """Desde código sync: si el cocinero es sync se resuelve en el acto; si es async, se agenda en el loop."""
        if brigade in self.brigades and cook in self.brigades[brigade].cooks and \
                self._is_sync(brigade, cook, "execute"):
            return self.action_sync(brigade, cook, action)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.action(brigade, cook, action))
        task = loop.create_task(self.action(brigade, cook, action))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return {"state": "scheduled"}

    def consult_sync(self, brigade: str, cook: str, msg: Message, by: str) -> Reply | None:
        out = self._call_sync(brigade, cook, "handle", msg, self.context(brigade, cook))
        if not out.ok or out.value is None:
            return None
        self.audit.record("consulta", who=by, a=f"{brigade}/{cook}", contacto=msg.contact)
        for a in out.value.actions:
            if a.target is None:
                a.target = msg.contact
            self.schedule_action(brigade, cook, a)
        return Reply(text=out.value.text)

    async def _execute(self, brigade: str, cook: str, action: Action) -> dict:
        out = await self._call(brigade, cook, "execute", action, self.context(brigade, cook))
        return self._finish(brigade, cook, action, out)

    def _finish(self, brigade: str, cook: str, action: Action, out: Any) -> dict:
        if not out.ok:
            err = str(out.error) if isinstance(out.error, ActionError) else out.reason
            self.audit.record("accion_fallida", who=f"{brigade}/{cook}", tipo=action.type, error=err[:300])
            return {"state": "error", "error": err}
        self.audit.record("accion_ejecutada", who=f"{brigade}/{cook}", tipo=action.type)
        if out.value and action.target:
            self.send(action.target, out.value)
        return {"state": "executed", "text": out.value}

    # --- lo que decide la persona --------------------------------------------------------------------------------------
    async def approve(self, pid: Any, changes: dict | None = None, who: str = "dueña") -> dict:
        p = self.approvals.open(pid)
        if p["kind"] == "trust":
            level = self.policy.confirm_step_down(p["brigade"], p["data"]["action"], who=who)
            self.approvals.close(p["id"], "aprobado", by=who)
            return {"state": "trust", "level": level.value}
        if p["level"] == Level.HUMAN.value:
            raise ActionError("esto lo resuelve una persona: usá resolve()")
        a = Action.from_dict(p["action"])
        a.data.update(changes or {})
        res = await (self._run_tool(p, a) if p["kind"] == "tool" else self._execute(p["brigade"], p["cook"], a))
        if res["state"] == "executed":
            self.approvals.close(p["id"], "aprobado", by=who, action=a.to_dict(), changed=bool(changes))
            self.audit.record("aprobado", who=who, id=p["id"], tipo=a.type, con_cambios=bool(changes))
            if self.policy.record_approval(p["brigade"], a.type, changed=bool(changes), who=who) == "propose":
                n = self.installation.trust.approvals_to_step_down
                tp = self._new_pending(
                    p["brigade"], p["cook"], Level.APPROVAL,
                    f"Aprobaste «{a.summary or a.type}» {n} veces seguidas sin cambios. ¿La dejo en automático? "
                    "Gasta plata o no tiene vuelta atrás.", None, "confianza progresiva", kind="trust",
                    data={"action": a.type})
                await self.bus.apublish("confianza.propuesta", {"id": tp["id"], "brigade": p["brigade"],
                                                                "action": a.type}, source="harness")
        await self._settle()
        return res

    async def reject(self, pid: Any, reason: str = "", who: str = "dueña") -> dict:
        p = self.approvals.open(pid)
        self.approvals.close(p["id"], "rechazado", by=who, motivo=reason)
        if p["kind"] == "trust":
            self.policy.decline_step_down(p["brigade"], p["data"]["action"], who=who)
            return {"state": "rejected"}
        action = p["action"] or {}
        self.audit.record("rechazado", who=who, id=p["id"], tipo=action.get("type"), why=reason)
        if p["brigade"] in self.brigades:
            self.policy.record_correction(p["brigade"], action.get("type", ""), who=who, why="rechazó")
        await self.bus.apublish("pendiente.rechazado", {"id": p["id"], "type": action.get("type"),
                                                         "brigade": p["brigade"], "cook": p["cook"],
                                                         "data": action.get("data", {}), "target": action.get("target"),
                                                         "reason": reason}, source="harness")
        await self._settle()
        return {"state": "rejected"}

    async def resolve(self, pid: Any, reply: str | None = None, who: str = "dueña") -> dict:
        """Cierra un pendiente que resuelve una persona. Si hay respuesta, le llega al destinatario."""
        p = self.approvals.open(pid)
        a = Action.from_dict(p["action"]) if p["action"] else None
        if reply and a is not None:
            a.data["reply"] = reply
            done = False
            if p["brigade"] in self.brigades and p["cook"] in self.brigades[p["brigade"]].cooks:
                done = (await self._execute(p["brigade"], p["cook"], a))["state"] == "executed"
            if not done and a.target:
                self.send(a.target, reply)
        self.approvals.close(p["id"], "resuelto", by=who, **({"action": a.to_dict()} if a else {}))
        self.audit.record("resuelto", who=who, id=p["id"], tipo=a.type if a else None)
        if a is not None and p["brigade"] in self.brigades and self.installation.trust.step_down_from_human:
            self.policy.record_approval(p["brigade"], a.type, who=who)
        await self._settle()
        return {"state": "resolved"}

    def correct(self, brigade: str, action_type: str, who: str = "dueña", why: str = "") -> str | None:
        """La persona corrigió o deshizo una acción automática: la confianza la sube un escalón."""
        self.audit.record("correccion", who=who, brigada=brigade, tipo=action_type, why=why)
        return self.policy.record_correction(brigade, action_type, who=who, why=why or "corrigió una acción automática")

    async def command(self, brigade: str, cook: str, name: str, data: dict | None = None, who: str = "dueña") -> Any:
        if brigade not in self.brigades or cook not in self.brigades[brigade].cooks:
            raise ActionError(f"'{brigade}/{cook}' no está montado")
        spec = self.brigades[brigade].manifest.commands.get(name)
        if who == "orquestador" and (spec is None or not spec.read):
            self.audit.record("comando_bloqueado", who=who, a=f"{brigade}/{cook}", comando=name)
            raise ActionError(f"el orquestador solo corre comandos declarados de lectura; '{name}' "
                              f"{'no está declarado' if spec is None else 'no es de lectura'}")
        if spec is None:
            note = f"{brigade}: el comando '{name}' no está declarado en el manifiesto"
            if note not in self.warnings:
                self.warnings.append(note)
            self.audit.record("comando_no_declarado", who=who, a=f"{brigade}/{cook}", comando=name)
        self.audit.record("comando", who=who, a=f"{brigade}/{cook}", comando=name)
        out = await self._call(brigade, cook, "command", name, dict(data or {}), self.context(brigade, cook))
        await self._settle()
        if out.ok:
            return out.value
        if isinstance(out.error, ActionError):
            raise out.error
        raise ActionError(f"el comando '{name}' falló: {out.reason}")

    async def talk_to_owner(self, text: str, *, session: str | None = None, channel: str | None = None,
                            on_event: Callable[[dict], Any] | None = None) -> OwnerReply:
        """La persona le habla al orquestador. `session` separa charlas (app, WhatsApp de la dueña, voz); `on_event`
        recibe el feed en vivo (ruteo, reparto, reportes) si la app lo quiere mostrar."""
        who = self.installation.identity.user or "dueña"
        self.audit.record("duena", who=who, texto=clean(text, 200), sesion=session, canal=channel)
        fn = getattr(self.orchestrator, "talk_to_owner", None)
        if fn is not None:
            token = _conversation.set(session or "default")
            try:
                r = fn(text, OwnerContext(self, who, session=session, channel=channel, on_event=on_event))
                if inspect.isawaitable(r):
                    r = await r
                await self._settle()
                if r is not None:
                    return r
            except Exception as exc:  # noqa: BLE001
                self.audit.record("orquestador_fallido", who="orquestador", error=repr(exc)[:200])
            finally:
                _conversation.reset(token)
        return OwnerReply("Todavía no tengo un orquestador que sepa atenderte: cuando esté, te ayudo con el día.")

    async def tick(self, now: datetime | None = None) -> None:
        now = now or self.clock()
        for b, c in self._live_cooks():
            await self._call(b, c, "tick", now, self.context(b, c))
        for b, m in list(self.brigades.items()):
            if m.health_fn is not None and (m.health_last is None or now - m.health_last >= HEALTH_EVERY):
                await self.check_health(b)
        if self.orchestrator is not None:
            await self._call_orchestrator("tick", now, OrchestratorContext(self))
        await self._settle()

    def _warn_cap(self) -> None:
        month = self.clock().strftime("%Y-%m")
        if self.usage.exceeded() and not self._sys.get("cap_warnings", month):
            self._sys.put("cap_warnings", month, {"month": month})
            self._new_pending(HARNESS, "harness", Level.HUMAN,
                              "Se pasó el tope de mensajes del plan: la IA queda apagada hasta el mes que viene; "
                              "los cocineros siguen con sus reglas.", Action("aviso_tope", {"mes": month}),
                              "tope del plan")

    # --- salida y supervisión -------------------------------------------------------------------------------------------
    def send(self, contact: str, text: str) -> None:
        channel, _, recipient = contact.partition(":")
        self._sys.put("outgoing", self._sys.next("outgoing"),
                      {"contact": contact, "text": text, "when": self.clock().isoformat(timespec="seconds"),
                       "order": self._sys.next("messages")})
        con = self.connectors.get(channel)
        if con is not None:
            try:
                con.send(recipient, text)
            except Exception as exc:  # noqa: BLE001 - un canal caído no tumba al harness
                self.audit.record("envio_fallido", who=channel, error=repr(exc)[:200])
        cap = _capture.get()
        if cap and cap[0] == contact:
            cap[1].append(text)

    def note_incoming(self, channel: str, sender: str, text: str, name: str = "") -> None:
        contact = f"{channel}:{sender}"
        when = self.clock().isoformat(timespec="seconds")
        self._sys.put("incoming", self._sys.next("incoming"),
                      {"contact": contact, "text": text, "name": name, "when": when, "order": self._sys.next("messages")})
        c = self._sys.get("contacts", contact) or {"contact": contact, "name": name, "messages": 0}
        c.update(name=name or c.get("name", ""), last=when, messages=c["messages"] + 1)
        self._sys.put("contacts", contact, c)

    def contacts(self) -> list[dict]:
        return sorted(self._sys.list("contacts"), key=lambda c: c.get("last", ""), reverse=True)

    def conversation(self, contact: str) -> list[dict]:
        inc = [{**m, "from": "contact"} for m in self._sys.list("incoming", contact=contact)]
        out = [{**m, "from": "raphael"} for m in self._sys.list("outgoing", contact=contact)]
        return sorted(inc + out, key=lambda m: m.get("order", 0))

    def outgoing(self, contact: str | None = None) -> list[dict]:
        return [x for x in self._sys.list("outgoing") if contact is None or x["contact"] == contact]

    def status(self) -> dict:
        """Versiones, brigadas, pendientes y políticas. Sin conversaciones ni datos de clientes."""
        return {
            "core": __version__, "contract": CONTRACT_VERSION, "edition": self.installation.edition,
            "plan": self.installation.plan,
            "orchestrator": f"{self.orchestrator.name} {self.orchestrator.version}" if self.orchestrator else None,
            "brigades": {b: {"version": m.manifest.version,
                             "cooks": {c: ("caído" if self.guard.is_down(f"{b}/{c}") else "ok") for c in m.cooks},
                             "chief": m.chief.roles() if m.chief else None,
                             "chief_down": m.chief_down, "chief_failures": m.chief_failures,
                             "health": dict(m.health) if m.health_fn else None}
                         for b, m in self.brigades.items()},
            "pending": len(self.approvals.list()), "notices": len(self.notices(unseen_only=True)),
            "warnings": list(self.warnings), "policy": self.policy.table(),
            "usage": self.usage.summary(), "tools": self.tools.list(), "helpers": self.live.snapshot(),
        }
