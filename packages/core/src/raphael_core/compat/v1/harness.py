"""El `Harness` de v1 (raphael-harness 0.4) con su misma interfaz, corriendo sobre el `Runtime` del v2.

Cada brigada v1 se monta como una brigada v2 de un solo cocinero (mismo nombre), con un manifiesto armado
a partir de sus atributos (`acciones`, `eventos`). Todo pasa por el v2: Policy Engine sin pisos con confianza
progresiva, aislamiento de fallos, auditoría, modelos por escalón. Lo que cambia para las brigadas v1:
    - un error en `atender` ya no tumba el mensaje: lo ve la siguiente brigada;
    - las acciones que en v1 eran "pisos" ahora son niveles de fábrica (ver `politicas.py`);
    - los datos siguen en un espacio por pieza, con el mismo nombre que en v1.
Los métodos son sync, como en v1 (por dentro usan `Runtime.run`): no llamarlos desde un loop async.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ... import __version__
from ...contract import Action, Cook, Message, Orchestrator, Origin, Reply
from ...installation import installation_from
from ...manifest import Manifest, manifest_from
from ...models import ModelGateway, Usage
from ...runtime import Runtime
from .almacen import Almacen, Espacio
from .cargador import descubrir
from .contrato import CONTRATO, Accion, Brigada, Charla, ErrorDeAccion, Mensaje, Orquestador, Respuesta
from .modelos import cargar_config, desde_v1
from .perfil import Perfil
from .politicas import Politicas, acciones_de

#: eventos del harness v2 que no existían en v1 (no se le pasan a las brigadas v1)
_SOLO_V2 = {"brigada.montada", "brigada.desmontada", "confianza.propuesta", "brigada.reporte", "tool.ejecutada",
            "brigada.jefe_caido", "brigada.salud"}
_ESTADOS = {"abierto": "pendiente", "aprobado": "aprobada", "rechazado": "rechazada", "resuelto": "resuelta"}
_RESULTADOS = {"executed": "ejecutada", "pending": "pendiente", "error": "error", "rejected": "rechazada",
               "resolved": "resuelta", "trust": "confianza", "scheduled": "agendada"}


class Conector:
    """Canal de salida v1 (WhatsApp, Instagram…). El de base no manda nada: solo registra."""

    def enviar(self, quien: str, texto: str) -> None:  # pragma: no cover
        pass


class _ConectorV2:
    def __init__(self, c: Conector) -> None:
        self._c = c

    def send(self, recipient: str, text: str) -> None:
        self._c.enviar(recipient, text)


# --- traducciones ---------------------------------------------------------------------------------------------------
def _msg_v1(m: Message) -> Mensaje:
    return Mensaje(m.channel, m.sender, m.text, m.name, m.attachment, m.at)


def _msg_v2(m: Mensaje) -> Message:
    return Message(m.canal, m.quien, m.texto, m.nombre, m.adjunto, m.cuando)


def _acc_v2(a: Accion) -> Action:
    return Action(a.tipo, dict(a.datos), a.resumen, a.destino, Origin.SYSTEM)


def _acc_v1(a: Action) -> Accion:
    datos = dict(a.data)
    if "reply" in datos:
        datos.setdefault("respuesta", datos.pop("reply"))
    return Accion(a.type, datos, a.summary, a.target)


def _pieza(brigade: str | None) -> str | None:
    return "harness" if brigade == "_harness" else brigade


def _evento_v1(evento: str, datos: dict) -> dict:
    d = dict(datos)
    src = d.pop("_from", None)
    if src == "harness" and evento == "pendiente.creado":
        return {"id": d.get("id"), "tipo": d.get("type"), "nivel": d.get("level"), "pieza": _pieza(d.get("brigade")),
                "destino": d.get("target")}
    if src == "harness" and evento == "pendiente.rechazado":
        return {"id": d.get("id"), "tipo": d.get("type"), "pieza": _pieza(d.get("brigade")), "datos": d.get("data", {}),
                "destino": d.get("target"), "motivo": d.get("reason", "")}
    if src and src != "harness":
        d["_de"] = src
    return d


def _resultado_v1(r: dict) -> dict:
    out = {"estado": _RESULTADOS.get(r.get("state"), r.get("state"))}
    for k, v in (("id", "id"), ("level", "nivel"), ("text", "texto"), ("error", "error")):
        if k in r:
            out[v] = r[k]
    return out


def _slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (texto or "").lower()).strip("-")[:40] or "empresa"


def _manifiesto(b: Brigada) -> Manifest:
    version = b.version if re.match(r"^\d+(\.\d+){0,2}", str(b.version or "")) else "0.0.0"
    return manifest_from({
        "id": b.nombre, "name": b.descripcion or b.nombre, "version": version, "contract": "^2.0",
        "cooks": [{"id": b.nombre, "entry": "raphael_core.compat.v1:Brigada"}],
        "actions": acciones_de(b),
        "events": {"publishes": ["*"], "consumes": list(b.eventos or ())},
        # v1 no distingue lectura de escritura: se declaran todos como NO de lectura (solo la dueña los usa)
        "commands": {c: {"read": False, "description": str(d)} for c, d in (b.comandos or {}).items()
                     if re.match(r"^[a-z][a-z0-9_]{0,59}$", c)},
    })


# --- adaptadores ----------------------------------------------------------------------------------------------------
class _CocineroV1(Cook):
    """Una brigada v1 vista como cocinero v2."""

    def __init__(self, h: Harness, b: Brigada) -> None:
        self.h, self.b = h, b
        self.name, self.version = b.nombre, b.version

    def _c(self) -> Contexto:
        return self.h._ctx(self.b.nombre)

    def start(self, ctx: Any) -> None:
        self.b.iniciar(self._c())

    def interest(self, msg: Message, ctx: Any) -> float:
        return self.b.interes(_msg_v1(msg), self._c())

    def in_progress(self, msg: Message, ctx: Any) -> bool:
        return self.b.en_curso(_msg_v1(msg), self._c())

    def handle(self, msg: Message, ctx: Any) -> Reply | None:
        r = self.b.atender(_msg_v1(msg), self._c())
        return None if r is None else Reply(r.texto, [_acc_v2(a) for a in r.acciones])

    def execute(self, action: Action, ctx: Any) -> str | None:
        return self.b.ejecutar(_acc_v1(action), self._c())

    def on_event(self, event: str, data: dict, ctx: Any) -> None:
        if event not in _SOLO_V2:
            self.b.al_evento(event, _evento_v1(event, data), self._c())

    def command(self, name: str, data: dict, ctx: Any) -> Any:
        return self.b.comando(name, data, self._c())

    def tick(self, now: datetime, ctx: Any) -> None:
        self.b.tick(now, self._c())


class OrdenSimple(Orquestador):
    """Orquestador de reserva de v1: primero la conversación abierta, después el interés."""

    nombre = "orden-simple"
    version = __version__

    def elegir(self, msg, ctx, brigadas):
        abiertas = [b for b in brigadas if b.en_curso(msg, ctx.para(b.nombre))]
        resto = sorted((b for b in brigadas if b not in abiertas), key=lambda b: -b.interes(msg, ctx.para(b.nombre)))
        return abiertas + resto


class _OrquestadorV2(Orchestrator):
    def __init__(self, h: Harness) -> None:
        self.h = h
        self.name, self.version = h.orquestador.nombre, h.orquestador.version

    def route(self, msg: Message, ctx: Any, cooks: list[Cook]) -> list[Cook]:
        por_id = {id(c.b): c for c in cooks if isinstance(c, _CocineroV1) and c.b.nombre in self.h.brigadas}
        elegidas = self.h.orquestador.elegir(_msg_v1(msg), self.h._ctx("orquestador"),
                                             [c.b for c in por_id.values()])
        return [por_id[id(b)] for b in elegidas if id(b) in por_id]


class _BusV1:
    def __init__(self, h: Harness) -> None:
        self._h = h

    @property
    def historial(self) -> list[tuple[str, dict]]:
        return [(e, _evento_v1(e, d)) for e, d in self._h.runtime.bus.history]

    def publicar(self, evento: str, datos: dict) -> None:
        self._h.runtime.bus.publish(evento, datos)


class _UsoV1:
    def __init__(self, usage: Usage) -> None:
        self._u = usage

    def excedido(self) -> bool:
        return self._u.exceeded()

    def resumen(self, mes: str | None = None) -> dict:
        s = self._u.summary(mes)
        return {"mes": s["month"], "mensajes": s["messages"], "ia": s["ai"], "tokens_in": s["tokens_in"],
                "tokens_out": s["tokens_out"], "costo_usd": s["cost_usd"], "fallas_ia": s["ai_failures"],
                "limite_mensajes": s["limit"], "excedido": s["exceeded"]}


# --- contexto -------------------------------------------------------------------------------------------------------
class Contexto:
    """Lo que el harness le ofrece a UNA pieza v1."""

    def __init__(self, h: Harness, pieza: str) -> None:
        self._h = h
        self.pieza = pieza

    @property
    def perfil(self) -> Perfil:
        return self._h.perfil

    @property
    def negocio(self) -> str:
        return self._h.perfil.negocio

    @property
    def datos(self) -> Espacio:
        return self._h.almacen.espacio(self.pieza)

    def ahora(self) -> datetime:
        return self._h.reloj()

    def hoy(self) -> date:
        return self._h.reloj().date()

    def instalada(self, brigada: str) -> bool:
        return brigada in self._h.brigadas

    def para(self, pieza: str) -> Contexto:
        """El contexto de otra pieza (solo lo usa el orquestador para preguntar interés)."""
        return self._h._ctx(pieza)

    def publicar(self, evento: str, datos: dict) -> None:
        self._h.runtime.audit.record("evento", who=self.pieza, evento=evento)
        self._h.runtime.bus.publish(evento, datos, source=self.pieza)

    def solicitar(self, accion: Accion) -> dict:
        if self.pieza not in self._h.runtime.brigades:
            return {"estado": "error", "error": f"'{self.pieza}' no es una brigada montada"}
        return _resultado_v1(self._h.runtime.schedule_action(self.pieza, self.pieza, _acc_v2(accion)))

    def consultar(self, brigada: str, msg: Mensaje) -> Respuesta | None:
        if brigada not in self._h.brigadas or brigada not in self._h.runtime.brigades:
            return None
        r = self._h.runtime.consult_sync(brigada, brigada, _msg_v2(msg), by=self.pieza)
        return None if r is None else Respuesta(texto=r.text)

    def ia(self, rol: str, mensajes: list[dict], **kw: Any) -> str | None:
        return self._h.modelos.complete(rol, mensajes, target=self.pieza, max_tokens=kw.get("max_tokens", 300),
                                        temperature=kw.get("temperatura", kw.get("temperature", 0.2)))

    def hay_ia(self, rol: str) -> bool:
        return self._h.modelos.available(rol, target=self.pieza)

    def registrar(self, que: str, **datos: Any) -> None:
        self._h.runtime.audit.record(que, who=self.pieza, **datos)

    # --- lo que el orquestador necesita para hacer de secretario (leer, nunca ejecutar)
    def brigadas_activas(self) -> list[str]:
        return list(self._h.brigadas)

    def pendientes(self) -> list[dict]:
        return self._h.pendientes()

    def conversacion(self, contacto: str) -> list[dict]:
        return self._h.conversacion(contacto)

    def consultar_datos(self, brigada: str, comando: str, datos: dict | None = None) -> Any:
        b = self._h.brigadas.get(brigada)
        if b is None:
            return None
        self._h.runtime.audit.record("consulta_orquestador", who=self.pieza, brigada=brigada, comando=comando)
        try:
            return b.comando(comando, dict(datos or {}), self._h._ctx(brigada))
        except Exception:  # noqa: BLE001 - una brigada rota no tumba al secretario
            return None


class ContextoDuena(Contexto):
    """Cuando habla la DUEÑA: además de leer, puede ejecutar lo que ella ordena. Todo queda auditado."""

    def _orden(self, orden: str, **datos: Any) -> None:
        self._h.runtime.audit.record("orden_duena", who=self._h.perfil.quien_decide, orden=orden, **datos)

    def aprobar(self, pid: int, cambios: dict | None = None) -> dict:
        self._orden("aprobar", id=pid)
        return self._h.aprobar(pid, cambios)

    def rechazar(self, pid: int, motivo: str = "") -> dict:
        self._orden("rechazar", id=pid)
        return self._h.rechazar(pid, motivo)

    def resolver(self, pid: int, respuesta: str | None = None) -> dict:
        self._orden("resolver", id=pid)
        return self._h.resolver(pid, respuesta)

    def ordenar(self, brigada: str, comando: str, datos: dict | None = None) -> Any:
        self._orden("comando", brigada=brigada, comando=comando)
        return self._h.comando(brigada, comando, datos)

    def escribir(self, contacto: str, texto: str) -> None:
        self._orden("escribir", contacto=contacto)
        self._h.runtime.send(contacto, texto)


# --- el harness -----------------------------------------------------------------------------------------------------
class Harness:
    def __init__(self, perfil: Perfil, *, almacen: Almacen | None = None, orquestador: Orquestador | None = None,
                 brigadas: list[Brigada] | None = None, rutas_dev: str | Path | None = None,
                 config_modelos: dict | None = None, reloj: Callable[[], datetime] | None = None,
                 conectores: dict[str, Conector] | None = None, env: dict[str, str] | None = None,
                 transporte_ia: Callable | None = None) -> None:
        self.reloj = reloj or datetime.now
        self.perfil = perfil
        self.almacen = almacen or Almacen(":memory:", reloj=self.reloj)
        self.avisos: list[str] = []
        self.conectores = conectores or {}

        if brigadas is None or orquestador is None:
            orq_cls, disponibles, avisos = descubrir(rutas_dev)
            self.avisos += avisos
            if brigadas is None:
                brigadas = [disponibles[n]() for n in perfil.brigadas if n in disponibles]
                faltan = [n for n in perfil.brigadas if n not in disponibles]
                if faltan:
                    self.avisos.append(f"el perfil pide brigadas que no están instaladas: {faltan}")
            if orquestador is None and orq_cls is not None:
                orquestador = orq_cls()
        for b in brigadas:
            if b.contrato != CONTRATO:
                raise ValueError(f"brigada '{b.nombre}' usa el contrato {b.contrato}; el harness usa {CONTRATO}")
        self.brigadas: dict[str, Brigada] = {b.nombre: b for b in brigadas}
        self.orquestador: Orquestador = orquestador or OrdenSimple()
        self._contextos: dict[str, Contexto] = {}

        inst = installation_from({
            "id": _slug(perfil.negocio), "edition": "personal" if perfil.plan == "privado" else "cloud",
            "plan": perfil.plan, "identity": {"user": perfil.quien_decide},
            "brigades": {n: {"active": True} for n in self.brigadas}, "autonomy": dict(perfil.politicas),
            "limits": {"messages_month": perfil.limites.mensajes_mes},
        })
        usage = Usage(self.almacen.store.space("_uso"), perfil.limites.mensajes_mes, self.reloj)
        config = desde_v1(config_modelos if config_modelos is not None else cargar_config())
        self.modelos = ModelGateway(config, usage, plan=perfil.plan, edition=inst.edition, env=env,
                                    transport=transporte_ia)
        self.runtime = Runtime(inst, store=self.almacen.store, clock=self.reloj, orchestrator=_OrquestadorV2(self),
                               connectors={c: _ConectorV2(x) for c, x in self.conectores.items()}, models=self.modelos)
        self.politicas = Politicas(dict(perfil.politicas), [], motor=self.runtime.policy)
        for b in self.brigadas.values():
            Runtime.run(self.runtime.mount(_manifiesto(b), {b.nombre: _CocineroV1(self, b)}))
        for a in [*self.politicas.ignoradas, *self.runtime.warnings]:
            if a not in self.avisos:
                self.avisos.append(a)
        self.bus = _BusV1(self)
        self.uso = _UsoV1(self.runtime.usage)

    # --- entrada
    def _ctx(self, pieza: str) -> Contexto:
        if pieza not in self._contextos:
            self._contextos[pieza] = Contexto(self, pieza)
        return self._contextos[pieza]

    def recibir(self, canal: str, quien: str, texto: str, nombre: str = "", adjunto: bool = False) -> list[str]:
        """Un mensaje de un cliente. Devuelve los textos que se le mandaron de vuelta."""
        return Runtime.run(self.runtime.receive(canal, quien, texto, nombre, adjunto))

    def anotar_entrante(self, canal: str, quien: str, texto: str, nombre: str = "") -> None:
        self.runtime.note_incoming(canal, quien, texto, nombre)

    # --- panel de la dueña
    def pendientes(self, estado: str | None = "pendiente") -> list[dict]:
        out = []
        for p in self.runtime.approvals.list(state=None):
            a = p.get("action") or {"type": p["kind"], "data": p.get("data", {}), "summary": p["summary"], "target": None}
            v1 = {"id": p["id"], "pieza": _pieza(p["brigade"]), "nivel": p["level"],
                  "accion": {"tipo": a["type"], "datos": a.get("data", {}), "resumen": a.get("summary") or p["summary"],
                             "destino": a.get("target")},
                  "estado": _ESTADOS.get(p["state"], p["state"]), "creado": p["created"]}
            if "motivo" in p:
                v1["motivo"] = p["motivo"]
            if estado is None or v1["estado"] == estado:
                out.append(v1)
        return out

    def aprobar(self, pid: int, cambios: dict | None = None) -> dict:
        return _resultado_v1(Runtime.run(self.runtime.approve(pid, cambios, who=self.perfil.quien_decide)))

    def rechazar(self, pid: int, motivo: str = "") -> dict:
        return _resultado_v1(Runtime.run(self.runtime.reject(pid, motivo, who=self.perfil.quien_decide)))

    def resolver(self, pid: int, respuesta: str | None = None) -> dict:
        return _resultado_v1(Runtime.run(self.runtime.resolve(pid, respuesta, who=self.perfil.quien_decide)))

    def comando(self, pieza: str, nombre: str, datos: dict | None = None) -> Any:
        if pieza not in self.brigadas:
            raise ErrorDeAccion(f"la brigada '{pieza}' no está instalada")
        return Runtime.run(self.runtime.command(pieza, pieza, nombre, datos, who=self.perfil.quien_decide))

    def hablar_con_duena(self, texto: str) -> Charla:
        self.runtime.audit.record("duena", who=self.perfil.quien_decide, texto=texto[:200])
        hacer = getattr(self.orquestador, "atender_duena", None)
        charla = hacer(texto, ContextoDuena(self, "orquestador")) if hacer else None
        return charla or Charla("Todavía no tengo secretario instalado: actualizá el orquestador para que pueda "
                                "ayudarte con el día.")

    def tick(self, ahora: datetime | None = None) -> None:
        Runtime.run(self.runtime.tick(ahora))

    # --- salida y supervisión
    def contactos(self) -> list[dict]:
        return [{"contacto": c["contact"], "nombre": c.get("name", ""), "mensajes": c["messages"],
                 "ultimo": c.get("last", "")} for c in self.runtime.contacts()]

    def conversacion(self, contacto: str) -> list[dict]:
        return [{"contacto": m["contact"], "texto": m["text"], "nombre": m.get("name", ""), "cuando": m["when"],
                 "orden": m.get("order", 0), "de": "cliente" if m["from"] == "contact" else "raphael"}
                for m in self.runtime.conversation(contacto)]

    def salientes(self, contacto: str | None = None) -> list[dict]:
        return [{"contacto": x["contact"], "texto": x["text"], "cuando": x["when"], "orden": x.get("order", 0)}
                for x in self.runtime.outgoing(contacto)]

    def registro(self) -> list[dict]:
        return [{"que": e["what"], "cuando": e["when"], "pieza": e["who"],
                 **{k: v for k, v in e.items() if k not in ("n", "what", "who", "when")}}
                for e in self.runtime.audit.entries()]

    def estado(self) -> dict:
        """Lo que ve el panel de soporte: versiones, avisos, uso. Sin conversaciones ni datos de clientes."""
        return {
            "harness": __version__, "contrato": CONTRATO,
            "orquestador": f"{self.orquestador.nombre} {self.orquestador.version}",
            "brigadas": {n: b.version for n, b in self.brigadas.items()},
            "plan": self.perfil.plan, "avisos": list(self.avisos), "uso": self.uso.resumen(),
            "pendientes": len(self.pendientes()), "politicas": self.politicas.tabla(),
        }
