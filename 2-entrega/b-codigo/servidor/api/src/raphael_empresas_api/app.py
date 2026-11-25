"""Rutas de la API (versión 1). Contrato completo en API.md.

Todo con `Authorization: Bearer <token>` salvo `GET /api/v1/health` y `POST /api/v1/login`. Las operaciones sobre el
runtime van de a una (candado): el harness y su SQLite no están pensados para escrituras en paralelo.
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import json
import os
import re
from collections.abc import AsyncIterator
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field
from raphael_core import ActionError, Runtime

from . import API_VERSION, __version__, configuracion, puentes
from .auth import Auth
from .entorno import check
from .meta import MetaChannel, parse_webhook, verify_signature
from .pagina import PAGINA

BRIGADE = "empresas"
TICK_SECONDS = 60

#: campos que la dueña puede cambiar al aprobar, por tipo de acción, con su tipo
EDITABLE: dict[str, dict[str, str]] = {
    "enviar_presupuesto": {"price": "money"},
    "confirmar_pago": {"amount": "money"},
    "confirmar_turno": {"date": "date", "time": "time"},
    "cancelar_pedido": {},
}
STATUSES = ("en_confeccion", "prueba", "listo", "entregado", "cancelado")


class LoginIn(BaseModel):
    key: str = Field(min_length=1, max_length=200)
    device: str = Field("", max_length=80)


class ConfigIn(BaseModel):
    set: dict[str, str] = Field(default_factory=dict)
    clear: list[str] = Field(default_factory=list, max_length=40)


class NewKeyIn(BaseModel):
    key: str = Field(max_length=200)


class ApproveIn(BaseModel):
    changes: dict[str, Any] = Field(default_factory=dict)


class RejectIn(BaseModel):
    reason: str = Field("", max_length=500)


class ResolveIn(BaseModel):
    reply: str = Field("", max_length=2000)


class SecretaryIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    session: str = Field("app", max_length=40, pattern=r"^[A-Za-z0-9_-]+$")


class StatusIn(BaseModel):
    status: str


def _coerce(kind: str, value: Any) -> Any:
    if kind == "money":
        try:
            v = float(value)
        except (TypeError, ValueError):
            raise HTTPException(422, "el monto tiene que ser un número") from None
        if not 0 < v <= 100_000_000:
            raise HTTPException(422, "el monto está fuera de rango")
        return v
    if kind == "date":
        try:
            return date.fromisoformat(str(value)).isoformat()
        except ValueError:
            raise HTTPException(422, "la fecha tiene que ser AAAA-MM-DD") from None
    if kind == "time":
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(value)):
            raise HTTPException(422, "la hora tiene que ser HH:MM")
        return str(value)
    raise HTTPException(422, "campo no editable")


def hmac_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


LOCAL_NAMES = ("127.0.0.1", "localhost", "::1")


def is_same_pc(request: Request) -> bool:
    """Pedido hecho desde esta misma PC, directo al servidor. Un túnel (Tailscale Funnel) o un proxy (Caddy) también
    conectan desde 127.0.0.1, así que además se exige que no traiga encabezados de reenvío y que se haya pedido a un
    nombre local. `Origin` y `Sec-Fetch-Site` frenan a una página ajena abierta en el navegador de esta PC."""
    h = request.headers
    if request.client is None or request.client.host not in ("127.0.0.1", "::1"):
        return False
    if any(k.startswith(("x-forwarded", "forwarded", "tailscale", "x-real-ip", "via", "cf-")) for k in h):
        return False
    host = h.get("host", "")
    if urlsplit("//" + host).hostname not in LOCAL_NAMES:
        return False
    if h.get("origin") not in (None, f"http://{host}"):
        return False
    return h.get("sec-fetch-site") in (None, "same-origin", "none")


def pending_view(p: dict) -> dict:
    a = p.get("action") or {}
    kind = a.get("type") or p.get("kind")
    human = p["level"] == "humano"
    return {"id": p["id"], "type": kind, "level": p["level"], "summary": p.get("summary") or kind,
            "contact": a.get("target"), "created": p.get("created"), "data": a.get("data") or {},
            "editable": sorted(EDITABLE.get(kind, {})) if not human else [],
            "can": ["resolve"] if human else (["approve", "reject"] if p.get("kind") in ("action", "tool", "trust") else [])}


def create_app(rt: Runtime, *, tick: bool = True, meta: MetaChannel | None = None, env_file: Path | None = None,
               environ: dict[str, str] | None = None, local_open: bool = False) -> FastAPI:
    """`meta`: el canal de WhatsApp e Instagram (sus conectores ya tienen que estar en el runtime); None = sin webhooks.
    `env_file`: el `raphael.env` local donde la pantalla de Configuración guarda las claves (None = sin Configuración).
    `environ`: el entorno del proceso que se cambia en caliente (por defecto `os.environ`).
    `local_open`: en la PC de la dueña, los pedidos de esa misma PC entran sin clave (ver `is_same_pc`)."""
    environ = os.environ if environ is None else environ
    auth = Auth(rt.store, rt.clock)
    lock = asyncio.Lock()
    owner = rt.installation.identity.user or "dueña"
    background: set[asyncio.Task] = set()

    def drain_failures() -> int:
        """Los mensajes que Meta no aceptó (o que no se podían mandar): un aviso para la dueña por cada uno."""
        n = 0
        while meta is not None and meta.outbox.failures:
            f = meta.outbox.failures.popleft()
            rt.notify(f"No le pude mandar el mensaje a {f.contact}: {f.reason}. Escribile vos: «{f.text[:200]}»",
                      kind="envio_fallido", contact=f.contact)
            n += 1
        return n

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(_ticker()) if tick else None
        yield
        if task:
            task.cancel()

    async def _ticker() -> None:
        while True:
            await asyncio.sleep(TICK_SECONDS)
            try:
                async with lock:
                    await rt.tick()
                    drain_failures()
            except Exception:  # noqa: BLE001 - un tick malo no tumba el servidor; el harness lo audita
                rt.audit.record("tick_fallido", who="api")

    app = FastAPI(title="Raphael Empresas", version=__version__, lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.auth = auth

    def session(request: Request, authorization: str | None = Header(None)) -> dict:
        token = authorization[7:] if authorization and authorization.lower().startswith("bearer ") else None
        s = auth.check(token)
        if s is None and local_open and is_same_pc(request):
            s, token = {"local": True}, None
        if s is None:
            raise HTTPException(401, "sesión inválida o vencida: volvé a entrar con tu clave")
        request.state.token = token
        return s

    def with_key(s: dict = Depends(session)) -> dict:
        """Modo mixto: lo que manda, ejecuta o cambia claves pide la clave aunque se esté en la misma PC. La Secretaria
        entra acá porque por chat también aprueba."""
        if s.get("local"):
            raise HTTPException(403, "para esto hace falta la clave: entrá con tu clave y repetilo")
        return s

    async def cmd(cook: str, name: str, data: dict | None = None) -> Any:
        try:
            async with lock:
                return await rt.command(BRIGADE, cook, name, data, who=owner)
        except ActionError as exc:
            raise HTTPException(400, str(exc)) from None

    def _open(pid: int) -> dict:
        p = next((x for x in rt.approvals.list() if x["id"] == pid), None)
        if p is None:
            raise HTTPException(404, f"el pendiente #{pid} no existe o ya se resolvió")
        return p

    # --- sin sesión
    @app.get("/api/v1/health")
    async def health() -> dict:
        m = rt.brigades.get(BRIGADE)
        return {"ok": m is not None, "api": API_VERSION, "version": __version__, "brigade": BRIGADE,
                "brigade_version": m.manifest.version if m else None, "ready": auth.has_key()}

    @app.post("/api/v1/login")
    async def login(body: LoginIn, request: Request) -> dict:
        who = request.client.host if request.client else "?"
        if not auth.has_key():
            raise HTTPException(409, "todavía no hay clave: ponela en el servidor con 'raphael-empresas-api clave'")
        if auth.locked(who):
            raise HTTPException(429, "demasiados intentos: esperá unos minutos")
        token = auth.login(body.key, who, body.device)
        if token is None:
            rt.bus.publish("acceso.fallido", {"source": who, "device": body.device[:40], "locked": auth.locked(who)},
                           source="servidor")       # lo escucha Seguridad (nunca lleva la clave probada)
            raise HTTPException(429 if auth.locked(who) else 401, "clave incorrecta")
        rt.audit.record("app_login", who=owner, dispositivo=body.device[:40])
        return {"token": token, "user": owner, "business": _business_name()}

    def _business_name() -> str:
        cfg = rt.installation.brigade_config(BRIGADE)
        return ((cfg.get("business") or {}).get("name")) or ""

    # --- webhooks de Meta (sin sesión: los firma Meta)
    @app.get("/webhook/meta", response_class=PlainTextResponse)
    async def meta_verify(request: Request) -> str:
        q = request.query_params
        token = meta.settings.verify_token if meta else ""
        if q.get("hub.mode") == "subscribe" and token and hmac_eq(q.get("hub.verify_token", ""), token):
            return q.get("hub.challenge", "")
        raise HTTPException(403, "token de verificación inválido")

    @app.post("/webhook/meta")
    async def meta_webhook(request: Request) -> dict:
        if meta is None:
            raise HTTPException(404, "este servidor no tiene el canal de Meta")
        body = await request.body()
        signed = verify_signature(meta.settings.app_secret, body, request.headers.get("x-hub-signature-256"))
        if (meta.settings.real or meta.settings.app_secret) and not signed:
            raise HTTPException(403, "firma inválida")
        try:
            payload = json.loads(body or b"{}")
        except ValueError:
            raise HTTPException(400, "cuerpo inválido") from None
        msgs = [m for m in parse_webhook(payload) if meta.first_time(m.mid)]
        if msgs:                                   # se contesta enseguida (Meta reintenta si tardamos) y se procesa atrás
            task = asyncio.create_task(_process(msgs))
            background.add(task)
            task.add_done_callback(background.discard)
        return {"received": len(msgs)}

    async def _process(msgs: list) -> None:
        for m in msgs:
            try:
                async with lock:
                    await rt.receive(m.channel, m.sender, m.text, m.name, m.attachment)
                    drain_failures()
            except Exception as exc:  # noqa: BLE001 - un mensaje que rompe no frena a los demás
                rt.audit.record("webhook_fallido", who="api", canal=m.channel, error=type(exc).__name__)

    # --- webhook de Mercado Pago (sin sesión: lo firma Mercado Pago; la firma la verifica la brigada de Cobros)
    @app.post("/webhook/mercadopago")
    async def mp_webhook(request: Request) -> dict:
        """Mercado Pago avisa que hay un pago. Se contesta enseguida y se procesa atrás: la brigada verifica la firma
        (sin MP_WEBHOOK_SECRET no acepta nada), lee el pago y deja la confirmación PENDIENTE para la dueña. Nunca confirma."""
        try:
            payload = json.loads((await request.body()) or b"{}")
        except ValueError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        q = dict(request.query_params)
        kind = str(q.get("type") or q.get("topic") or payload.get("type") or "payment")
        pid = str(q.get("data.id") or q.get("id") or (payload.get("data") or {}).get("id") or "")
        if kind != "payment" or not re.fullmatch(r"\d{1,20}", pid):
            return {"received": 0}
        q["data.id"] = pid
        data = {"payment_id": pid, "headers": dict(request.headers), "query": q}
        task = asyncio.create_task(_mp_process(data))
        background.add(task)
        task.add_done_callback(background.discard)
        return {"received": 1}

    async def _mp_process(data: dict) -> None:
        try:
            async with lock:
                await rt.command(BRIGADE, "cobros", "mp_aviso", data, who="mercadopago")
        except Exception as exc:  # noqa: BLE001 - un aviso que rompe no tumba el servidor
            rt.audit.record("webhook_mp_fallido", who="api", error=type(exc).__name__)

    app.state.process_pending = lambda: asyncio.gather(*background)

    # --- con sesión
    @app.get("/api/v1/channels")
    async def channels(s: dict = Depends(session)) -> dict:
        if meta is None:
            return {"mode": None, "channels": [], "problems": ["el servidor no tiene el canal de Meta"]}
        drain_failures()
        return {"mode": meta.settings.mode, "channels": sorted(rt.connectors), "problems": meta.settings.problems(),
                "graph_version": meta.settings.graph_version}

    # --- configuración (claves a voluntad, solo con sesión; nunca se devuelven completas)
    @app.get("/", response_class=HTMLResponse)
    @app.get("/config", response_class=HTMLResponse)
    async def pagina() -> HTMLResponse:
        return HTMLResponse(PAGINA, headers={"Cache-Control": "no-store", "X-Frame-Options": "DENY",
                                             "Content-Security-Policy": "default-src 'self'; style-src 'unsafe-inline'; "
                                                                        "script-src 'unsafe-inline'; frame-ancestors 'none'"})

    def _config_view(restart: list[str] | None = None) -> dict:
        if env_file is None:
            raise HTTPException(404, "este servidor no tiene pantalla de Configuración")
        items = check(env=environ, installation=rt.installation, models=rt.models,
                      meta=meta.settings if meta else _no_meta(), app_key_set=auth.has_key(),
                      env_files=[env_file.name] if env_file.is_file() else [], public_url=environ.get("RAPHAEL_PUBLIC_URL", ""))
        return {"fields": configuracion.view(environ), "checks": [vars(i) for i in items],
                "restart_needed": restart or [], "initial_key_file": (env_file.parent / "clave-inicial.txt").is_file()}

    def _no_meta() -> Any:
        from .meta import MetaSettings

        return MetaSettings()

    @app.get("/api/v1/config")
    async def config_get(s: dict = Depends(session)) -> dict:
        return _config_view()

    @app.put("/api/v1/config")
    async def config_put(body: ConfigIn, s: dict = Depends(with_key)) -> dict:
        if env_file is None:
            raise HTTPException(404, "este servidor no tiene pantalla de Configuración")
        try:
            async with lock:
                restart = configuracion.apply(env_file, environ, body.set, body.clear)
                for shown in {*body.clear} & set(puentes.ALIASES.values()):   # sacar MP_* saca también su nombre de la brigada
                    environ.pop(next(k for k, v in puentes.ALIASES.items() if v == shown), None)
                puentes.apply_aliases(environ)
                if rt.models is not None:
                    rt.models.set_env(dict(environ))
                if meta is not None:
                    from .meta import settings_from_env

                    meta.reconfigure(settings_from_env(environ), rt)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        rt.audit.record("config_cambiada", who=owner, puso=sorted(body.set), saco=sorted(body.clear))   # solo nombres
        return _config_view(restart)

    @app.post("/api/v1/config/clave")
    async def config_key(body: NewKeyIn, request: Request, s: dict = Depends(with_key)) -> dict:
        """Cambia la clave de la app. Cierra todas las sesiones: la app entra de nuevo con la clave nueva."""
        try:
            auth.set_key(body.key)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        if env_file is not None:
            with contextlib.suppress(OSError):
                (env_file.parent / "clave-inicial.txt").unlink()
        rt.audit.record("clave_app_cambiada", who=owner)
        return {"ok": True}

    @app.post("/api/v1/logout")
    async def logout(request: Request, s: dict = Depends(session)) -> dict:
        if request.state.token:
            auth.logout(request.state.token)
        return {"ok": True}

    @app.get("/api/v1/summary")
    async def summary(s: dict = Depends(session)) -> dict:
        ps = rt.approvals.list()
        st = rt.status()
        b = st["brigades"].get(BRIGADE) or {}
        return {"user": owner, "business": _business_name(), "pending": len(ps),
                "pending_human": sum(1 for p in ps if p["level"] == "humano"),
                "cooks": b.get("cooks", {}), "health": b.get("health"), "usage": {"messages": st["usage"].get("messages")},
                "notices": len(rt.notices(unseen_only=True)), "warnings": st["warnings"][:10]}

    def seen_upto() -> int:
        return int((rt.store.space("_api").get("notices", "seen") or {}).get("upto", 0))

    def unseen() -> list[dict]:
        drain_failures()
        upto = seen_upto()
        return [n for n in rt.notices() if n["id"] > upto]

    @app.get("/api/v1/updates")
    async def updates(s: dict = Depends(session)) -> dict:
        ps = rt.approvals.list()
        new = unseen()
        return {"pending": len(ps), "pending_human": sum(1 for p in ps if p["level"] == "humano"),
                "latest": max((p["id"] for p in ps), default=0),
                "items": [{"id": p["id"], "summary": p.get("summary", "")[:140], "level": p["level"]} for p in ps[-5:]],
                "notices_unseen": len(new), "notice_latest": max((n["id"] for n in new), default=seen_upto()),
                "notice_last": new[-1]["text"][:200] if new else ""}

    @app.get("/api/v1/pending")
    async def pending(s: dict = Depends(session)) -> dict:
        return {"items": [pending_view(p) for p in rt.approvals.list()]}

    @app.post("/api/v1/pending/{pid}/approve")
    async def approve(pid: int, body: ApproveIn, s: dict = Depends(with_key)) -> dict:
        p = _open(pid)
        if p["level"] == "humano":
            raise HTTPException(409, "esto lo resolvés vos: usá 'resolver' con tu respuesta")
        kind = (p.get("action") or {}).get("type") or p.get("kind")
        allowed = EDITABLE.get(kind, {})
        bad = sorted(set(body.changes) - set(allowed))
        if bad:
            raise HTTPException(422, f"no se puede cambiar: {', '.join(bad)}")
        changes = {k: _coerce(allowed[k], v) for k, v in body.changes.items()}
        try:
            async with lock:
                r = await rt.approve(pid, changes or None, who=owner)
        except ActionError as exc:
            raise HTTPException(409, str(exc)) from None
        if r.get("state") == "error":
            raise HTTPException(400, r.get("error") or "no se pudo")
        return {"state": r["state"], "text": r.get("text")}

    @app.post("/api/v1/pending/{pid}/reject")
    async def reject(pid: int, body: RejectIn, s: dict = Depends(with_key)) -> dict:
        _open(pid)
        async with lock:
            r = await rt.reject(pid, body.reason, who=owner)
        return {"state": r["state"]}

    @app.post("/api/v1/pending/{pid}/resolve")
    async def resolve(pid: int, body: ResolveIn, s: dict = Depends(with_key)) -> dict:
        p = _open(pid)
        if p["level"] != "humano":
            raise HTTPException(409, "esto se aprueba o se rechaza")
        async with lock:
            r = await rt.resolve(pid, body.reply.strip() or None, who=owner)
        return {"state": r["state"]}

    @app.post("/api/v1/secretary")
    async def secretary(body: SecretaryIn, s: dict = Depends(with_key)) -> dict:
        async with lock:
            r = await rt.talk_to_owner(body.text, session=f"app-{body.session}", channel="app")
        d = r.to_dict()
        d["meta"] = {"warnings": (d.get("meta") or {}).get("warnings", [])}
        return d

    @app.get("/api/v1/orders")
    async def orders(all: bool = False, s: dict = Depends(session)) -> dict:
        items = await cmd("encargos", "listar", {"all": all})
        return {"items": sorted(items, key=lambda o: o.get("number", 0), reverse=True)}

    @app.get("/api/v1/orders/{num}")
    async def order(num: int, s: dict = Depends(session)) -> dict:
        return await cmd("encargos", "ver", {"number": num})

    @app.post("/api/v1/orders/{num}/status")
    async def order_status(num: int, body: StatusIn, s: dict = Depends(with_key)) -> dict:
        if body.status not in STATUSES:
            raise HTTPException(422, f"estado inválido; válidos: {', '.join(STATUSES)}")
        return await cmd("encargos", "estado", {"number": num, "status": body.status})

    @app.get("/api/v1/appointments")
    async def appointments(s: dict = Depends(session)) -> dict:
        return {"items": await cmd("agenda", "turnos")}

    @app.get("/api/v1/deposits")
    async def deposits(s: dict = Depends(session)) -> dict:
        return {"waiting": await cmd("cobros", "esperando"), "notified": await cmd("cobros", "avisados")}

    @app.get("/api/v1/questions")
    async def questions(s: dict = Depends(session)) -> dict:
        return {"items": await cmd("atencion", "dudas")}

    @app.get("/api/v1/catalog")
    async def catalog(q: str = "", s: dict = Depends(session)) -> dict:
        state = await cmd("tienda", "catalogo")
        items = await cmd("tienda", "productos", {"q": q[:100]} if q else {})
        return {"state": state, "items": items[:200]}

    @app.get("/api/v1/conversation/{contact}")
    async def conversation(contact: str, s: dict = Depends(session)) -> dict:
        if not re.fullmatch(r"[a-z]+:[\w.+@-]{1,80}", contact):
            raise HTTPException(422, "contacto inválido")
        return {"items": [{"from": m.get("from"), "text": m.get("text"), "when": m.get("when")}
                          for m in rt.conversation(contact)[-30:]]}

    @app.get("/api/v1/notices")
    async def notices(s: dict = Depends(session)) -> dict:
        drain_failures()
        upto = seen_upto()
        return {"items": [{"id": n["id"], "text": n["text"], "when": n["when"], "kind": (n.get("data") or {}).get("kind", ""),
                           "seen": n["id"] <= upto} for n in rt.notices()[-30:]][::-1], "unseen": len(unseen())}

    @app.post("/api/v1/notices/seen")
    async def notices_seen(s: dict = Depends(session)) -> dict:
        latest = max((n["id"] for n in rt.notices()), default=0)
        rt.store.space("_api").put("notices", "seen", {"upto": latest})
        return {"unseen": 0}

    return app
