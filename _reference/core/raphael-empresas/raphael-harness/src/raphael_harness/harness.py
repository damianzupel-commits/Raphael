"""El harness: el punto de reunión de todas las piezas de Raphael.

Carga el orquestador y las brigadas instaladas, les da a cada una su Contexto (perfil, datos,
eventos, IA, acciones) y es el único camino entre ellas y el mundo: los mensajes entran por
acá, toda acción pasa por el Policy Engine y todo queda registrado (Supervisión).
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from . import __version__
from .almacen import Almacen, Espacio
from .cargador import descubrir
from .contrato import CONTRATO, Accion, Brigada, Charla, ErrorDeAccion, Mensaje, Nivel, Orquestador, Respuesta
from .eventos import Bus
from .modelos import Modelos, cargar_config
from .perfil import Perfil
from .politicas import Politicas
from .texto import limpio
from .uso import Uso


class Conector:
    """Canal de salida hacia el cliente (WhatsApp, Instagram…). El de base no manda nada: solo registra."""

    def enviar(self, quien: str, texto: str) -> None:  # pragma: no cover - lo implementan los conectores reales
        pass


class OrdenSimple(Orquestador):
    """Orquestador de reserva si no hay ninguno instalado: primero la conversación abierta, después el interés."""

    nombre = "orden-simple"
    version = __version__

    def elegir(self, msg, ctx, brigadas):
        abiertas = [b for b in brigadas if b.en_curso(msg, ctx.para(b.nombre))]
        resto = sorted((b for b in brigadas if b not in abiertas), key=lambda b: -b.interes(msg, ctx.para(b.nombre)))
        return abiertas + resto


class Contexto:
    """Lo que el harness le ofrece a UNA pieza. Es todo lo que una brigada puede tocar."""

    def __init__(self, harness: "Harness", pieza: str) -> None:
        self._h = harness
        self.pieza = pieza

    # --- datos y entorno
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

    def para(self, pieza: str) -> "Contexto":
        """El contexto de otra pieza (solo lo usa el orquestador para preguntar interés)."""
        return self._h._ctx(pieza)

    # --- comunicación entre piezas (siempre a través del harness)
    def publicar(self, evento: str, datos: dict) -> None:
        self._h._registrar("evento", pieza=self.pieza, evento=evento)
        self._h.bus.publicar(evento, {**datos, "_de": self.pieza})

    def solicitar(self, accion: Accion) -> dict:
        """Pide una acción (pasa por el Policy Engine). Devuelve {'estado': 'ejecutada'|'pendiente'|'error', …}."""
        return self._h._accion(self.pieza, accion)

    def consultar(self, brigada: str, msg: Mensaje) -> Respuesta | None:
        """Le pasa un mensaje a otra brigada y devuelve su respuesta (sus acciones ya quedan procesadas)."""
        return self._h._consultar(self.pieza, brigada, msg)

    def ia(self, rol: str, mensajes: list[dict], **kw: Any) -> str | None:
        """Texto de la IA del plan, o None (sin modelo, falla o tope): la brigada sigue con sus reglas."""
        return self._h.modelos.completar(rol, mensajes, **kw)

    def hay_ia(self, rol: str) -> bool:
        """¿Hay una IA lista para este rol (configurada, con clave y sin pasarse del tope)?"""
        return self._h.modelos.disponible(rol)

    def registrar(self, que: str, **datos: Any) -> None:
        self._h._registrar(que, pieza=self.pieza, **datos)

    # --- lo que el orquestador necesita para hacer de secretario (leer, nunca ejecutar)
    def brigadas_activas(self) -> list[str]:
        return list(self._h.brigadas)

    def pendientes(self) -> list[dict]:
        return self._h.pendientes()

    def conversacion(self, contacto: str) -> list[dict]:
        return self._h.conversacion(contacto)

    def consultar_datos(self, brigada: str, comando: str, datos: dict | None = None) -> Any:
        """Corre un comando de lectura de otra brigada (listar encargos, turnos…). None si no está instalada o falla."""
        b = self._h.brigadas.get(brigada)
        if b is None:
            return None
        try:
            return b.comando(comando, dict(datos or {}), self._h._ctx(brigada))
        except Exception:  # noqa: BLE001 - una brigada rota no tumba al secretario
            return None


class ContextoDuena(Contexto):
    """El contexto del orquestador cuando es la DUEÑA quien habla: además de leer, puede ejecutar lo que ella ordena.

    Solo se crea dentro de `hablar_con_duena`; las brigadas nunca lo reciben. Cada orden queda en la auditoría.
    """

    def aprobar(self, pid: int, cambios: dict | None = None) -> dict:
        self._h._registrar("orden_duena", orden="aprobar", id=pid)
        return self._h.aprobar(pid, cambios)

    def rechazar(self, pid: int, motivo: str = "") -> dict:
        self._h._registrar("orden_duena", orden="rechazar", id=pid)
        return self._h.rechazar(pid, motivo)

    def resolver(self, pid: int, respuesta: str | None = None) -> dict:
        self._h._registrar("orden_duena", orden="resolver", id=pid)
        return self._h.resolver(pid, respuesta)

    def ordenar(self, brigada: str, comando: str, datos: dict | None = None) -> Any:
        """Corre un comando de una brigada (cambiar el estado de un encargo, etc.). Levanta ErrorDeAccion si no existe."""
        self._h._registrar("orden_duena", orden="comando", brigada=brigada, comando=comando)
        return self._h.comando(brigada, comando, datos)

    def escribir(self, contacto: str, texto: str) -> None:
        self._h._registrar("orden_duena", orden="escribir", contacto=contacto)
        self._h._enviar(contacto, texto)


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

        self._sis = self.almacen.espacio("_harness")
        self._audit = self.almacen.espacio("_auditoria")
        self.uso = Uso(self.almacen.espacio("_uso"), perfil.limites.mensajes_mes, self.reloj)
        self.modelos = Modelos(config_modelos if config_modelos is not None else cargar_config(), perfil.plan, self.uso,
                               env=env, transporte=transporte_ia)
        self.politicas = Politicas(perfil.politicas, list(self.brigadas.values()))
        self.avisos += self.politicas.ignoradas
        self.bus = Bus()
        self._contextos: dict[str, Contexto] = {}
        self._captura: tuple[str, list[str]] | None = None

        for b in self.brigadas.values():
            b.iniciar(self._ctx(b.nombre))
            for ev in b.eventos:
                self.bus.suscribir(ev, lambda e, d, b=b: b.al_evento(e, d, self._ctx(b.nombre)))
        self._registrar("inicio", brigadas={n: b.version for n, b in self.brigadas.items()},
                        orquestador=f"{self.orquestador.nombre} {self.orquestador.version}", avisos=self.avisos)

    # ------------------------------------------------------------------ entrada
    def _ctx(self, pieza: str) -> Contexto:
        if pieza not in self._contextos:
            self._contextos[pieza] = Contexto(self, pieza)
        return self._contextos[pieza]

    def recibir(self, canal: str, quien: str, texto: str, nombre: str = "", adjunto: bool = False) -> list[str]:
        """Un mensaje de un cliente. Devuelve los textos que se le mandaron de vuelta."""
        msg = Mensaje(canal, quien, texto, nombre, adjunto, self.reloj())
        self.anotar_entrante(canal, quien, texto, nombre)
        self.uso.registrar_mensaje()
        self._registrar("mensaje", contacto=msg.contacto, texto=limpio(texto, 300))
        self._avisar_tope()
        self._captura = (msg.contacto, [])
        try:
            orden = self.orquestador.elegir(msg, self._ctx("orquestador"), list(self.brigadas.values()))
            for b in orden:
                r = b.atender(msg, self._ctx(b.nombre))
                if r is not None:
                    self._registrar("atendio", pieza=b.nombre, contacto=msg.contacto)
                    self._procesar(b.nombre, r, msg)
                    break
            else:
                self._crear_pendiente("harness", Accion("responder_duda", {"pregunta": limpio(texto, 300)},
                                                        f"Nadie supo responder: «{limpio(texto, 120)}»", msg.contacto),
                                      Nivel.HUMANO)
                self._enviar(msg.contacto, f"¡Gracias por escribir! 😊 En un rato te responde {self.perfil.quien_decide}.")
            return self._captura[1]
        finally:
            self._captura = None

    def _procesar(self, pieza: str, r: Respuesta, msg: Mensaje) -> None:
        if r.texto:
            self._enviar(msg.contacto, r.texto)
        for a in r.acciones:
            if a.destino is None:
                a.destino = msg.contacto
            self._accion(pieza, a)

    def _consultar(self, origen: str, destino: str, msg: Mensaje) -> Respuesta | None:
        b = self.brigadas.get(destino)
        if b is None:
            return None
        r = b.atender(msg, self._ctx(destino))
        if r is None:
            return None
        self._registrar("consulta", pieza=origen, a=destino, contacto=msg.contacto)
        for a in r.acciones:
            if a.destino is None:
                a.destino = msg.contacto
            self._accion(destino, a)
        return Respuesta(texto=r.texto)

    # ------------------------------------------------------------------ acciones
    def _accion(self, pieza: str, accion: Accion) -> dict:
        nivel = self.politicas.nivel(pieza, accion.tipo)
        self._registrar("accion", pieza=pieza, tipo=accion.tipo, nivel=nivel.value, destino=accion.destino)
        if nivel is Nivel.AUTO:
            return self._ejecutar(pieza, accion)
        pid = self._crear_pendiente(pieza, accion, nivel)
        return {"estado": "pendiente", "id": pid, "nivel": nivel.value}

    def _ejecutar(self, pieza: str, accion: Accion) -> dict:
        b = self.brigadas.get(pieza)
        if b is None:
            return {"estado": "error", "error": f"la brigada '{pieza}' no está instalada"}
        try:
            texto = b.ejecutar(accion, self._ctx(pieza))
        except ErrorDeAccion as e:
            self._registrar("accion_fallida", pieza=pieza, tipo=accion.tipo, error=str(e))
            return {"estado": "error", "error": str(e)}
        self._registrar("accion_ejecutada", pieza=pieza, tipo=accion.tipo)
        if texto and accion.destino:
            self._enviar(accion.destino, texto)
        return {"estado": "ejecutada", "texto": texto}

    def _crear_pendiente(self, pieza: str, accion: Accion, nivel: Nivel) -> int:
        pid = self._sis.siguiente("pendientes")
        self._sis.guardar("pendientes", pid, {"id": pid, "pieza": pieza, "nivel": nivel.value, "accion": accion.a_dict(),
                                              "estado": "pendiente", "creado": self.reloj().isoformat(timespec="seconds")})
        self.bus.publicar("pendiente.creado", {"id": pid, "tipo": accion.tipo, "nivel": nivel.value, "pieza": pieza,
                                               "destino": accion.destino})
        return pid

    # ------------------------------------------------------------------ panel de la dueña
    def pendientes(self, estado: str | None = "pendiente") -> list[dict]:
        ps = self._sis.listar("pendientes")
        return [p for p in ps if estado is None or p["estado"] == estado]

    def _pendiente(self, pid: int) -> dict:
        p = self._sis.obtener("pendientes", pid)
        if not p or p["estado"] != "pendiente":
            raise ErrorDeAccion(f"no hay un pendiente abierto con el número {pid}")
        return p

    def aprobar(self, pid: int, cambios: dict | None = None) -> dict:
        p = self._pendiente(pid)
        if p["nivel"] == Nivel.HUMANO.value:
            raise ErrorDeAccion("esto lo resuelve una persona: usá resolver()")
        a = Accion.de_dict(p["accion"])
        a.datos.update(cambios or {})
        res = self._ejecutar(p["pieza"], a)
        if res["estado"] == "ejecutada":
            self._sis.guardar("pendientes", pid, {**p, "accion": a.a_dict(), "estado": "aprobada"})
            self._registrar("aprobado", id=pid, tipo=a.tipo)
        return res

    def rechazar(self, pid: int, motivo: str = "") -> dict:
        p = self._pendiente(pid)
        self._sis.guardar("pendientes", pid, {**p, "estado": "rechazada", "motivo": motivo})
        self._registrar("rechazado", id=pid, motivo=motivo)
        self.bus.publicar("pendiente.rechazado", {"id": pid, "tipo": p["accion"]["tipo"], "pieza": p["pieza"],
                                                  "datos": p["accion"]["datos"], "destino": p["accion"]["destino"],
                                                  "motivo": motivo})
        return {"estado": "rechazada"}

    def resolver(self, pid: int, respuesta: str | None = None) -> dict:
        """Cierra un pendiente de nivel humano. Si hay respuesta, le llega al cliente."""
        p = self._pendiente(pid)
        a = Accion.de_dict(p["accion"])
        res: dict = {"estado": "resuelta"}
        if respuesta:
            a.datos["respuesta"] = respuesta
            b = self.brigadas.get(p["pieza"])
            hecho = False
            if b is not None:
                try:
                    texto = b.ejecutar(a, self._ctx(p["pieza"]))
                    if texto and a.destino:
                        self._enviar(a.destino, texto)
                    hecho = True
                except ErrorDeAccion:
                    hecho = False
            if not hecho and a.destino:
                self._enviar(a.destino, respuesta)
        self._sis.guardar("pendientes", pid, {**p, "accion": a.a_dict(), "estado": "resuelta"})
        self._registrar("resuelto", id=pid, tipo=a.tipo)
        return res

    def comando(self, pieza: str, nombre: str, datos: dict | None = None) -> Any:
        b = self.brigadas.get(pieza)
        if b is None:
            raise ErrorDeAccion(f"la brigada '{pieza}' no está instalada")
        self._registrar("comando", pieza=pieza, comando=nombre)
        return b.comando(nombre, dict(datos or {}), self._ctx(pieza))

    def hablar_con_duena(self, texto: str) -> Charla:
        """La dueña le habla al orquestador (modo secretario)."""
        self._registrar("duena", texto=limpio(texto, 200))
        hacer = getattr(self.orquestador, "atender_duena", None)
        charla = hacer(texto, ContextoDuena(self, "orquestador")) if hacer else None
        return charla or Charla("Todavía no tengo secretario instalado: actualizá el orquestador para que pueda ayudarte con el día.")

    def tick(self, ahora: datetime | None = None) -> None:
        ahora = ahora or self.reloj()
        for b in self.brigadas.values():
            b.tick(ahora, self._ctx(b.nombre))

    # ------------------------------------------------------------------ salida y supervisión
    def _enviar(self, contacto: str, texto: str) -> None:
        canal, _, quien = contacto.partition(":")
        self._sis.guardar("salientes", self._sis.siguiente("salientes"),
                          {"contacto": contacto, "texto": texto, "cuando": self.reloj().isoformat(timespec="seconds"),
                           "orden": self._sis.siguiente("mensajes")})
        con = self.conectores.get(canal)
        if con is not None:
            con.enviar(quien, texto)
        if self._captura and self._captura[0] == contacto:
            self._captura[1].append(texto)

    def anotar_entrante(self, canal: str, quien: str, texto: str, nombre: str = "") -> None:
        """Guarda un mensaje recibido (también cuando el servidor está pausado y no responde)."""
        contacto = f"{canal}:{quien}"
        cuando = self.reloj().isoformat(timespec="seconds")
        self._sis.guardar("entrantes", self._sis.siguiente("entrantes"),
                          {"contacto": contacto, "texto": texto, "nombre": nombre, "cuando": cuando,
                           "orden": self._sis.siguiente("mensajes")})
        c = self._sis.obtener("contactos", contacto) or {"contacto": contacto, "nombre": nombre, "mensajes": 0}
        c.update(nombre=nombre or c.get("nombre", ""), ultimo=cuando, mensajes=c["mensajes"] + 1)
        self._sis.guardar("contactos", contacto, c)

    def contactos(self) -> list[dict]:
        """Clientes que escribieron, el más reciente primero."""
        return sorted(self._sis.listar("contactos"), key=lambda c: c.get("ultimo", ""), reverse=True)

    def conversacion(self, contacto: str) -> list[dict]:
        """Lo que dijo el cliente y lo que se le respondió, en orden."""
        entra = [{**m, "de": "cliente"} for m in self._sis.listar("entrantes", contacto=contacto)]
        sale = [{**m, "de": "raphael"} for m in self._sis.listar("salientes", contacto=contacto)]
        return sorted(entra + sale, key=lambda m: m.get("orden", 0))

    def salientes(self, contacto: str | None = None) -> list[dict]:
        s = self._sis.listar("salientes")
        return [x for x in s if contacto is None or x["contacto"] == contacto]

    def _avisar_tope(self) -> None:
        mes = self.reloj().strftime("%Y-%m")
        if self.uso.excedido() and not self._sis.obtener("avisos_tope", mes):
            self._sis.guardar("avisos_tope", mes, {"mes": mes})
            self._crear_pendiente("harness", Accion("aviso_tope", {"mes": mes},
                                                    "Se pasó el tope de mensajes del plan: la IA queda apagada hasta "
                                                    "el mes que viene; las brigadas siguen con sus reglas."), Nivel.HUMANO)

    def _registrar(self, que: str, **datos: Any) -> None:
        self._audit.guardar("registro", self._audit.siguiente("registro"),
                            {"que": que, "cuando": self.reloj().isoformat(timespec="seconds"), **datos})

    def registro(self) -> list[dict]:
        return self._audit.listar("registro")

    def estado(self) -> dict:
        """Lo que ve el panel de soporte: versiones, avisos, uso. Sin conversaciones ni datos de clientes."""
        return {
            "harness": __version__, "contrato": CONTRATO,
            "orquestador": f"{self.orquestador.nombre} {self.orquestador.version}",
            "brigadas": {n: b.version for n, b in self.brigadas.items()},
            "plan": self.perfil.plan, "avisos": list(self.avisos), "uso": self.uso.resumen(),
            "pendientes": len(self.pendientes()), "politicas": self.politicas.tabla(),
        }
