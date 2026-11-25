"""API de Raphael personal (versión 1): la misma forma que la de Empresas, pero contra el orquestador maestro.

Con `Authorization: Bearer <token>` salvo `GET /api/v1/health` y `POST /api/v1/login`. Un solo cerebro en la PC: el panel
de escritorio, la app del celular y la página web son clientes de esta API, con los mismos datos y la misma charla.
Las operaciones sobre el runtime van de a una (candado). Aprobar, rechazar y resolver son del humano: ningún endpoint
aprueba solo, y lo que es nivel `humano` no se puede aprobar, solo resolver con una respuesta.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import os
import secrets
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field
from raphael_core import ActionError, Runtime
from raphael_core.models import ModelsConfig

from raphael_empresas_api import configuracion
from raphael_empresas_api.app import ConfigIn, LoginIn, NewKeyIn, RejectIn, ResolveIn, is_same_pc
from raphael_empresas_api.auth import Auth

from . import API_VERSION, __version__, campos, cerebro
from .pagina import PAGINA

TICK_SECONDS = 60
PROBE_CACHE = 10.0
HEADERS = {"Cache-Control": "no-store", "X-Frame-Options": "DENY",
           "Content-Security-Policy": "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                                      "connect-src 'self'; img-src data:; frame-ancestors 'none'"}


SUFFIX = {"audio/wav": ".wav", "audio/x-wav": ".wav", "audio/ogg": ".ogg", "audio/mpeg": ".mp3", "audio/mp4": ".m4a"}


class CommandIn(BaseModel):
    brigade: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,39}$")
    cook: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,39}$")
    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,59}$")
    data: dict[str, Any] = Field(default_factory=dict)


class PairIn(BaseModel):
    code: str = Field(min_length=4, max_length=20)
    device: str = Field("", max_length=80)


PAIR_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # sin 0/O ni 1/I
PAIR_TTL = 300.0
WS_AUTH_SECONDS = 10.0


def phone_link_default():
    """El enlace con el celular de la brigada Operaciones (`link`), o None si esa brigada no está instalada."""
    try:
        from raphael_operaciones.adapters.phone import link
    except ImportError:
        return None
    return link


class ChatIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    session: str = Field("app", max_length=40, pattern=r"^[A-Za-z0-9_-]+$")


def pending_view(p: dict) -> dict:
    a = p.get("action") or {}
    kind = a.get("type") or p.get("kind")
    human = p["level"] == "humano"
    return {"id": p["id"], "type": kind, "brigade": p.get("brigade"), "level": p["level"], "summary": p.get("summary") or kind,
            "created": p.get("created"), "data": a.get("data") or {},
            "can": ["resolve"] if human else (["approve", "reject"] if p.get("kind") in ("action", "tool", "trust") else [])}


def create_app(rt: Runtime, *, report: dict | None = None, tick: bool = True, env_file: Path | None = None,
               environ: dict[str, str] | None = None, local_open: bool = False, models_path: str | Path | None = None,
               fetch: cerebro.Fetch = cerebro.http_get, speech: Any = None, phone_link: Any = None) -> FastAPI:
    """`report`: lo que devolvió `boot.start` (brigadas montadas, errores, pendientes).
    `env_file`: el `raphael.env` local donde la pantalla de Configuración guarda las claves (None = sin Configuración).
    `fetch`: cómo se mira si el modelo local responde (los tests ponen uno falso).
    `speech`: la voz hablada del orquestador (`speech_from`); None = sin voz (los endpoints dicen por qué).
    `phone_link`: el enlace con el celular de Operaciones (`register`, `handle_incoming`, `unregister`); None = se busca
    `raphael_operaciones.adapters.phone.link` al conectarse el celular.
    `local_open`: en la PC, los pedidos de esa misma PC entran sin clave (ver `is_same_pc`)."""
    environ = os.environ if environ is None else environ
    report = report or {}
    auth = Auth(rt.store, rt.clock)
    lock = asyncio.Lock()
    user = rt.installation.identity.user or "Damián"
    cfg: ModelsConfig = rt.models.config if rt.models is not None else cerebro.load(models_path, environ)
    watch = cerebro.LocalWatch(rt.notify, cfg, fetch)
    cache: dict[str, Any] = {"at": 0.0, "probe": []}

    async def probe(force: bool = False) -> list[dict]:
        if force or time.monotonic() - cache["at"] > PROBE_CACHE:
            cache["probe"] = await asyncio.to_thread(cerebro.probe_local, watch.cfg, fetch)
            cache["at"] = time.monotonic()
        return cache["probe"]

    async def watch_local() -> None:
        r = await asyncio.to_thread(watch.check)
        cache.update(at=time.monotonic(), probe=r["probe"])

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(_ticker()) if tick else None
        yield
        if task:
            task.cancel()

    async def _ticker() -> None:
        while True:
            try:
                await watch_local()
                async with lock:
                    await rt.tick()
            except Exception:  # noqa: BLE001 - un tick malo no tumba el servidor; el harness lo audita
                rt.audit.record("tick_fallido", who="api")
            await asyncio.sleep(TICK_SECONDS)

    app = FastAPI(title="Raphael personal", version=__version__, lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.auth = auth
    app.state.watch = watch

    def session(request: Request, authorization: str | None = Header(None)) -> dict:
        token = authorization[7:] if authorization and authorization.lower().startswith("bearer ") else None
        s = auth.check(token)
        if s is None and local_open and is_same_pc(request):
            s, token = {"local": True}, None
        if s is None:
            raise HTTPException(401, "sesión inválida o vencida: volvé a entrar con tu clave")
        request.state.token = token
        return s

    def _open(pid: int) -> dict:
        p = next((x for x in rt.approvals.list() if x["id"] == pid), None)
        if p is None:
            raise HTTPException(404, f"el pendiente #{pid} no existe o ya se resolvió")
        return p

    # --- sin sesión
    @app.get("/api/v1/health")
    async def health() -> dict:
        return {"ok": rt.orchestrator is not None, "api": API_VERSION, "version": __version__, "edition": "personal",
                "ready": auth.has_key(), "brigades": sorted(rt.brigades)}

    @app.post("/api/v1/login")
    async def login(body: LoginIn, request: Request) -> dict:
        who = request.client.host if request.client else "?"
        if not auth.has_key():
            raise HTTPException(409, "todavía no hay clave: ponela en el servidor con 'arrancar-personal.bat clave'")
        if auth.locked(who):
            raise HTTPException(429, "demasiados intentos: esperá unos minutos")
        token = auth.login(body.key, who, body.device)
        if token is None:
            rt.bus.publish("acceso.fallido", {"source": who, "device": body.device[:40], "locked": auth.locked(who)},
                           source="servidor")       # lo escucha Seguridad (nunca lleva la clave probada)
            raise HTTPException(429 if auth.locked(who) else 401, "clave incorrecta")
        rt.audit.record("app_login", who=user, dispositivo=body.device[:40])
        return {"token": token, "user": user}

    @app.get("/", response_class=HTMLResponse)
    @app.get("/config", response_class=HTMLResponse)
    async def pagina() -> HTMLResponse:
        return HTMLResponse(PAGINA, headers=HEADERS)

    @app.post("/api/v1/logout")
    async def logout(request: Request, s: dict = Depends(session)) -> dict:
        if request.state.token:
            auth.logout(request.state.token)
        return {"ok": True}

    # --- hablar con Raphael
    @app.post("/api/v1/chat")
    async def chat(body: ChatIn, s: dict = Depends(session)) -> dict:
        async with lock:
            r = await rt.talk_to_owner(body.text, session=f"app-{body.session}", channel="app")
        d = r.to_dict()
        d["meta"] = {"warnings": (d.get("meta") or {}).get("warnings", [])}
        return d

    # --- celular: emparejamiento por código (QR) y WebSocket de Operaciones
    pairing: dict[str, float] = {}      # hash del código -> vence (monotonic); de un solo uso

    @app.post("/api/v1/phone/pair")
    async def phone_pair(s: dict = Depends(session)) -> dict:
        """Un código de un solo uso (5 minutos) para emparejar el celular. El QR lleva `payload`; sin `segno` no hay imagen."""
        now = time.monotonic()
        for h in [h for h, t in pairing.items() if t < now]:
            pairing.pop(h)
        if len(pairing) >= 5:
            raise HTTPException(429, "ya hay códigos sin usar: esperá a que venzan o usalos")
        code = "".join(secrets.choice(PAIR_ALPHABET) for _ in range(8))
        pairing[hashlib.sha256(code.encode()).hexdigest()] = now + PAIR_TTL
        base = environ.get("RAPHAEL_PUBLIC_URL", "").rstrip("/")
        payload = f"raphael://pair?host={base}&code={code}" if base else f"raphael://pair?code={code}"
        out = {"code": code, "expires_in": int(PAIR_TTL), "payload": payload, "host": base, "qr_svg": ""}
        try:
            import io

            import segno

            buf = io.BytesIO()
            segno.make(payload).save(buf, kind="svg", scale=6)
            out["qr_svg"] = buf.getvalue().decode()
        except Exception:  # noqa: BLE001 - sin la librería (o falla): queda el texto del payload
            pass
        rt.audit.record("celular_codigo", who=user)
        return out

    @app.post("/api/v1/phone/redeem")
    async def phone_redeem(body: PairIn, request: Request) -> dict:
        """El celular canjea el código por una sesión. Sin sesión previa; el mismo tope de intentos que la clave."""
        who = request.client.host if request.client else "?"
        if auth.locked(who):
            raise HTTPException(429, "demasiados intentos: esperá unos minutos")
        h = hashlib.sha256(body.code.strip().upper().encode()).hexdigest()
        exp = pairing.pop(h, None)
        if exp is None or exp < time.monotonic():
            auth.fail(who)
            rt.bus.publish("acceso.fallido", {"source": who, "device": body.device[:40], "locked": auth.locked(who),
                                              "via": "emparejamiento"}, source="servidor")
            raise HTTPException(401, "código inválido o vencido")
        rt.audit.record("celular_emparejado", who=user, dispositivo=body.device[:40])
        return {"token": auth.issue(body.device or "celular"), "user": user}

    @app.websocket("/ws/phone")
    async def ws_phone(ws: WebSocket) -> None:
        """El celular de Operaciones. Se identifica con `Authorization: Bearer` o con un primer mensaje `{"token": …}` (nunca
        por la dirección, que queda en los registros). Cada mensaje siguiente va a `link.handle_incoming`."""
        link = phone_link or phone_link_default()
        if link is None:
            await ws.close(code=1013, reason="Operaciones no está instalada")
            return
        h = ws.headers.get("authorization", "")
        token = h[7:] if h.lower().startswith("bearer ") else None
        await ws.accept()
        if token is None:
            try:
                first = await asyncio.wait_for(ws.receive_json(), WS_AUTH_SECONDS)
                token = first.get("token") if isinstance(first, dict) else None
            except (TimeoutError, ValueError, WebSocketDisconnect):
                token = None
        if auth.check(token) is None:
            who = ws.client.host if ws.client else "?"
            rt.bus.publish("acceso.fallido", {"source": who, "device": "", "locked": False, "via": "ws/phone"}, source="servidor")
            await ws.close(code=1008, reason="sesión inválida")
            return
        await link.register(ws)
        rt.audit.record("celular_conectado", who=user)
        try:
            while True:
                await link.handle_incoming(await ws.receive_text())
        except WebSocketDisconnect:
            pass
        finally:
            await link.unregister(ws)
            rt.audit.record("celular_desconectado", who=user)

    # --- comandos y eventos (para los clientes de las brigadas, ej. el globo de Geolocalización: pines, capa, pin.agregado)
    @app.post("/api/v1/command")
    async def command(body: CommandIn, s: dict = Depends(session)) -> Any:
        """Un comando de un cocinero (`rt.command`), por el mismo harness: lo que tiene efecto sigue pidiendo aprobación."""
        try:
            async with lock:
                return await rt.command(body.brigade, body.cook, body.name, body.data, who=user)
        except ActionError as exc:
            raise HTTPException(400, str(exc)) from None

    @app.get("/api/v1/events")
    async def events(event: str = "", limit: int = 50, s: dict = Depends(session)) -> dict:
        """Últimos eventos del bus (`pin.agregado`…), del más viejo al más nuevo. Sin cursor: el cliente descarta repetidos."""
        rows = [{"event": e, "data": d} for e, d in rt.bus.history if not event or e == event or e.startswith(event + ".")]
        return {"items": rows[-max(1, min(limit, 200)):]}

    # --- voz hablada (oír y hablar); el audio y el texto no salen de la PC
    async def _voz():
        if speech is None:
            raise HTTPException(503, "la voz no está instalada en este servidor (ver orquestador.env.plantilla)")
        return speech

    @app.get("/api/v1/voz")
    async def voz_estado(refresh: bool = False, s: dict = Depends(session)) -> dict:
        if speech is None:
            return {"kind": "off", "enabled": False, "motivo": "la voz no está instalada en este servidor"}
        return await speech.status(refresh)

    @app.post("/api/v1/voz/transcribir")
    async def voz_transcribir(request: Request, s: dict = Depends(session)) -> dict:
        """Cuerpo = el audio crudo (webm, wav, ogg…). Devuelve el texto; no lo manda al orquestador (eso lo decide el cliente)."""
        sp = await _voz()
        data = await request.body()
        kind = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
        suffix = SUFFIX.get(kind, ".webm")
        try:
            return await sp.transcribe(data, suffix)
        except Exception as exc:  # noqa: BLE001 - SpeechError y fallas del subproceso: mensaje claro, no un 500
            raise HTTPException(422, str(exc)[:300]) from None

    @app.post("/api/v1/voz/hablar")
    async def voz_hablar(body: ChatIn, s: dict = Depends(session)) -> Response:
        sp = await _voz()
        try:
            audio = await sp.speak(body.text)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(422, str(exc)[:300]) from None
        return Response(audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})

    # --- estado
    @app.get("/api/v1/summary")
    async def summary(s: dict = Depends(session)) -> dict:
        ps = rt.approvals.list()
        st = rt.status()
        pr = await probe()
        return {"user": user, "pending": len(ps), "pending_human": sum(1 for p in ps if p["level"] == "humano"),
                "brigades": sorted(rt.brigades), "not_installed": report.get("pending", []),
                "errors": {k: v[:200] for k, v in (report.get("errors") or {}).items()},
                "local_model": cerebro.local_ready(pr), "usage": {"messages": st["usage"].get("messages")},
                "notices": len(rt.notices(unseen_only=True)), "warnings": st["warnings"][:10]}

    @app.get("/api/v1/brain")
    async def brain(refresh: bool = False, s: dict = Depends(session)) -> dict:
        return cerebro.status(watch.cfg, await probe(refresh), rt.models)

    @app.get("/api/v1/brigades")
    async def brigades(s: dict = Depends(session)) -> dict:
        inst = rt.installation
        return {"items": [{"id": b, "active": t.active, "mounted": b in rt.brigades, "private": b in watch.cfg.private,
                           "not_installed": b in report.get("pending", [])} for b, t in sorted(inst.brigades.items())]}

    def seen_upto() -> int:
        return int((rt.store.space("_api").get("notices", "seen") or {}).get("upto", 0))

    @app.get("/api/v1/updates")
    async def updates(s: dict = Depends(session)) -> dict:
        ps = rt.approvals.list()
        upto = seen_upto()
        new = [n for n in rt.notices() if n["id"] > upto]
        return {"pending": len(ps), "pending_human": sum(1 for p in ps if p["level"] == "humano"),
                "latest": max((p["id"] for p in ps), default=0),
                "items": [{"id": p["id"], "summary": p.get("summary", "")[:140], "level": p["level"]} for p in ps[-5:]],
                "notices_unseen": len(new), "notice_latest": max((n["id"] for n in new), default=upto),
                "notice_last": new[-1]["text"][:200] if new else ""}

    @app.get("/api/v1/notices")
    async def notices(s: dict = Depends(session)) -> dict:
        upto = seen_upto()
        items = [{"id": n["id"], "text": n["text"], "when": n["when"], "kind": (n.get("data") or {}).get("kind", ""),
                  "seen": n["id"] <= upto} for n in rt.notices()[-30:]][::-1]
        return {"items": items, "unseen": sum(1 for i in items if not i["seen"])}

    @app.post("/api/v1/notices/seen")
    async def notices_seen(s: dict = Depends(session)) -> dict:
        rt.store.space("_api").put("notices", "seen", {"upto": max((n["id"] for n in rt.notices()), default=0)})
        return {"unseen": 0}

    # --- aprobaciones: solo las resuelve la persona
    @app.get("/api/v1/pending")
    async def pending(s: dict = Depends(session)) -> dict:
        return {"items": [pending_view(p) for p in rt.approvals.list()]}

    @app.post("/api/v1/pending/{pid}/approve")
    async def approve(pid: int, s: dict = Depends(session)) -> dict:
        p = _open(pid)
        if p["level"] == "humano":
            raise HTTPException(409, "esto lo resolvés vos: usá 'resolver' con tu respuesta")
        try:
            async with lock:
                r = await rt.approve(pid, None, who=user)
        except ActionError as exc:
            raise HTTPException(409, str(exc)) from None
        if r.get("state") == "error":
            raise HTTPException(400, r.get("error") or "no se pudo")
        return {"state": r["state"], "text": r.get("text")}

    @app.post("/api/v1/pending/{pid}/reject")
    async def reject(pid: int, body: RejectIn, s: dict = Depends(session)) -> dict:
        _open(pid)
        async with lock:
            r = await rt.reject(pid, body.reason, who=user)
        return {"state": r["state"]}

    @app.post("/api/v1/pending/{pid}/resolve")
    async def resolve(pid: int, body: ResolveIn, s: dict = Depends(session)) -> dict:
        p = _open(pid)
        if p["level"] != "humano":
            raise HTTPException(409, "esto se aprueba o se rechaza")
        async with lock:
            r = await rt.resolve(pid, body.reply.strip() or None, who=user)
        return {"state": r["state"]}

    # --- configuración
    async def _config_view(restart: list[str] | None = None) -> dict:
        if env_file is None:
            raise HTTPException(404, "este servidor no tiene pantalla de Configuración")
        items = campos.check(environ, app_key_set=auth.has_key(), probe=await probe(), pending=report.get("pending", []),
                             errors=report.get("errors") or {}, mounted=sorted(rt.brigades),
                             orchestrator_ok=rt.orchestrator is not None)
        return {"fields": configuracion.view(environ, campos.FIELDS), "checks": [vars(i) for i in items],
                "restart_needed": restart or [], "initial_key_file": (env_file.parent / "clave-inicial.txt").is_file()}

    @app.get("/api/v1/config")
    async def config_get(s: dict = Depends(session)) -> dict:
        return await _config_view()

    @app.put("/api/v1/config")
    async def config_put(body: ConfigIn, s: dict = Depends(session)) -> dict:
        if env_file is None:
            raise HTTPException(404, "este servidor no tiene pantalla de Configuración")
        try:
            async with lock:
                trial = {**environ}
                for n in body.clear:
                    trial.pop(n, None)
                trial.update({k: v.strip() for k, v in body.set.items()})
                new_cfg = cerebro.load(models_path, trial)         # si la combinación no sirve, no se guarda nada
                restart = configuracion.apply(env_file, environ, body.set, body.clear, campos.BY_NAME, campos.extra_check)
                watch.cfg = new_cfg
                if rt.models is not None:
                    rt.models.config = new_cfg
                    rt.models.set_env(dict(environ))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        rt.audit.record("config_cambiada", who=user, puso=sorted(body.set), saco=sorted(body.clear))   # solo nombres
        return await _config_view(restart)

    @app.post("/api/v1/config/clave")
    async def config_key(body: NewKeyIn, s: dict = Depends(session)) -> dict:
        """Cambia la clave de la app. Cierra todas las sesiones: el cliente entra de nuevo con la clave nueva."""
        try:
            auth.set_key(body.key)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        if env_file is not None:
            with contextlib.suppress(OSError):
                (env_file.parent / "clave-inicial.txt").unlink()
        rt.audit.record("clave_app_cambiada", who=user)
        return {"ok": True}

    return app
