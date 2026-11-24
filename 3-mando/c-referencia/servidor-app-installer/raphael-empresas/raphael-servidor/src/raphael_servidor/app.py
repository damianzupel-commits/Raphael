"""Servidor de Raphael para UN cliente: panel de la dueña, webhooks de Meta, relay, licencia, backups y tareas."""

from __future__ import annotations

import os
import logging
import mimetypes
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Callable

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from raphael_harness import ErrorDeAccion, Harness, cargar_perfil
from raphael_harness.almacen import Almacen

from . import __version__, ia as ia_cfg
from .config import Config
from .conectores import Instagram, WhatsApp, leer_meta, verificar_firma
from .seguridad import Secretos
from .servicios import ColaRelay, Licencia, hacer_backup, latido
from .tienda import ErrorTienda, Tienda, cargar_catalogo

log = logging.getLogger("raphael.servidor")
WEB = Path(__file__).with_name("web")

try:                                   # en algunos equipos leer los tipos del registro de Windows falla:
    mimetypes.init()                   # se usa la tabla propia de Python y listo
except Exception:  # noqa: BLE001
    mimetypes._db = mimetypes.MimeTypes()
    mimetypes.inited = True
mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("image/svg+xml", ".svg")


class Clave(BaseModel):
    clave: str


class Cambios(BaseModel):
    cambios: dict[str, Any] = {}


class Motivo(BaseModel):
    motivo: str = ""


class Resolucion(BaseModel):
    respuesta: str | None = None


class Comando(BaseModel):
    brigada: str
    nombre: str
    datos: dict[str, Any] = {}


class Conexion(BaseModel):
    celular: bool


class Habla(BaseModel):
    texto: str


class ConfigIA(BaseModel):
    proveedor: str = "otro"
    base_url: str = ""
    model: str = ""
    api_key: str = ""          # vacío = conservar la que ya está guardada


class Prueba(BaseModel):
    quien: str = "probador"
    texto: str
    nombre: str = ""


class Manual(BaseModel):
    contacto: str
    texto: str


class Raphael:
    """Todo lo que corre en el equipo del cliente, armado a partir de la Config."""

    def __init__(self, cfg: Config, transporte_meta: Callable | None = None, central_post: Callable | None = None,
                 relay: ColaRelay | None = None, transporte_ia: Callable | None = None) -> None:
        self.cfg = cfg
        cfg.dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.secretos = Secretos(cfg.secretos)
        self.almacen = Almacen(str(cfg.base))
        self._srv = self.almacen.espacio("_servidor")
        conectores = {}
        if cfg.modo == "real":
            if cfg.whatsapp_token and cfg.whatsapp_phone_id:
                conectores["whatsapp"] = WhatsApp(cfg.whatsapp_token, cfg.whatsapp_phone_id, cfg.meta_graph,
                                                  transporte_meta, self._envio_fallido)
            if cfg.instagram_token:
                conectores["instagram"] = Instagram(cfg.instagram_token, cfg.meta_graph, transporte_meta, self._envio_fallido)
        self._conectores = conectores
        self._transporte_ia = transporte_ia
        self.harness = self._armar_harness()
        self.tienda = Tienda(Path(cfg.piezas or cfg.dev or cfg.dir / "piezas"), cfg.perfil, cargar_catalogo(),
                             cfg.fuente_repos, cfg.fuente_local)
        kw = {"post": central_post} if central_post else {}
        self.licencia = Licencia(cfg.central_url, cfg.licencia, self.secretos.instalacion, cfg.dir / "licencia.json",
                                 __version__, **kw)
        self._central_post = central_post
        self.relay = relay or ColaRelay(cfg.relay_url, cfg.relay_token)
        self._parar = threading.Event()

    def _armar_harness(self) -> Harness:
        from raphael_harness.modelos import cargar_config
        cfg_ia = ia_cfg.config_modelos(cargar_config(), ia_cfg.leer(self.cfg.dir))
        return Harness(cargar_perfil(self.cfg.perfil), almacen=self.almacen, rutas_dev=self.cfg.piezas or self.cfg.dev or None,
                       conectores=self._conectores, config_modelos=cfg_ia, transporte_ia=self._transporte_ia)

    def recargar(self) -> None:
        """Vuelve a leer el perfil y las piezas: así se acopla o se suelta una brigada sin reiniciar."""
        with self.lock:
            self.harness = self._armar_harness()

    # ------------------------------------------------------------ mensajes
    def _envio_fallido(self, quien: str, texto: str, error: str) -> None:
        self._srv.guardar("envios_fallidos", self._srv.siguiente("envios_fallidos"),
                          {"quien": quien, "texto": texto, "error": error[:300], "cuando": time.strftime("%Y-%m-%dT%H:%M:%S")})

    def procesar_meta(self, payload: dict) -> int:
        n = 0
        for m in leer_meta(payload):
            with self.lock:
                if self.licencia.activa:
                    self.harness.recibir(m["canal"], m["quien"], m["texto"], m["nombre"], m["adjunto"])
                else:                                   # licencia vencida: se guarda pero no se responde
                    self.harness.anotar_entrante(m["canal"], m["quien"], m["texto"], m["nombre"])
            n += 1
        return n

    def estado(self) -> dict:
        with self.lock:
            e = self.harness.estado()
        return {**e, "servidor": __version__, "modo": self.cfg.modo, "instalacion": self.secretos.instalacion,
                "licencia": {"activa": self.licencia.activa, **{k: v for k, v in self.licencia.estado.items() if k != "clave"}},
                "envios_fallidos": len(self._srv.listar("envios_fallidos")), "ia": self._ia()}

    def _ia(self) -> str:
        p = self.harness.modelos.proveedor("secretaria")
        return f"{p['model']} ({p['nombre']})" if p else "solo reglas (sin IA)"

    # ------------------------------------------------------------ tareas de fondo
    def _cada(self, segundos: float, fn: Callable[[], None], nombre: str) -> None:
        def bucle() -> None:
            while not self._parar.is_set():
                try:
                    fn()
                except Exception:  # noqa: BLE001
                    log.exception("falló la tarea %s", nombre)
                self._parar.wait(segundos)
        threading.Thread(target=bucle, name=nombre, daemon=True).start()

    def tick(self) -> None:
        with self.lock:
            self.harness.tick()

    def traer_relay(self) -> None:
        for p in self.relay.traer():
            self.procesar_meta(p)

    def enviar_latido(self) -> None:
        kw = {"post": self._central_post} if self._central_post else {}
        e = self.estado()
        latido(self.cfg.central_url, self.cfg.licencia, self.secretos.instalacion,
               {k: e[k] for k in ("harness", "servidor", "orquestador", "brigadas", "plan", "avisos", "uso", "pendientes",
                                  "licencia", "envios_fallidos")}, **kw)

    def backup(self) -> Path:
        with self.lock:
            return hacer_backup(self.cfg.base, self.cfg.backups, self.cfg.clave_backup)

    def arrancar_tareas(self) -> None:
        self._cada(15 * 60, self.tick, "tick")
        self._cada(3, self.traer_relay, "relay")
        self._cada(6 * 3600, self.licencia.validar, "licencia")
        self._cada(15 * 60, self.enviar_latido, "latido")
        self._cada(24 * 3600, self.backup, "backup")

    def detener(self) -> None:
        self._parar.set()


def crear_app(cfg: Config | None = None, raphael: Raphael | None = None) -> FastAPI:
    r = raphael or Raphael(cfg or Config.desde_entorno())

    @asynccontextmanager
    async def vida(app: FastAPI):
        r.licencia.validar()
        if r.cfg.tareas:
            r.arrancar_tareas()
        yield
        r.detener()

    app = FastAPI(title="Raphael", version=__version__, lifespan=vida, docs_url=None, redoc_url=None)
    app.state.raphael = r

    def duena(request: Request) -> None:
        token = request.headers.get("authorization", "").removeprefix("Bearer ").strip() or request.cookies.get("raphael", "")
        if not r.secretos.sesion_valida(token):
            raise HTTPException(401, "Iniciá sesión")

    def accion(fn: Callable[[], Any]) -> Any:
        try:
            with r.lock:
                return fn()
        except ErrorDeAccion as e:
            raise HTTPException(400, str(e)) from e

    # ------------------------------------------------------------ público
    @app.get("/", include_in_schema=False)
    def raiz():
        return RedirectResponse("/panel/")

    @app.get("/salud")
    def salud():
        return {"ok": True, "version": __version__, "licencia": r.licencia.activa}

    @app.post("/api/primera-clave")
    def primera_clave(b: Clave):
        if r.secretos.tiene_clave:
            raise HTTPException(409, "La clave ya está configurada")
        try:
            r.secretos.poner_clave(b.clave)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        return {"token": r.secretos.sesion()}

    @app.post("/api/login")
    def login(b: Clave, request: Request):
        if not r.secretos.verificar_clave(b.clave, request.client.host if request.client else "-"):
            raise HTTPException(401, "Clave incorrecta (o demasiados intentos: esperá unos minutos)")
        resp = JSONResponse({"token": r.secretos.sesion()})
        resp.set_cookie("raphael", r.secretos.sesion(), httponly=True, samesite="strict", max_age=30 * 24 * 3600)
        return resp

    @app.get("/api/inicio")
    def inicio():
        return {"negocio": r.harness.perfil.negocio, "tiene_clave": r.secretos.tiene_clave}

    @app.get("/webhook/meta", response_class=PlainTextResponse)
    def verificar_webhook(request: Request):
        q = request.query_params
        if q.get("hub.mode") == "subscribe" and r.cfg.meta_verify_token and q.get("hub.verify_token") == r.cfg.meta_verify_token:
            return q.get("hub.challenge", "")
        raise HTTPException(403, "token de verificación inválido")

    @app.post("/webhook/meta")
    async def webhook(request: Request):
        cuerpo = await request.body()
        if r.cfg.modo == "real" and not verificar_firma(r.cfg.meta_app_secret, cuerpo, request.headers.get("x-hub-signature-256")):
            raise HTTPException(403, "firma inválida")
        return {"procesados": r.procesar_meta(await request.json())}

    # ------------------------------------------------------------ panel de la dueña
    privado = [Depends(duena)]

    @app.get("/api/resumen", dependencies=privado)
    def resumen():
        return r.estado()

    @app.get("/api/pendientes", dependencies=privado)
    def pendientes(todos: bool = False):
        with r.lock:
            return r.harness.pendientes(None if todos else "pendiente")

    @app.post("/api/pendientes/{pid}/aprobar", dependencies=privado)
    def aprobar(pid: int, b: Cambios):
        res = accion(lambda: r.harness.aprobar(pid, b.cambios))
        if res.get("estado") == "error":
            raise HTTPException(400, res["error"])
        return res

    @app.post("/api/pendientes/{pid}/rechazar", dependencies=privado)
    def rechazar(pid: int, b: Motivo):
        return accion(lambda: r.harness.rechazar(pid, b.motivo))

    @app.post("/api/pendientes/{pid}/resolver", dependencies=privado)
    def resolver(pid: int, b: Resolucion):
        return accion(lambda: r.harness.resolver(pid, b.respuesta))

    @app.post("/api/comando", dependencies=privado)
    def comando(b: Comando):
        return accion(lambda: r.harness.comando(b.brigada, b.nombre, b.datos))

    @app.get("/api/contactos", dependencies=privado)
    def contactos():
        with r.lock:
            return r.harness.contactos()

    @app.get("/api/conversacion", dependencies=privado)
    def conversacion(contacto: str):
        with r.lock:
            return r.harness.conversacion(contacto)

    @app.post("/api/enviar", dependencies=privado)
    def enviar(b: Manual):
        with r.lock:
            r.harness._enviar(b.contacto, b.texto)
        return {"ok": True}

    def _direcciones() -> list[str]:
        """Direcciones de esta PC en la red local, para escribir en la app del celular."""
        import socket
        puerto = int(os.environ.get("RAPHAEL_PUERTO", "8787"))
        ips: list[str] = []
        try:                                        # la IP que usa para salir a la red (no manda nada)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sk:
                sk.connect(("10.255.255.255", 1))
                ips.append(sk.getsockname()[0])
        except OSError:
            pass
        try:
            ips += [i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)]
        except OSError:
            pass
        vistas = []
        for ip in ips:
            if not ip.startswith(("127.", "169.254.")) and ip not in vistas:
                vistas.append(ip)
        return [f"http://{ip}:{puerto}" for ip in vistas]

    @app.get("/api/conexion", dependencies=privado)
    def conexion():
        """Estado del acceso desde el celular: si el servidor escucha en la red y con qué dirección."""
        activado = (r.cfg.dir / "celular.on").exists()
        escuchando = os.environ.get("RAPHAEL_HOST", "127.0.0.1") not in ("127.0.0.1", "localhost")
        return {"activado": activado, "escuchando": escuchando, "direcciones": _direcciones() if escuchando else [],
                "nube": os.environ.get("RAPHAEL_NUBE") == "1"}

    @app.post("/api/conexion", dependencies=privado)
    def cambiar_conexion(b: Conexion):
        marca = r.cfg.dir / "celular.on"
        if b.celular:
            marca.write_text("1", encoding="utf-8")
        elif marca.exists():
            marca.unlink()
        return {"activado": b.celular, "reiniciar": True}

    @app.get("/api/ia", dependencies=privado)
    def ver_ia():
        return {**ia_cfg.publica(ia_cfg.leer(r.cfg.dir)), "presets": ia_cfg.PRESETS, "activa": r._ia()}

    def _completa(b: ConfigIA) -> dict:
        """Lo que mandó el panel + la clave ya guardada si no escribió una nueva."""
        previa = ia_cfg.leer(r.cfg.dir) or {}
        clave = b.api_key.strip() or (previa.get("api_key", "") if previa.get("base_url", "").rstrip("/") == b.base_url.strip().rstrip("/") else "")
        return {"proveedor": b.proveedor.strip() or "otro", "base_url": b.base_url.strip(), "model": b.model.strip(), "api_key": clave}

    @app.post("/api/ia/probar", dependencies=privado)
    def probar_ia(b: ConfigIA):
        return ia_cfg.probar(_completa(b), r._transporte_ia)

    @app.post("/api/ia", dependencies=privado)
    def guardar_ia(b: ConfigIA):
        d = _completa(b)
        if not d["base_url"].startswith(("http://", "https://")):
            raise HTTPException(400, "La dirección tiene que empezar con http:// o https://")
        if not d["model"]:
            raise HTTPException(400, "Falta el nombre del modelo.")
        ia_cfg.guardar(r.cfg.dir, d)
        r.recargar()
        return {**ia_cfg.publica(d), "activa": r._ia()}

    @app.post("/api/ia/quitar", dependencies=privado)
    def quitar_ia():
        ia_cfg.quitar(r.cfg.dir)
        r.recargar()
        return {**ia_cfg.publica(None), "activa": r._ia()}

    @app.post("/api/secretaria", dependencies=privado)
    def secretaria(b: Habla):
        """La dueña le habla al orquestador: qué hay para hoy, qué hacer primero, el detalle de una tarea."""
        with r.lock:
            return r.harness.hablar_con_duena(b.texto).a_dict()

    @app.post("/api/probar", dependencies=privado)
    def probar(b: Prueba):
        with r.lock:
            antes = len(r.harness.registro())
            respuestas = r.harness.recibir("prueba", b.quien, b.texto, b.nombre)
            nuevos = r.harness.registro()[antes:]
        atendio = next((x["pieza"] for x in nuevos if x.get("que") == "atendio"), None)
        consultas = [x["a"] for x in nuevos if x.get("que") == "consulta"]
        pendientes = sum(1 for x in nuevos if x.get("que") == "accion" and x.get("nivel") in ("aprobacion", "humano"))
        return {"respuestas": respuestas, "brigada": atendio, "consultas": consultas, "pendientes_nuevos": pendientes}

    @app.get("/api/envios-fallidos", dependencies=privado)
    def envios_fallidos():
        return r._srv.listar("envios_fallidos")

    def tienda(fn: Callable[[], Any]) -> Any:
        try:
            with r.lock:
                res = fn()
            return res
        except ErrorTienda as e:
            raise HTTPException(400, str(e)) from e

    @app.get("/api/brigadas", dependencies=privado)
    def brigadas():
        return {"orquestador": f"{r.harness.orquestador.nombre} {r.harness.orquestador.version}", "brigadas": r.tienda.estado()}

    @app.post("/api/brigadas/{nombre}/descargar", dependencies=privado)
    def descargar(nombre: str):
        try:                                       # sin el lock: clonar puede tardar y Raphael sigue atendiendo
            return r.tienda.descargar(nombre)
        except ErrorTienda as e:
            raise HTTPException(400, str(e)) from e

    @app.post("/api/brigadas/{nombre}/activar", dependencies=privado)
    def activar(nombre: str):
        activas = tienda(lambda: r.tienda.activar(nombre))
        r.recargar()
        if nombre not in r.harness.brigadas:
            r.tienda.desactivar(nombre)
            r.recargar()
            raise HTTPException(400, f"'{nombre}' no se pudo acoplar: " + "; ".join(r.harness.avisos))
        return {"activas": activas}

    @app.post("/api/brigadas/{nombre}/desactivar", dependencies=privado)
    def desactivar(nombre: str):
        activas = tienda(lambda: r.tienda.desactivar(nombre))
        r.recargar()
        return {"activas": activas}

    @app.post("/api/backup", dependencies=privado)
    def backup():
        return {"archivo": r.backup().name}

    @app.middleware("http")
    async def sin_cache_en_el_panel(request: Request, call_next):
        """El panel cambia con cada actualización: que ni el navegador ni la ventana de escritorio guarden una copia vieja."""
        resp = await call_next(request)
        if request.url.path.startswith("/panel"):
            resp.headers["Cache-Control"] = "no-cache"
        return resp

    if WEB.is_dir():
        app.mount("/panel", StaticFiles(directory=str(WEB), html=True), name="panel")
    return app
