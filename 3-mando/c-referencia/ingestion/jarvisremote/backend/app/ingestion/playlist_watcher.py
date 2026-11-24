"""Vigilante en background de la playlist de YouTube (2026-10-05).

Tarea de vida larga que cada `PLAYLIST_WATCH_INTERVAL_MINUTES` revisa la playlist
"Info para Jarvis" e ingiere los videos NUEVOS automáticamente, sin que Damian
tenga que pedirlo. Así "cada vez que guardo un video en la playlist, se ingiere
solo" (dentro del intervalo de chequeo).

Por qué polling y no push: YouTube no notifica a una app local cuando agregás un
video a una playlist, y el backend no está expuesto a internet (solo Tailscale/LAN),
así que no hay callback público para un webhook. Revisar cada tanto es la vía real.

Barato cuando no hay novedad: reusa `ingest_playlist`, que es idempotente (dedup
por video ID). Si no hay videos nuevos, `select_new_videos` devuelve vacío y NO se
llama al LLM -- el chequeo es solo una enumeración con yt-dlp. El costo (LLM) solo
aparece cuando de verdad hay un video nuevo que resumir.

Corre en background (arrancado desde el startup de FastAPI con `asyncio.create_task`,
igual que el escaneo de malware), NO por el endpoint HTTP del chat -> no sufre el
timeout de 1800s de la tray-app: puede tardar lo que haga falta.

Mismo patrón que `app/malware/fullscan.py::full_scan_loop`.
"""

from __future__ import annotations

import asyncio
import logging

from ..config import settings
from . import youtube_playlist

logger = logging.getLogger("jarvis.ingestion.playlist_watcher")

# Delay inicial: deja que el backend termine de arrancar antes del primer chequeo.
_STARTUP_DELAY_SECONDS = 90.0


async def run_once() -> dict:
    """Una pasada: ingiere los videos nuevos de la playlist histórica + de todas las fuentes
    que el usuario agregó a la watchlist (sources.add_source). Registra cada ítem nuevo con su
    link (sources.log_ingested) y lo reporta a la brigada Ingesta del panel. Devuelve el resumen
    agregado. Aislada para poder testearla."""
    from . import sources

    urls: list[str] = []
    legacy = settings.playlist_watch_url or youtube_playlist.DEFAULT_PLAYLIST_URL
    if legacy:
        urls.append(legacy)
    for u in sources.list_sources():
        if u not in urls:
            urls.append(u)

    max_per_run = settings.playlist_watch_max_per_run or None  # 0 -> sin tope
    total_created = 0
    total_new_attempted = 0  # videos nuevos que se intentaron (creados + fallidos)
    total_failed = 0  # nuevos que NO se pudieron ingerir (sin transcripción + error técnico)
    check_errors = 0  # fuentes cuyo chequeo mismo reventó (yt-dlp/red/LLM caído)
    runs: list[dict] = []
    for url in urls:
        try:
            result = await youtube_playlist.ingest_playlist(url, max_videos=max_per_run)
        except Exception:  # noqa: BLE001 -- una fuente rota no frena al resto
            logger.exception("ingesta falló para %s", url)
            check_errors += 1
            continue
        d = result.to_dict()
        for item in d.get("created", []):
            vid = item.get("video_id", "")
            link = f"https://www.youtube.com/watch?v={vid}" if vid else url
            title = item.get("title") or vid or url
            sources.log_ingested(title, link, "youtube")
            try:
                from .. import mission_control
                await mission_control.report("ing", f"📥 {title}", inc=1)
            except Exception:  # noqa: BLE001
                pass
        created = d.get("created_count", 0)
        # "Falló" = video nuevo que se intentó pero NO quedó como nota: sin subtítulos
        # usables o error técnico de transcripción. (El salto por --min-relevance es a
        # pedido explícito de Damian, no un fallo, así que cuenta como "intentado" pero
        # no como "falló".)
        failed = d.get("skipped_no_transcript_count", 0) + d.get("transcript_errors_count", 0)
        total_created += created
        total_failed += failed
        total_new_attempted += created + failed + d.get("skipped_low_relevance_count", 0)
        runs.append(d)
    return {
        "created_count": total_created,
        "new_attempted": total_new_attempted,
        "failed_count": total_failed,
        "check_errors": check_errors,
        "runs": runs,
    }


async def watch_loop() -> None:
    """Corutina de vida larga -- arrancarla UNA vez desde el startup de FastAPI
    (`app/main.py`) con `asyncio.create_task`. Hace la primera revisión poco
    después del arranque y después se repite cada `PLAYLIST_WATCH_INTERVAL_MINUTES`.
    Un fallo de una pasada se loguea y NO corta el loop."""
    if not settings.playlist_watch_enabled:
        logger.info("vigilante de playlist deshabilitado (PLAYLIST_WATCH_ENABLED=false)")
        return

    await asyncio.sleep(_STARTUP_DELAY_SECONDS)
    while True:
        try:
            summary = await run_once()
            created = summary.get("created_count", 0)
            failed = summary.get("failed_count", 0)
            check_errors = summary.get("check_errors", 0)
            if created:
                logger.info("vigilante de playlist: %s video(s) nuevo(s) ingerido(s)", created)
            # Reporte HONESTO al Centro de Mando (fix 2026-10-31, bug que notó Damian):
            # NO decir "sin novedades" si en realidad SÍ había videos nuevos que no se
            # pudieron ingerir (sin transcripción / error técnico / LLM caído) o si el
            # chequeo mismo falló. Antes se reportaba "sin novedades" siempre que
            # created==0, escondiendo fallos reales. Los creados ya los reportó run_once
            # uno por uno; acá reportamos lo que quedó sin ingerir, con su motivo.
            try:
                from .. import mission_control

                if failed or check_errors:
                    detalle: list[str] = []
                    if failed:
                        detalle.append(f"{failed} video(s) nuevo(s) sin ingerir (sin transcripción o error)")
                    if check_errors:
                        detalle.append(f"{check_errors} fuente(s) con error de chequeo")
                    msg = "⚠ playlist: " + "; ".join(detalle)
                    logger.warning("vigilante de playlist: %s", "; ".join(detalle))
                    await mission_control.report("ing", msg, inc=0)
                elif not created:
                    logger.info("vigilante de playlist: sin videos nuevos")
                    await mission_control.report("ing", "playlist revisada · sin novedades", inc=0)
            except Exception:  # noqa: BLE001
                pass
        except Exception:
            logger.exception("el chequeo de la playlist falló")
        await asyncio.sleep(max(60.0, settings.playlist_watch_interval_minutes * 60))
