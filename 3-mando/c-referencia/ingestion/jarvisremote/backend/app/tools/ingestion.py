"""Tool del agente para la ingesta de playlists de YouTube al vault
(ver `app/ingestion/youtube_playlist.py`).

Reusa la lógica del módulo de ingesta -- no la duplica -- para que Jarvis
pueda disparar el pipeline por voz/chat, además de la CLI
(`python -m app.ingestion.youtube_playlist <URL>`).
"""

from __future__ import annotations

from ..ingestion import youtube_playlist
from . import register_tool


@register_tool(
    name="youtube_ingest_playlist",
    description=(
        "Ingesta automática de una playlist de YouTube al vault de conocimiento (Obsidian). Enumera "
        "los videos de la playlist con yt-dlp, detecta cuáles todavía NO tienen nota (por video ID, "
        "así no duplica si se corre de nuevo), baja la transcripción de cada video nuevo (prefiere "
        "español, cae a inglés), genera un resumen con tu propio LLM y guarda una nota firmada como "
        "'jarvis' con el formato de las notas de video existentes (## Fuente / ## Resumen / ## Temas "
        "clave / ## Notas relacionadas), actualizando el índice de la playlist. Reemplaza el flujo "
        "manual de pasar cada video por NotebookLM. Si no se pasa URL, usa la playlist personal "
        "'Info para Jarvis' de Damian. Un video sin transcripción se salta sin romper la corrida."
    ),
    parameters={
        "type": "object",
        "properties": {
            "playlist_url": {
                "type": "string",
                "description": "URL de la playlist de YouTube. Opcional: por default la playlist 'Info para Jarvis'.",
            },
            "max_videos": {
                "type": "integer",
                "description": "Tope opcional de videos NUEVOS a procesar en esta corrida (para no procesar toda la playlist de una).",
            },
        },
        "required": [],
    },
)
async def youtube_ingest_playlist(playlist_url: str | None = None, max_videos: int | None = None) -> dict:
    result = await youtube_playlist.ingest_playlist(
        playlist_url or youtube_playlist.DEFAULT_PLAYLIST_URL, max_videos=max_videos
    )
    return result.to_dict()


@register_tool(
    name="youtube_ingest_video",
    description=(
        "Ingesta UN video de YouTube suelto (no una playlist) al vault de conocimiento. Usá ESTA, no "
        "youtube_ingest_playlist, cuando Damian pasa el link de un video individual (watch?v=..., "
        "youtu.be/... o el ID de 11 caracteres). Baja la transcripción (prefiere español, cae a "
        "inglés/portugués), genera resumen + discernimiento de relevancia con tu LLM y guarda la nota "
        "firmada como 'jarvis' con el mismo formato de las notas de video (## Fuente / ## Resumen / "
        "## Temas clave / ## Notas relacionadas), actualizando el índice. Idempotente: si el video ya "
        "tiene nota, no la duplica (pasá force=true para rehacerla). Un video sin transcripción se "
        "reporta sin romper. NO es web_get: esto SÍ guarda la nota en el vault, no te devuelve el texto."
    ),
    parameters={
        "type": "object",
        "properties": {
            "video_url": {
                "type": "string",
                "description": "URL del video (watch?v=..., youtu.be/...) o el video ID de 11 caracteres.",
            },
            "force": {
                "type": "boolean",
                "description": "Si es true, re-ingiere aunque el video ya tenga nota. Default false.",
            },
        },
        "required": ["video_url"],
    },
)
async def youtube_ingest_video(video_url: str, force: bool = False) -> dict:
    result = await youtube_playlist.ingest_video(video_url, force=force)
    return result.to_dict()
