import asyncio
import json
import logging
import time
from pathlib import Path

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from . import chat_link, mission_control, pairing, user_config
from .agent import get_display_history, run_agent
from .auth import _scope_for, verify_api_key, verify_read
from .config import settings
from .llm_client import client
from .logging_config import configure_logging
from .ingestion import playlist_watcher
from .malware import behavioral_watcher, fullscan
from .obsidian import consolidation, curiosity
from .models import ChatMirrorMessage, ChatRequest, ChatResponse, HistoryResponse, ToolCallLog
from .network_info import network_candidates
from .operation_mode import OperationMode, operating_as
from .phone_link import handle_incoming, is_phone_connected, register_phone, unregister_phone
from .routers.brigada import router as brigada_router
from .routers.codebase import router as codebase_router
from .routers.investigation import router as investigation_router
from .routers.brigades import router as brigades_router
from .routers.obsidian import router as obsidian_router
from .routers.scout import router as scout_router
from .routers.trading import router as trading_router

configure_logging()
logger = logging.getLogger("jarvis.main")

app = FastAPI(title="Jarvis Remote Backend", version="0.1.0")
app.include_router(codebase_router)
app.include_router(obsidian_router)
app.include_router(investigation_router)
app.include_router(brigada_router)
app.include_router(trading_router)
app.include_router(scout_router)
app.include_router(brigades_router)


@app.on_event("startup")
async def _start_malware_protection() -> None:
    """Arranca los dos servicios en background del centinela de malware (ver
    app/malware/, spec 2026-08-16) -- no bloquean el arranque del server: el
    escaneo on-access corre en su propio thread (Observer de watchdog,
    síncrono por diseño de esa librería), y el escaneo completo diario es
    una tarea asyncio que arranca, espera su delay inicial, y se repite sola
    sin intervención de este handler de nuevo."""
    behavioral_watcher.start_watching()
    asyncio.create_task(fullscan.full_scan_loop())
    # Vigilante de la playlist de YouTube: ingiere solo los videos nuevos cada cierto
    # rato (ver app/ingestion/playlist_watcher.py). Corre en background, no bloquea el
    # arranque, se repite solo. Apagable con PLAYLIST_WATCH_ENABLED=false.
    asyncio.create_task(playlist_watcher.watch_loop())
    # Consolidación de memoria ("sueño"): agrupa notas recientes y escribe síntesis en
    # background (ver app/obsidian/consolidation.py). Default APAGADO (escribe al vault
    # con el LLM); se prende con CONSOLIDATION_ENABLED=true.
    asyncio.create_task(consolidation.consolidation_loop())
    # Curiosidad (Etapa C): detecta huecos del vault y los surge (solo-avisar). Default
    # apagado (CURIOSITY_ENABLED). Tier 0, no actúa: solo avisa.
    asyncio.create_task(curiosity.curiosity_loop())
    # Watchlist de Trading en background (2026-10-13): refresca símbolos y alerta al pasar a
    # "señal activa". Default APAGADO (TRADING_WATCH_LOOP_ENABLED). SOLO análisis, nunca opera.
    from . import trading_watch
    asyncio.create_task(trading_watch.watch_loop())
    # Aprendizaje proactivo (2026-10-13): amplía casos abiertos / llena huecos del vault por
    # iniciativa propia. Default APAGADO (PROACTIVE_LEARNING_ENABLED). Gasta LLM, por eso off.
    from . import proactive
    asyncio.create_task(proactive.proactive_loop())
    # Capa de barcos (AIS): stream WebSocket de AISStream en background. Inactivo sin AISSTREAM_KEY.
    from . import geo_ships
    asyncio.create_task(geo_ships.ais_loop())
    # Cerebro proactivo (jefe de Memoria, paso 3, 2026-11-03): reindexa la memoria y
    # consolida/escribe sus conclusiones por su cuenta. Default APAGADO
    # (CEREBRO_PROACTIVE_ENABLED); corre local (pesado en CPU), por eso opt-in.
    from brigades import cerebro_proactive
    asyncio.create_task(cerebro_proactive.cerebro_loop())


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "phone_connected": is_phone_connected(),
        # Direcciones donde este backend es alcanzable ahora mismo, ordenadas
        # de conexión directa (hotspot WiFi de la PC / LAN) a Tailscale
        # (fallback). El celular usa esto para recordar la URL directa y
        # preferirla la próxima vez, sin dejar de tener Tailscale como red de
        # respaldo cuando no están en la misma red.
        "network_candidates": network_candidates(settings.port),
    }


# Timeout corto a propósito, distinto del timeout general del cliente
# (settings.llm_request_timeout_seconds, 1800s) -- un chequeo de salud tiene
# que responder rápido; si el LLM está genuinamente colgado, mejor reportar
# "no responde" en 30s que esperar hasta media hora.
_HEALTH_DEEP_TIMEOUT_SECONDS = 30.0


@app.get("/api/health/deep")
async def health_deep() -> dict:
    """A diferencia de /api/health (que solo confirma que el proceso HTTP
    responde), esto ejercita el loop del LLM de verdad -- un round-trip real
    y mínimo (sin tools, pocos tokens de salida) para confirmar que el modelo
    responde, no solo que el puerto está abierto.

    Prerequisito #3 de la Opción A (identificado en el informe de
    arquitectura 2026-08-10): un futuro watchdog que reinicia el backend
    después de un self-edit necesita poder distinguir "el proceso está up"
    de "el agente realmente funciona" -- un proceso con el loop del agente
    roto pasaría /api/health igual (no hace ninguna llamada real al modelo),
    así que ese endpoint solo no alcanza para verificar un self-restart."""
    start = time.monotonic()
    try:
        response = await client.chat.completions.create(
            model=settings.lmstudio_model,
            messages=[{"role": "user", "content": "Respondé solo con la palabra: ok"}],
            max_tokens=10,
            timeout=_HEALTH_DEEP_TIMEOUT_SECONDS,
        )
        elapsed = time.monotonic() - start
        content = (response.choices[0].message.content or "").strip()
        return {
            "status": "ok",
            "llm_reachable": True,
            "elapsed_seconds": round(elapsed, 2),
            "response_preview": content[:50],
        }
    except Exception as exc:
        elapsed = time.monotonic() - start
        return {
            "status": "error",
            "llm_reachable": False,
            "elapsed_seconds": round(elapsed, 2),
            "error": str(exc),
        }


@app.post("/api/chat", response_model=ChatResponse, dependencies=[Depends(verify_api_key)])
async def chat(req: ChatRequest) -> ChatResponse:
    # Este es el ÚNICO punto de entrada interactivo: hay un humano (Damian) del
    # otro lado, sea por la ventana de escritorio, la voz de la tray o el chat
    # del celular, todos pegan acá. Por eso declara modo SUPERVISADO (attended):
    # el sandbox de filesystem se abre al root amplio para no perder potencia
    # mientras Damian está mirando y puede frenar cualquier macana. Cualquier
    # OTRO camino de ejecución (tareas programadas, CLIs de ingesta/scan,
    # self-repair desatendido, loops de fondo) NO pasa por acá y queda AUTÓNOMO
    # por el default fail-safe del ContextVar. Ver app/operation_mode.py.
    with operating_as(OperationMode.SUPERVISED, source="http_chat"):
        conv_id, reply, tool_calls = await run_agent(req.message, req.conversation_id)
    # Espejado en vivo (2026-10-06): re-emite este turno a los demás clientes (PC/
    # celular) suscritos a la conversación. Se saltea el origin (ya lo mostró por esta
    # respuesta HTTP). Best-effort: nunca romper el chat por un problema de broadcast.
    try:
        await chat_link.broadcast(
            conv_id,
            chat_link.turn_payload(conv_id, req.message, reply, time.time(), req.client_id),
            origin=req.client_id,
        )
    except Exception:  # noqa: BLE001
        logger.exception("chat_link: fallo al re-emitir el turno (no afecta la respuesta)")
    return ChatResponse(
        conversation_id=conv_id,
        reply=reply,
        tool_calls=[ToolCallLog(**tc) for tc in tool_calls],
    )


@app.get("/api/history", response_model=HistoryResponse, dependencies=[Depends(verify_api_key)])
async def history(conversation_id: str = "default", limit: int = 200) -> HistoryResponse:
    """Historial mostrable de una conversación, para que la PC y el celular carguen el
    mismo hilo al abrir (2026-10-06). Solo mensajes user/assistant con texto."""
    msgs = get_display_history(conversation_id, limit=limit)
    import time as _t

    now = _t.time()
    return HistoryResponse(
        conversation_id=conversation_id,
        messages=[ChatMirrorMessage(role=m["role"], content=m["content"], ts=now) for m in msgs],
    )


@app.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket) -> None:
    """Espejado del chat en vivo. La UI (tray PC / app Android) abre este WebSocket,
    se autentica con el mismo Bearer token que /api/chat, y manda un primer frame JSON
    de suscripción: {"conversation_id": "default", "client_id": "tray-pc"}. A partir de
    ahí recibe cada turno nuevo de esa conversación (venga del otro dispositivo), para
    mostrarlo al instante. El propio origin no recibe su eco (ver chat_link)."""
    if not _check_bearer(websocket.headers.get("authorization")):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    conversation_id = "default"
    try:
        raw = await websocket.receive_text()
        try:
            sub = json.loads(raw)
            conversation_id = str(sub.get("conversation_id") or "default")
            client_id = sub.get("client_id")
        except (json.JSONDecodeError, AttributeError):
            client_id = None
        chat_link.register(conversation_id, websocket, client_id)
        logger.info("chat_link: cliente suscrito a '%s' (origin=%s)", conversation_id, client_id)
        while True:
            # El cliente no necesita mandar nada más; recibir mantiene viva la conexión
            # y detecta la desconexión. Los frames entrantes extra se ignoran.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        chat_link.unregister(conversation_id, websocket)
        logger.info("chat_link: cliente desuscrito de '%s'", conversation_id)


# --- Centro de Mando (2026-10-11): el panel de brigadas servido por el harness ---
_MC_HTML = Path(__file__).resolve().parent.parent.parent / "docs" / "raphael" / "centro-de-mando-raphael.html"


@app.get("/centro-de-mando", response_class=HTMLResponse)
async def centro_de_mando() -> HTMLResponse:
    """Sirve el panel del Centro de Mando. El HTML se conecta solo a /ws/mission-control
    para la data en vivo (mismo origen). Sin auth: es estado de brigadas de solo-lectura,
    pensado para uso local (si se quiere cerrar, se agrega un token -- pendiente)."""
    try:
        return HTMLResponse(_MC_HTML.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return HTMLResponse("<h1>Centro de Mando: HTML no encontrado</h1>", status_code=404)


# --- Suite Raphael (2026-11-02): UI propia por brigada, separada del chat del
# maestro. Shell con sidebar de brigadas + vista de Scout funcional; el resto de
# brigadas van "próximamente", con el mismo molde. Habla con /api/scout/*. Sin
# auth sobre el HTML (como los otros paneles): lee la key de ?key= y la manda en
# las llamadas a la API. Pensado para uso local; se baja a app de escritorio luego.
_SUITE_HTML = Path(__file__).resolve().parent.parent.parent / "docs" / "raphael" / "suite-raphael.html"


@app.get("/suite", response_class=HTMLResponse)
async def suite() -> HTMLResponse:
    try:
        return HTMLResponse(_SUITE_HTML.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return HTMLResponse("<h1>Suite: HTML no encontrado</h1>", status_code=404)


@app.get("/api/mission-control/state", dependencies=[Depends(verify_read)])
async def mission_control_state() -> dict:
    return mission_control.snapshot()


def _ws_token(websocket: WebSocket) -> str:
    """Token de un WebSocket: del header Authorization (apps nativas) o del query param
    ?key=/?token= (los navegadores NO pueden setear headers en un WebSocket)."""
    h = websocket.headers.get("authorization") or ""
    if h.startswith("Bearer "):
        return h.removeprefix("Bearer ").strip()
    return websocket.query_params.get("key") or websocket.query_params.get("token") or ""


def _ws_read_ok(websocket: WebSocket) -> bool:
    return _scope_for(_ws_token(websocket)) in ("master", "full", "read")


@app.websocket("/ws/mission-control")
async def mission_control_ws(websocket: WebSocket) -> None:
    """El panel se suscribe acá y recibe el estado inicial + cada evento de brigada en vivo.
    Auth de solo-lectura (2026-10-13): acepta la key maestra o un device token (header o
    ?key=). Sin token válido, cierra (el HTML cae a su modo simulación)."""
    if not _ws_read_ok(websocket):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    mission_control.register(websocket)
    logger.info("mission_control: panel suscrito")
    try:
        await websocket.send_text(
            json.dumps({"type": "snapshot", **mission_control.snapshot()}, ensure_ascii=False)
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        mission_control.unregister(websocket)
        logger.info("mission_control: panel desuscrito")


# --- Configuración amigable (2026-10-11): panel web /configuracion servido por el harness ---
_CFG_HTML = Path(__file__).resolve().parent.parent.parent / "docs" / "raphael" / "configuracion-raphael.html"


@app.get("/configuracion", response_class=HTMLResponse)
async def configuracion() -> HTMLResponse:
    """Sirve el panel de Configuración amigable. El HTML lee GET /api/config y guarda con
    POST /api/config usando el Bearer token que la tray-app le pasa por ?key= (mismo patrón
    que el Centro de Mando). Sin key, el panel se muestra deshabilitado para guardar."""
    try:
        return HTMLResponse(_CFG_HTML.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return HTMLResponse("<h1>Configuración: HTML no encontrado</h1>", status_code=404)


@app.get("/api/config", dependencies=[Depends(verify_api_key)])
async def get_config() -> dict:
    """Esquema de todas las opciones amigables + su valor actual (leído del .env)."""
    return user_config.schema_with_values()


@app.post("/api/config", dependencies=[Depends(verify_api_key)])
async def save_config(changes: dict) -> dict:
    """Guarda cambios al backend/.env. `user_config.apply` solo escribe keys del esquema
    (no puede tocar secretos ni gates). La mayoría toma efecto al reiniciar el backend."""
    written = user_config.apply(changes)
    return {"ok": True, "written": written, "restart_required": True}


# --- Emparejamiento por QR (2026-10-12): la PC muestra un QR; el celular lo escanea ---
_PAIR_HTML = Path(__file__).resolve().parent.parent.parent / "docs" / "raphael" / "vincular-raphael.html"


@app.get("/vincular", response_class=HTMLResponse)
async def vincular() -> HTMLResponse:
    """Página con el QR de emparejamiento. El HTML es solo la cáscara (sin secretos); el QR
    y la API key los trae de GET /api/pairing con el Bearer que la tray le pasa por ?key=."""
    try:
        return HTMLResponse(_PAIR_HTML.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return HTMLResponse("<h1>Vincular: HTML no encontrado</h1>", status_code=404)


@app.get("/api/pairing", dependencies=[Depends(verify_api_key)])
async def api_pairing() -> dict:
    """QR + URLs locales para vincular el celular. Autenticado: el QR lleva la API key."""
    return pairing.pairing_response()


# --- Trading (2026-10-12): watchlist de símbolos + estado (brigada Trading). SOLO análisis ---
@app.get("/api/trading/watch", dependencies=[Depends(verify_api_key)])
async def api_trading_watch() -> dict:
    from . import trading_watch

    return trading_watch.snapshot()


@app.post("/api/trading/watch/add", dependencies=[Depends(verify_api_key)])
async def api_trading_watch_add(body: dict) -> dict:
    from . import trading_watch

    syms = trading_watch.add_symbol(
        str(body.get("instrument", "")),
        str(body.get("source", "ccxt")),
        str(body.get("timeframe", "1h")),
    )
    return {"symbols": syms}


@app.post("/api/trading/watch/remove", dependencies=[Depends(verify_api_key)])
async def api_trading_watch_remove(body: dict) -> dict:
    from . import trading_watch

    return {"symbols": trading_watch.remove_symbol(str(body.get("instrument", "")))}


@app.post("/api/trading/watch/refresh", dependencies=[Depends(verify_api_key)])
async def api_trading_watch_refresh(body: dict | None = None) -> dict:
    from . import trading_watch

    inst = str((body or {}).get("instrument") or "") or None
    return await trading_watch.refresh(inst)


@app.post("/api/trading/watch/backtest", dependencies=[Depends(verify_api_key)])
async def api_trading_watch_backtest(body: dict) -> dict:
    from . import trading_watch

    return await trading_watch.backtest(str(body.get("instrument", "")))


# --- Investigación (2026-10-12): casos de research retenidos (brigada Investigación) ---
@app.get("/api/investigation", dependencies=[Depends(verify_api_key)])
async def api_investigation() -> dict:
    from . import research_cases

    return {"cases": research_cases.list_cases()}


@app.post("/api/investigation/status", dependencies=[Depends(verify_api_key)])
async def api_investigation_status(body: dict) -> dict:
    from . import research_cases

    cases = research_cases.set_status(str(body.get("id", "")), str(body.get("status", "")))
    return {"cases": cases}


# --- Ingesta (2026-10-12): fuentes auto-ingeridas + últimos ítems ingeridos (brigada Ingesta) ---
@app.get("/api/ingest", dependencies=[Depends(verify_api_key)])
async def api_ingest() -> dict:
    from .ingestion import sources

    return sources.snapshot()


@app.post("/api/ingest/add", dependencies=[Depends(verify_api_key)])
async def api_ingest_add(body: dict) -> dict:
    from .ingestion import sources

    return {"sources": sources.add_source(str(body.get("url", "")))}


@app.post("/api/ingest/remove", dependencies=[Depends(verify_api_key)])
async def api_ingest_remove(body: dict) -> dict:
    from .ingestion import sources

    return {"sources": sources.remove_source(str(body.get("url", "")))}


# --- Mapa de inteligencia geoespacial (2026-10-13): el globo de Raphael con su OSINT ---
_GLOBO_HTML = Path(__file__).resolve().parent.parent.parent / "docs" / "raphael" / "globo-raphael.html"


@app.get("/globo", response_class=HTMLResponse)
async def globo() -> HTMLResponse:
    """Globo 3D con la inteligencia geoespacial de Raphael (puntos de ip_geolocate, etc.).
    El HTML lee GET /api/geo/points y se suscribe a /ws/geo con la key de ?key=."""
    try:
        return HTMLResponse(_GLOBO_HTML.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return HTMLResponse("<h1>Globo: HTML no encontrado</h1>", status_code=404)


# --- Grafo de Obsidian para la brigada Memoria (2026-10-18): el grafo del vault,
# servido como HTML para embeberlo en el detalle de Memoria del Centro de Mando.
# Lee GET /api/obsidian/graph (sin auth, solo-lectura local). ---
_GRAFO_HTML = Path(__file__).resolve().parent.parent.parent / "docs" / "raphael" / "grafo-memoria.html"


@app.get("/grafo-memoria", response_class=HTMLResponse)
async def grafo_memoria() -> HTMLResponse:
    """Grafo 3D del vault de Obsidian (memoria de Raphael). Lee /api/obsidian/graph."""
    try:
        return HTMLResponse(_GRAFO_HTML.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return HTMLResponse("<h1>Grafo: HTML no encontrado</h1>", status_code=404)


@app.get("/api/geo/points", dependencies=[Depends(verify_read)])
async def geo_points() -> dict:
    from . import geo_intel

    return geo_intel.snapshot()


@app.get("/api/geo/flights", dependencies=[Depends(verify_read)])
async def geo_flights() -> dict:
    """Capa de vuelos en vivo (ADS-B público vía OpenSky, server-side). Best-effort."""
    from . import geo_intel

    return {"flights": await asyncio.to_thread(geo_intel.fetch_flights)}


@app.get("/api/geo/layer/{name}", dependencies=[Depends(verify_read)])
async def geo_layer(name: str) -> dict:
    """Capas públicas del mundo (terremotos, noticias, ISS, satélites, infraestructura).
    Todas 🟢 gratis/sin key, server-side y cacheadas (app/geo_layers.py)."""
    from . import geo_layers

    return await asyncio.to_thread(geo_layers.get, name)


@app.websocket("/ws/geo")
async def geo_ws(websocket: WebSocket) -> None:
    """El globo se suscribe acá y recibe el snapshot inicial + cada punto nuevo en vivo."""
    if not _ws_read_ok(websocket):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    from . import geo_intel

    geo_intel.register(websocket)
    try:
        await websocket.send_text(
            json.dumps({"type": "snapshot", **geo_intel.snapshot()}, ensure_ascii=False)
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        geo_intel.unregister(websocket)


# --- Self-model (2026-10-13, capa 1 de autoconciencia): el modelo de sí mismo, consultable ---
@app.get("/api/self", dependencies=[Depends(verify_read)])
async def api_self() -> dict:
    from . import self_model

    return self_model.build()


# --- Modelo activo (2026-10-18, ítem 6): el modelo REAL que está usando el chat
# ahora mismo (resuelto por testmode/routing), para que los paneles no muestren un
# nombre fijo. `model` = efectivo; `configured` = LMSTUDIO_MODEL del .env. ---
@app.get("/api/model", dependencies=[Depends(verify_read)])
async def api_model() -> dict:
    from . import testmode

    try:
        effective = testmode.chat_model()
    except Exception:  # noqa: BLE001
        effective = settings.lmstudio_model
    return {
        "model": effective,
        "configured": settings.lmstudio_model,
        "test_mode": testmode.is_on(),
    }


# --- Dispositivos (2026-10-13): listar/revocar tokens por dispositivo (emparejamiento por QR) ---
@app.get("/api/devices", dependencies=[Depends(verify_api_key)])
async def api_devices() -> dict:
    from . import device_tokens

    return {"devices": device_tokens.list_devices()}


@app.post("/api/devices/revoke", dependencies=[Depends(verify_api_key)])
async def api_devices_revoke(body: dict) -> dict:
    from . import device_tokens

    ok = device_tokens.revoke(str(body.get("token_id", "")))
    return {"ok": ok, "devices": device_tokens.list_devices()}


def _check_bearer(authorization: str | None) -> bool:
    if not authorization or not authorization.startswith("Bearer "):
        return False
    return authorization.removeprefix("Bearer ").strip() == settings.api_key


@app.websocket("/ws/phone")
async def phone_ws(websocket: WebSocket) -> None:
    """Conexión saliente del celular. Se autentica con el mismo Bearer token que
    `/api/chat`, mandado como header `Authorization` en el handshake del WebSocket.

    Mientras esté conectado, las tools con `target="phone"` (ver `tools/phone.py`)
    se despachan acá adentro y esperan la respuesta correlacionada por id
    (ver `phone_link.dispatch_to_phone` / `handle_incoming`).
    """
    if not _check_bearer(websocket.headers.get("authorization")):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    await register_phone(websocket)
    logger.info("phone_link: celular conectado")
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("phone_link: mensaje no-JSON ignorado")
                continue
            await handle_incoming(message)
    except WebSocketDisconnect:
        pass
    finally:
        await unregister_phone(websocket)
        logger.info("phone_link: celular desconectado")
