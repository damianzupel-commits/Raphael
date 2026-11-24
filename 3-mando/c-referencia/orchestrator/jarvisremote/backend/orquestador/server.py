"""App FastAPI del Orquestador standalone: UI + ruteo + stream de los jefes de brigada.

Liviana a propósito: NO importa `app.main` ni `app.agent` ni el registro completo de tools
(ver `slim_tools.py`; el launcher `run_orquestador.py` lo instala antes de importar esto).
Reusa tal cual los jefes de `brigades/` (`get_chief`) y su feed NDJSON.

Seguridad (los jefes pueden escribir notas y ejecutar tools de Investigación):
  - escucha solo en 127.0.0.1;
  - la API exige un token efímero que se genera en cada arranque y se inyecta en el HTML que
    sirve `GET /`; otra web no puede leerlo (sin CORS) y se rechaza cualquier Host que no sea
    el local (anti DNS-rebinding). No hay que copiar ninguna key.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field

import time

from brigades import identidad
from brigades.identidad import personalizar

from . import agentes, brigadas, conversacion, turno, voz, watchdog
from .routing import BRIGADES, DIRECTAS, brigadas_conjuntas, es_charla, pregunta_por_raphael, route

logger = logging.getLogger("orquestador")
_UI = Path(__file__).resolve().parent / "ui.html"


class HablarIn(BaseModel):
    texto: str = Field(max_length=8000)


class ChatIn(BaseModel):
    message: str
    brigade: str | None = None  # forzar una brigada desde la UI; None = que rutee el orquestador


class DirectricesIn(BaseModel):
    text: str


class DraftIn(BaseModel):
    draft: dict  # el borrador JSON (esquema de brigades/factory.py)


class DescripcionIn(BaseModel):
    descripcion: str


class ActivarIn(BaseModel):
    hash: str  # el hash del contenido que se REVISÓ (completo o prefijo de >= 12 caracteres)


class ProyectoNuevo(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    formato: str = "vertical"


class OpsIn(BaseModel):
    operaciones: list[dict] = Field(min_length=1, max_length=50)
    rev_base: int | None = None


class RenderIn(BaseModel):
    calidad: str = "preview"


STARTED = time.time()  # cuándo arrancó ESTE proceso (el lanzador lo compara con la fecha del código y del .env)


def create_app(port: int, token: str | None = None) -> FastAPI:
    token = token or secrets.token_urlsafe(24)
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
    locks: dict[str, asyncio.Lock] = {}  # un turno a la vez por jefe (comparten estado en disco)
    app = FastAPI(title="Raphael Orquestador", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def only_local_host(request: Request, call_next):
        if request.headers.get("host", "") not in allowed_hosts:
            return JSONResponse({"detail": "host no permitido"}, status_code=403)
        return await call_next(request)

    async def auth(authorization: str | None = Header(default=None)) -> None:
        sent = (authorization or "").removeprefix("Bearer ").strip()
        if not secrets.compare_digest(sent, token):
            raise HTTPException(status_code=401, detail="token inválido")

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        html = _UI.read_text(encoding="utf-8").replace("__TOKEN__", token)
        return HTMLResponse(html, headers={"Cache-Control": "no-store"})

    @app.get("/api/health")
    async def health() -> dict:
        return {"ok": True, "brigades": [*BRIGADES, *DIRECTAS], "started": STARTED}  # `started`: para detectar un proceso viejo

    # --- VOZ LOCAL (faster-whisper + Piper es-AR en esta PC; ver voice/ y docs/VOZ-LOCAL.md). Apagable con VOICE_ENABLED=0. ---
    @app.get("/api/voz", dependencies=[Depends(auth)])
    async def voz_estado() -> dict:
        """Qué hay disponible (STT, TTS) y, si falta algo, exactamente qué instalar. No carga modelos."""
        from voice.engine import get_engine

        return await get_engine().status()

    @app.post("/api/voz/transcribir", dependencies=[Depends(auth)])
    async def voz_transcribir(request: Request):
        """STT: el cuerpo es el audio crudo que grabó el navegador (webm/ogg/wav…); devuelve {texto, idioma, segundos}."""
        from voice.engine import MAX_AUDIO_BYTES, VoiceError, get_engine

        data = await request.body()
        if len(data) > MAX_AUDIO_BYTES:
            return JSONResponse({"detail": "el audio es demasiado largo"}, status_code=413)
        ct = (request.headers.get("content-type") or "").lower()
        suffix = next((s for k, s in (("webm", ".webm"), ("ogg", ".ogg"), ("wav", ".wav"), ("mp4", ".mp4"), ("mpeg", ".mp3")) if k in ct), ".webm")
        try:
            res = await get_engine().transcribe(data, suffix)
        except VoiceError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=503)
        return {"texto": res.get("texto", ""), "idioma": res.get("idioma"), "segundos": res.get("segundos")}

    @app.post("/api/voz/hablar", dependencies=[Depends(auth)])
    async def voz_hablar(body: HablarIn):
        """TTS: devuelve un WAV con el texto leído por Piper (voz es-AR). El texto se limpia (sin markdown ni código)."""
        from voice.engine import VoiceError, get_engine

        try:
            wav = await get_engine().speak(body.texto)
        except VoiceError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=503)
        return Response(content=wav, media_type="audio/wav")

    @app.on_event("shutdown")
    async def _cerrar_voz() -> None:
        from voice import engine as _voice

        if _voice._ENGINE is not None:
            await _voice._ENGINE.close()

    @app.get("/api/cocineros", dependencies=[Depends(auth)])
    async def cocineros() -> dict:
        """Por brigada: los COCINEROS (agentes permanentes: jefe + ayudantes persistentes) con su modelo efectivo, y los
        efímeros que puede crear. Sale del spec de cada brigada (Cerebro, Investigación, Seguridad y las creadas ACTIVAS)."""
        from brigades.registry import created_active_ids

        return {"brigadas": agentes.todas([*BRIGADES, *DIRECTAS, "seguridad", *created_active_ids()])}

    @app.get("/api/efimeros", dependencies=[Depends(auth)])
    async def efimeros() -> dict:
        """Tablero EN VIVO: los ayudantes efímeros que están corriendo ahora en todas las brigadas (de dónde son, qué hacen,
        desde cuándo) + los últimos que terminaron. Lo alimenta `brigades/live.py` (el motor registra al spawnear)."""
        from brigades import live

        return live.snapshot()

    @app.get("/api/watchdog", dependencies=[Depends(auth)])
    async def watchdog_status() -> dict:
        """Estado del watchdog y sus últimas intervenciones (cortes y reportes)."""
        return watchdog.status()

    @app.get("/api/privacidad", dependencies=[Depends(auth)])
    async def privacidad() -> dict:
        """Auditoría de datos por rol (O-11): qué modelo/proveedor corre cada rol, si es de esta PC, y qué datos ve. Sale de la
        misma resolución que usa el motor (sin claves). Para llevar un rol a local: ROLES_EN_LOCAL (ver .env.example)."""
        from brigades.registry import created_active_ids

        return agentes.privacidad([*BRIGADES, *DIRECTAS, "seguridad", *created_active_ids()])

    @app.get("/api/meta", dependencies=[Depends(auth)])
    async def meta() -> dict:
        from brigades.registry import created_active_ids, get_chief

        out = []
        for b in [*BRIGADES, *DIRECTAS, *created_active_ids()]:  # + las creadas y ACTIVAS (nunca los borradores)
            try:
                c = get_chief(b)
                item = {"id": b, "name": personalizar(c.config.name), "model": c.model, "model_label": c.model_label,
                        "tools": len(c.config.tool_names)}
                roles = getattr(c, "roles", None)
                if callable(roles):  # modelo EFECTIVO de cada rol de la brigada: el jefe y cada ayudante
                    item["roles"] = roles()
                out.append(item)
            except Exception as exc:  # noqa: BLE001 — una brigada caída no tumba la UI
                out.append({"id": b, "name": b, "error": str(exc)[:200]})
        from brigades.config import describe_role_model, orquestador_info

        # modelo efectivo del propio orquestador (clasifica/rutea) y de su VOZ (comunica); sin claves
        return {"brigades": out, "orquestador": orquestador_info(), "voz": describe_role_model("voz"),
                "asistente": identidad.asistente(), "usuario": identidad.usuario()}

    # --- datos de las vistas por brigada (mismas fuentes que routers/brigades.py y routers/scout.py
    # del Raphael completo, pero sin importarlos: eso arrastraría auth/config del monolito) ---
    @app.get("/api/cerebro/activity", dependencies=[Depends(auth)])
    async def cerebro_activity(limit: int = 30) -> dict:
        from brigades.cerebro_activity import recent

        return {"items": recent(limit)}

    @app.get("/api/cerebro/directrices", dependencies=[Depends(auth)])
    async def cerebro_get_directrices() -> dict:
        from brigades.directrices import load_directrices

        return {"text": load_directrices()}

    @app.post("/api/cerebro/directrices", dependencies=[Depends(auth)])
    async def cerebro_set_directrices(body: DirectricesIn) -> dict:
        from brigades.directrices import save_directrices

        return {"ok": save_directrices(body.text or "")}

    @app.get("/api/investigacion/skills", dependencies=[Depends(auth)])
    async def investigacion_skills() -> dict:
        from brigades.investigacion import describe_skills

        return {"skills": describe_skills()}

    @app.get("/api/investigacion/notes", dependencies=[Depends(auth)])
    async def investigacion_notes(limit: int = 30) -> dict:
        """Notas capturadas por Scout (tag 'investigacion') en su vault, más recientes primero."""
        from app.obsidian import profile as vault_profile
        from app.obsidian import vault
        from scout.config import load_scout_config

        cfg = load_scout_config()
        prof = vault_profile.VaultProfile(vault_path=cfg.vault_path, embeddings_path=cfg.embeddings_path)
        try:
            with vault_profile.use_profile(prof):
                notes = vault.list_notes(tag="investigacion")
        except Exception as exc:  # noqa: BLE001 — vault aún inexistente: la vista no debe romperse
            logger.warning("no se pudieron listar notas de Scout: %s", exc)
            return {"notes": []}
        return {"notes": [n.to_summary_dict() for n in notes[: max(1, min(limit, 200))]]}

    @app.post("/api/chat", dependencies=[Depends(auth)])
    async def chat(body: ChatIn):
        """Rutea el pedido y streamea NDJSON: primero `route` (a qué brigada fue y por qué); después el feed del jefe
        (start / plan / delegacion / tool / tool_result / resultado_ayudante / sintesis / reporte) y, al final, el `final`
        del ORQUESTADOR: su mensaje para Damian, derivado del reporte interno (orquestador/turno.py). Los comandos de
        gestión, los gates y el watchdog responden con texto de CÓDIGO, que sale literal (sin pasar por el LLM de la voz)."""
        from brigades.registry import get_chief

        message = (body.message or "").strip()
        queue: asyncio.Queue = asyncio.Queue()

        async def on_event(ev: dict) -> None:
            await queue.put(ev)

        async def runner() -> None:
            try:
                if not message:
                    await queue.put({"type": "error", "message": "El mensaje está vacío."})
                    return
                cmd = brigadas.parse_command(message)  # lo interpreta CÓDIGO, nunca un modelo; solo si el mensaje EMPIEZA con el comando
                if cmd:
                    await queue.put({"type": "route", "brigade": "orq", "name": "Gestión de brigadas", "via": "comando",
                                     "reason": f"/{cmd[0]}"})
                    await queue.put({"type": "start", "topic": message})
                    async with locks.setdefault("_gestion", asyncio.Lock()):  # un diseño con el modelo local a la vez
                        text = await brigadas.run_command(cmd[0], cmd[1])
                    await queue.put({"type": "final", "reply": text, "origen": "comando", "literal": True})  # texto de código: literal
                    return
                if body.brigade and body.brigade not in BRIGADES and body.brigade not in DIRECTAS and body.brigade not in brigadas.active_ids():
                    # Un borrador (o un id inexistente) NO rutea ni corre: error explícito, nunca un ruteo silencioso a otra brigada.
                    await queue.put({"type": "error", "message": f"La brigada '{body.brigade}' no existe o no está activa "
                                     "(un borrador no es operativo hasta que la actives: /revisar-brigada y /activar-brigada)."})
                    return
                if not body.brigade and es_charla(message) and os.getenv("ORQUESTADOR_CHARLA_DIRECTA", "1").strip().lower() not in ("0", "off", "false", "no"):
                    # Saludo / gracias / chau en la pestaña de auto-ruteo: lo contesta el orquestador directo (una llamada a
                    # la voz). No hay nada que buscar: despertar a Cerebro era un turno entero para decir "no encontré nada".
                    await queue.put({"type": "route", "brigade": "orq", "name": "Orquestador", "via": "charla",
                                     "reason": "saludo o charla corta: no hay nada que buscar, responde el orquestador sin despertar a una brigada"})
                    t0 = time.monotonic()
                    recordar = conversacion.enabled()
                    msg = await voz.charlar(message, conversacion=conversacion.para_prompt() if recordar else "")
                    dt = round(time.monotonic() - t0, 2)
                    await queue.put({"type": "final", "reply": msg.texto, "origen": "orquestador", "brigada": "orquestador",
                                     "tiempos": {"plan": 0, "ayudantes": 0, "sintesis": 0, "jefe": 0, "voz": dt, "total": dt}, **msg.evento()})
                    if recordar:
                        conversacion.anotar(message, "orquestador", msg.texto)
                    return
                if not body.brigade and pregunta_por_raphael(message) and os.getenv("ORQUESTADOR_AUTOCONOCIMIENTO", "1").strip().lower() not in ("0", "off", "false", "no"):
                    # Pregunta sobre Raphael mismo (qué brigadas tiene, qué puede hacer): la respuesta está en el REGISTRO, no en
                    # el vault. Antes iba a Cerebro, que buscaba en las notas y contestaba que no existía lo que sí existe.
                    await queue.put({"type": "route", "brigade": "orq", "name": "Orquestador", "via": "sistema",
                                     "reason": "pregunta sobre Raphael mismo: responde el orquestador con lo que hay en el registro de brigadas"})
                    t0 = time.monotonic()
                    borradores = [r["id"] for r in brigadas.listing()["borradores"]]
                    reporte = agentes.reporte_del_sistema([*BRIGADES, *DIRECTAS, *sorted(brigadas.active_ids())], ["seguridad"], borradores)
                    await queue.put({"type": "reporte", "brigada": "orquestador", "reporte": reporte.to_dict()})
                    await queue.put({"type": "comunicacion", "modelo": voz.modelo_label()})
                    recordar = conversacion.enabled()
                    msg = await voz.comunicar(reporte, message, conversacion=conversacion.para_prompt() if recordar else "")
                    dt = round(time.monotonic() - t0, 2)
                    await queue.put({"type": "final", "reply": msg.texto, "origen": "orquestador", "brigada": "orquestador",
                                     "tiempos": {"plan": 0, "ayudantes": 0, "sintesis": 0, "jefe": 0, "voz": dt, "total": dt}, **msg.evento()})
                    if recordar:
                        conversacion.anotar(message, "orquestador", msg.texto)
                    return
                conj, motivo = brigadas_conjuntas(message) if not body.brigade else ((), "")
                if conj and os.getenv("ORQUESTADOR_TRABAJO_CONJUNTO", "1").strip().lower() not in ("0", "off", "false", "no"):
                    # Trabajo CONJUNTO: el pedido trae señal explícita de más de una brigada. Cada una trabaja por separado (su
                    # jefe, sus ayudantes, su watchdog, su candado) y el orquestador junta los reportes y comunica UNA respuesta.
                    from brigades.registry import get_spec

                    partes, nombres = [], {}
                    for b in conj:
                        jefe = get_chief(b)
                        try:
                            sp = get_spec(b)
                        except KeyError:
                            sp = None
                        partes.append((b, jefe, sp))
                        nombres[b] = personalizar(jefe.config.name)
                    await queue.put({"type": "route", "brigade": "orq", "name": " + ".join(nombres[b] for b in conj), "via": "conjunto",
                                     "reason": motivo, "brigadas": list(conj)})
                    async with contextlib.AsyncExitStack() as pila:
                        for b in sorted(conj):  # siempre en el mismo orden: dos turnos conjuntos no se traban entre sí
                            await pila.enter_async_context(locks.setdefault(b, asyncio.Lock()))
                        await turno.run_conjunto(partes, message, on_event, nombres=nombres)
                    return
                r = await route(message, brigade=body.brigade)
                chief = get_chief(r.brigade)
                await queue.put({"type": "route", "brigade": r.brigade, "name": personalizar(chief.config.name),
                                 "via": r.via, "reason": r.reason})
                try:
                    from brigades.registry import get_spec

                    spec = get_spec(r.brigade)
                except KeyError:  # brigada legacy sin spec (Scout): el watchdog usa los defaults
                    spec = None
                async with locks.setdefault(r.brigade, asyncio.Lock()):
                    # Turno completo: el jefe planifica/delega/sintetiza/reporta (vigilado por el watchdog) y el ORQUESTADOR
                    # comunica: el `final` es suyo. Ningún texto de jefe o ayudante llega al usuario sin pasar por la voz.
                    await turno.run_turno(chief, r.message, on_event, brigade=r.brigade, spec=spec)
            except Exception as exc:  # noqa: BLE001 — se reporta como evento (ej. Ollama apagado)
                logger.exception("turno falló")
                await queue.put({"type": "error", "message": str(exc)})
            finally:
                await queue.put(None)

        async def gen():
            task = asyncio.create_task(runner())
            try:
                while True:
                    ev = await queue.get()
                    if ev is None:
                        break
                    yield json.dumps(ev, ensure_ascii=False) + "\n"
            finally:
                if not task.done():
                    task.cancel()

        return StreamingResponse(gen(), media_type="application/x-ndjson")

    # --- brigadas CREADAS (Etapa 2): borradores, revisión, activación. Todo con el token del orquestador. ---
    def _fail(exc: Exception) -> JSONResponse:
        from brigades.draft_store import DraftInvalid

        if isinstance(exc, DraftInvalid):
            return JSONResponse({"detail": "borrador inválido", "errores": exc.errors}, status_code=422)
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.get("/api/brigadas", dependencies=[Depends(auth)])
    async def brigadas_list() -> dict:
        return brigadas.listing()

    @app.get("/api/brigadas/ejemplos", dependencies=[Depends(auth)])
    async def brigadas_ejemplos() -> dict:
        return {"ejemplos": brigadas.EJEMPLOS}

    @app.get("/api/brigadas/{brigade_id}", dependencies=[Depends(auth)])
    async def brigadas_review(brigade_id: str):
        from brigades import draft_store

        try:
            return draft_store.review_for(brigade_id)
        except draft_store.DraftError as exc:
            return _fail(exc)

    @app.post("/api/brigadas/borrador", dependencies=[Depends(auth)])
    async def brigadas_borrador(body: DraftIn):
        """Guarda un BORRADOR a partir del JSON (sin modelo). Nunca lo activa."""
        from brigades import draft_store

        try:
            rec = draft_store.create_draft(body.draft, origen="json")
            return draft_store.review_for(rec["draft"]["id"])
        except draft_store.DraftError as exc:  # incluye DraftInvalid
            return _fail(exc)

    @app.post("/api/brigadas/{brigade_id}/restaurar", dependencies=[Depends(auth)])
    async def brigadas_restaurar(brigade_id: str, body: ActivarIn):
        """Vuelve un BORRADOR a una versión anterior (por su hash). Nunca activa nada: lo restaurado es otro borrador a revisar."""
        from brigades import draft_store

        try:
            draft_store.restore_version(brigade_id, body.hash)
            return draft_store.review_for(brigade_id)
        except draft_store.DraftError as exc:
            return _fail(exc)

    @app.post("/api/brigadas/crear", dependencies=[Depends(auth)])
    async def brigadas_crear(body: DescripcionIn):
        """Descripción en lenguaje natural -> BORRADOR (lo diseña el modelo local). Nunca lo activa."""
        from brigades import designer, draft_store

        try:
            async with locks.setdefault("_gestion", asyncio.Lock()):
                rec = await designer.design_from_description(body.descripcion)
            return draft_store.review_for(rec["draft"]["id"])
        except draft_store.DraftError as exc:
            return _fail(exc)
        except Exception as exc:  # noqa: BLE001 — p. ej. Ollama apagado
            logger.warning("diseño de brigada falló: %s", exc)
            return JSONResponse({"detail": f"No se pudo diseñar la brigada: {exc}"}, status_code=502)

    @app.post("/api/brigadas/{brigade_id}/activar", dependencies=[Depends(auth)])
    async def brigadas_activar(brigade_id: str, body: ActivarIn):
        """LA acción de aprobar: activa SOLO si el hash es el del contenido guardado. Firma la aprobación."""
        from brigades import draft_store

        try:
            rec = draft_store.activate(brigade_id, body.hash)
        except draft_store.DraftError as exc:
            return _fail(exc)
        return {"ok": True, "id": brigade_id, "estado": rec["estado"], "hash": rec["hash"]}

    @app.post("/api/brigadas/{brigade_id}/desactivar", dependencies=[Depends(auth)])
    async def brigadas_desactivar(brigade_id: str):
        from brigades import draft_store

        try:
            rec = draft_store.deactivate(brigade_id)
        except draft_store.DraftError as exc:
            return _fail(exc)
        return {"ok": True, "id": brigade_id, "estado": rec["estado"]}

    @app.delete("/api/brigadas/{brigade_id}", dependencies=[Depends(auth)])
    async def brigadas_descartar(brigade_id: str):
        from brigades import draft_store

        try:
            draft_store.discard(brigade_id)
        except draft_store.DraftError as exc:
            return _fail(exc)
        return {"ok": True, "id": brigade_id}

    # --- publicaciones de Video en Instagram: preparar lo hace un ayudante; APROBAR solo se alcanza desde acá (acción de Damian) ---
    @app.get("/api/publicaciones", dependencies=[Depends(auth)])
    async def publicaciones_listar():
        from app import publicaciones

        return {"publicaciones": publicaciones.listar()}

    @app.post("/api/publicaciones/{pid}/aprobar", dependencies=[Depends(auth)])
    async def publicaciones_aprobar(pid: str):
        from app import publicaciones

        try:
            return {"ok": True, **await asyncio.to_thread(publicaciones.aprobar_y_publicar, pid)}
        except publicaciones.PublicacionError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.post("/api/publicaciones/{pid}/descartar", dependencies=[Depends(auth)])
    async def publicaciones_descartar(pid: str):
        from app import publicaciones

        try:
            return {"ok": True, **publicaciones.descartar(pid)}
        except publicaciones.PublicacionError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=409)

    # --- editor de video: el MISMO proyecto que edita la IA (tools video_proyecto_*) se edita desde el panel ---
    def _autorizado(authorization: str | None, tk: str | None) -> bool:
        sent = (authorization or "").removeprefix("Bearer ").strip() or (tk or "")
        return secrets.compare_digest(sent, token)

    def _vfail(exc: Exception) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.get("/api/video/proyectos", dependencies=[Depends(auth)])
    async def video_proyectos():
        from app import video_edit, video_proyecto

        video_edit.asegurar_carpetas()
        return {"proyectos": video_proyecto.listar(), "carpeta": str(video_edit.base_dir())}

    @app.get("/api/video/medios", dependencies=[Depends(auth)])
    async def video_medios():
        from app import video_edit

        try:
            if not video_edit.efectos_dir().exists():
                await asyncio.to_thread(video_edit.generar_efectos)      # primera vez: se arma el pack de efectos de sonido
            return video_edit.listar()
        except video_edit.VideoError as exc:
            return _vfail(exc)

    @app.post("/api/video/proyectos", dependencies=[Depends(auth)])
    async def video_proyecto_nuevo(body: ProyectoNuevo):
        from app import video_proyecto

        try:
            return {"ok": True, "proyecto": video_proyecto.crear(body.nombre, body.formato)}
        except video_proyecto.ProyectoError as exc:
            return _vfail(exc)

    @app.get("/api/video/proyectos/{pid}", dependencies=[Depends(auth)])
    async def video_proyecto_leer(pid: str):
        from app import video_proyecto

        try:
            return video_proyecto.leer(pid)
        except video_proyecto.ProyectoError as exc:
            return _vfail(exc)

    @app.post("/api/video/proyectos/{pid}/ops", dependencies=[Depends(auth)])
    async def video_proyecto_ops(pid: str, body: OpsIn):
        from app import video_proyecto

        try:
            return {"ok": True, **video_proyecto.aplicar(pid, body.operaciones, "usuario", body.rev_base)}
        except video_proyecto.ProyectoError as exc:
            return _vfail(exc)

    @app.post("/api/video/proyectos/{pid}/deshacer", dependencies=[Depends(auth)])
    async def video_proyecto_deshacer(pid: str):
        from app import video_proyecto

        try:
            return {"ok": True, **video_proyecto.deshacer(pid, "usuario")}
        except video_proyecto.ProyectoError as exc:
            return _vfail(exc)

    @app.post("/api/video/proyectos/{pid}/rehacer", dependencies=[Depends(auth)])
    async def video_proyecto_rehacer(pid: str):
        from app import video_proyecto

        try:
            return {"ok": True, **video_proyecto.rehacer(pid, "usuario")}
        except video_proyecto.ProyectoError as exc:
            return _vfail(exc)

    @app.post("/api/video/proyectos/{pid}/render", dependencies=[Depends(auth)])
    async def video_proyecto_render(pid: str, body: RenderIn):
        from app import video_proyecto

        try:
            return {"ok": True, **await asyncio.to_thread(video_proyecto.renderizar, pid, body.calidad)}
        except video_proyecto.ProyectoError as exc:
            return _vfail(exc)

    @app.get("/api/video/media/{archivo:path}")
    async def video_media(archivo: str, authorization: str | None = Header(default=None), tk: str | None = None):
        """Sirve un archivo de la carpeta de video para el reproductor (con Range). `tk` = token en la URL: un <video> no manda cabeceras."""
        from fastapi.responses import FileResponse

        from app import video_edit

        if not _autorizado(authorization, tk):
            raise HTTPException(status_code=401, detail="token inválido")
        try:
            ruta = video_edit.resolver(archivo, video_edit.VIDEO_EXT | video_edit.AUDIO_EXT | video_edit.IMG_EXT)
        except video_edit.VideoError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from None
        tipos = {".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm", ".mkv": "video/x-matroska", ".avi": "video/x-msvideo",
                 ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".aac": "audio/aac", ".ogg": "audio/ogg", ".flac": "audio/flac",
                 ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif"}
        # `media_type` explícito: no depende del registro de tipos de Windows (mimetypes lo lee y a veces falla)
        return FileResponse(ruta, media_type=tipos.get(ruta.suffix.lower(), "application/octet-stream"), headers={"Cache-Control": "no-store"})

    app.state.token = token
    return app
