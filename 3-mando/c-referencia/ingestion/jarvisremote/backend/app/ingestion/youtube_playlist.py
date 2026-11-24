"""Pipeline automático de ingesta de videos de YouTube al vault de Obsidian
(ver `app/obsidian/vault.py`), pensado para reemplazar el flujo MANUAL con el
que Damian venía procesando su playlist "Info para Jarvis": pasar cada video
por NotebookLM a mano y copiar el resumen a una nota.

Flujo (todo con piezas reales del repo, nada simulado en producción):

  1. Enumera los videos de una playlist con `yt-dlp --flat-playlist` (solo
     id + título + canal, sin bajar los videos).
  2. Detecta los NUEVOS: los que están en la playlist pero todavía no tienen
     una nota en el vault. La detección es por VIDEO ID (los 11 chars de
     `watch?v=<ID>`), parseado del cuerpo de las notas ya existentes -- NO por
     título (los títulos de las notas están curados y no coinciden con el del
     video), así el pipeline es idempotente: correrlo dos veces no duplica.
  3. Para cada nuevo, obtiene la transcripción (prefiere español, cae a
     inglés) y con ella genera el resumen llamando al MISMO LLM de chat que ya
     usa Jarvis (`app/llm_client.py` + `settings.lmstudio_model`), sin
     duplicar cliente.
  4. Escribe la nota replicando EXACTO el formato de las notas existentes
     (frontmatter author=jarvis, tags [info-para-jarvis, video, <categoría>],
     secciones ## Fuente / ## Resumen / ## Temas clave / ## Notas relacionadas
     con wikilinks), con "Generado con: resumen automático" en ## Fuente en
     lugar del NotebookLM de las notas viejas. Actualiza el índice
     `Playlist: Información para Jarvis (YouTube)` agregando el wikilink y
     recalculando el conteo de videos.

Un video sin transcripción disponible se salta con gracia (se reporta, no se
crea una nota vacía ni se rompe la corrida entera).

┌─────────────────────────────────────────────────────────────────────────┐
│ ⚠️  NO PROBADO CONTRA YOUTUBE REAL. El entorno donde se escribió este     │
│ módulo tiene YouTube bloqueado por red, así que el pipeline NUNCA corrió  │
│ end-to-end contra la API/subtítulos reales de YouTube -- solo contra      │
│ mocks (ver backend/tests/test_youtube_ingestion.py). La lógica de vault,  │
│ detección de nuevos, formato de nota, idempotencia e índice sí está       │
│ testeada. Damian tiene que correrlo UNA vez en su PC (con red a YouTube y │
│ el LLM levantado) para validar que `yt-dlp` y `youtube-transcript-api`    │
│ devuelven lo que este código espera antes de confiar en él.               │
└─────────────────────────────────────────────────────────────────────────┘

Uso:

  CLI:   python -m app.ingestion.youtube_playlist <URL_de_la_playlist>
  Tool:  registrada como `youtube_ingest_playlist` (ver app/tools/ingestion.py),
         así Jarvis la puede disparar por voz/chat.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field

from ..config import settings
from ..llm_client import client
from ..obsidian import vault

logger = logging.getLogger("jarvis.ingestion.youtube")


def _cookie_opts() -> dict:
    """Cookies para yt-dlp, para pasar el 'Sign in to confirm you're not a bot' de
    YouTube (bloqueo 2026-11). Dos vías, en orden de prioridad:

    1. `YT_COOKIES_FILE`=ruta a un cookies.txt (formato Netscape). Es la vía ROBUSTA en
       Windows: Chrome/Brave/Edge cifran sus cookies con app-bound encryption y yt-dlp
       NO las puede leer del navegador (falla 'Failed to decrypt with DPAPI', issue
       #10927). Exportá el cookies.txt con una extensión tipo 'Get cookies.txt LOCALLY'
       y poné su ruta acá.
    2. `YT_COOKIES_BROWSER`=chrome|edge|firefox|brave (leer del navegador). Solo
       funciona bien con Firefox en Windows; con los Chromium suele fallar por DPAPI.

    Vacío = sin cookies (comportamiento de antes)."""
    f = os.getenv("YT_COOKIES_FILE", "").strip()
    if f:
        return {"cookiefile": f}
    b = os.getenv("YT_COOKIES_BROWSER", "").strip().lower()
    return {"cookiesfrombrowser": (b,)} if b else {}

# Título e id de la nota índice de la playlist (ya existe en el vault, creada
# a mano cuando el flujo era manual). Se actualiza in-place con note_id para
# no romper su slug/frontmatter.
INDEX_NOTE_ID = "jarvis/playlist-informacion-para-jarvis-youtube"
INDEX_NOTE_TITLE = "Playlist: Información para Jarvis (YouTube)"

# URL default de la playlist personal de Damian ("Info para Jarvis"), la que
# alimentaba el flujo manual -- así la CLI/tool se pueden llamar sin argumento.
DEFAULT_PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLVjx_ae3DGSo"

# Un video ID de YouTube son exactamente 11 chars del alfabeto base64-url.
_VIDEO_ID_RE = re.compile(r"(?:v=|/watch\?v=|youtu\.be/)([0-9A-Za-z_-]{11})")

# Idiomas de subtítulos a aceptar, en orden de preferencia. Se comparan por
# PREFIJO contra los códigos que YouTube expone, así "es" matchea es/es-419/
# es-ES, "en" matchea en/en-US y "pt" matchea pt/pt-BR. El portugués entra
# porque parte de la playlist es de canales BR; DeepSeek resume igual de bien
# desde PT (reemplaza al viejo fallback de traducción de youtube-transcript-api).
_SUBTITLE_LANG_PREFS = ("es", "en", "pt")

# Reintentos ante rate-limit (HTTP 429) de YouTube. El 429 es TRANSITORIO (te
# limita el ritmo, no te bloquea), así que vale reintentar con espera creciente
# (3s, 6s, 12s) antes de rendirse -- probado 2026-09-01: yt-dlp bajaba unos
# videos y otros daban 429 por el ritmo. Un fallo que NO es 429 (bloqueo real,
# red caída) se propaga en el primer intento, sin reintentar de gusto.
_TRANSCRIPT_MAX_RETRIES = 4
_TRANSCRIPT_BACKOFF_BASE = 3.0
# Respiro entre videos para no gatillar el 429 de entrada (segundos).
_DELAY_BETWEEN_VIDEOS = 1.5


def _is_rate_limited(exc: Exception) -> bool:
    """True si la excepción parece un rate-limit HTTP 429 de YouTube. yt-dlp a
    veces envuelve el HTTPError en su propio DownloadError, así que se mira el
    texto del mensaje (robusto ante el tipo concreto)."""
    msg = str(exc).lower()
    return "429" in msg or "too many requests" in msg

# Tope de caracteres de transcripción que se le manda al LLM. Una
# transcripción larga (video de 30 min) puede superar el presupuesto de
# contexto del modelo (ver settings.model_context_tokens) -- se recorta para
# no disparar el context-shift de Ollama (mismo problema documentado en
# app/agent.py). El resumen igual capta la idea con el arranque del video.
_MAX_TRANSCRIPT_CHARS = 12000

# Temas de interés del proyecto Jarvis contra los que se juzga la UTILIDAD de
# cada video (agregado 2026-08-18, decisión de Damian). Configurable: se puede
# pasar otra lista a `ingest_playlist(..., relevance_topics=[...])`. Estos son
# los defaults.
#
# ⚠️ FILOSOFÍA (no debilitar sin pedírselo a Damian): la relevancia es una
# SEÑAL/ETIQUETA, NUNCA un filtro que descarta. Aunque un video puntúe bajo hoy,
# es info que Damian curó a mano y que "tal vez un día le sirva" -- así que TODO
# se guarda. La única forma de que la relevancia saltee un video es que Damian
# lo pida explícito con --min-relevance N (default: no filtra nada).
DEFAULT_RELEVANCE_TOPICS = [
    "ciberseguridad ofensiva y defensiva",
    "hacking",
    "IA y agentes",
    "métodos de aprendizaje",
    "robótica y exoesqueletos",
    "desarrollo del propio asistente Jarvis",
]

# Veredictos canónicos que puede devolver el discernimiento de relevancia, en
# orden de mayor a menor utilidad. El LLM puede escribir variantes (con/sin
# tilde, "util", etc.); `_parse_relevance` las normaliza a uno de estos.
_RELEVANCE_VERDICTS = ["útil", "dudoso", "no útil"]

# Umbral por debajo del cual (o con veredicto "no útil") una nota se marca como
# baja relevancia: tag `baja-relevancia` + advertencia visible en la nota. NO
# borra ni saltea -- solo etiqueta.
_LOW_RELEVANCE_SCORE = 2


@dataclass
class VideoEntry:
    """Un video tal como lo devuelve `yt-dlp --flat-playlist`."""

    video_id: str
    title: str
    channel: str = ""
    duration: str = ""


@dataclass
class IngestResult:
    """Resultado de una corrida del pipeline (serializable a dict para la
    tool del agente)."""

    playlist_url: str
    total_in_playlist: int = 0
    already_present: list[str] = field(default_factory=list)  # video_ids ya en el vault
    created: list[dict] = field(default_factory=list)  # {video_id, note_id, title, relevancia, relevancia_score}
    skipped_no_transcript: list[dict] = field(default_factory=list)  # {video_id, title}
    # ERRORES TÉCNICOS al obtener la transcripción (IpBlocked, VideoUnavailable,
    # cambio de API, timeout, etc.). NO es lo mismo que "sin subtítulos": acá va
    # lo que falló por un problema técnico, con su motivo real, para que NO se
    # oculte como si el video no tuviera transcripción. {video_id, title, error}
    transcript_errors: list[dict] = field(default_factory=list)
    # Saltados SOLO por --min-relevance explícito de Damian (no por juicio de
    # relevancia por default -- por default nada se saltea). {video_id, title,
    # relevancia, relevancia_score}
    skipped_low_relevance: list[dict] = field(default_factory=list)

    def relevance_breakdown(self) -> dict:
        """Conteo de notas creadas por veredicto de relevancia, para el resumen
        final (ej. útil: 6, dudoso: 2, no útil: 1)."""
        counts = {v: 0 for v in _RELEVANCE_VERDICTS}
        for c in self.created:
            verdict = c.get("relevancia")
            if verdict in counts:
                counts[verdict] += 1
        return counts

    def to_dict(self) -> dict:
        return {
            "playlist_url": self.playlist_url,
            "total_in_playlist": self.total_in_playlist,
            "created_count": len(self.created),
            "already_present_count": len(self.already_present),
            "skipped_no_transcript_count": len(self.skipped_no_transcript),
            "transcript_errors_count": len(self.transcript_errors),
            "skipped_low_relevance_count": len(self.skipped_low_relevance),
            "relevance_breakdown": self.relevance_breakdown(),
            "created": self.created,
            "already_present": self.already_present,
            "skipped_no_transcript": self.skipped_no_transcript,
            "transcript_errors": self.transcript_errors,
            "skipped_low_relevance": self.skipped_low_relevance,
        }


# ---------------------------------------------------------------------------
# Adaptadores hacia librerías externas (yt-dlp / youtube-transcript-api / LLM).
# Se aíslan en funciones finas a propósito: son los ÚNICOS puntos que tocan la
# red real de YouTube o el LLM, así los tests los mockean sin tener que
# simular toda la mecánica interna del pipeline.
# ---------------------------------------------------------------------------


def fetch_playlist_entries(playlist_url: str) -> list[VideoEntry]:
    """Enumera los videos de la playlist con `yt-dlp` en modo flat (sin bajar
    los videos, solo metadata). Import perezoso de yt_dlp para que el módulo
    se pueda importar (y testear) sin la dependencia instalada."""
    import yt_dlp  # import perezoso -- ver docstring

    ydl_opts = {
        "quiet": True,
        "extract_flat": True,  # equivalente a --flat-playlist: no resuelve cada video
        "skip_download": True,
        **_cookie_opts(),
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)

    entries = info.get("entries") or []
    result: list[VideoEntry] = []
    for entry in entries:
        if not entry:
            continue
        video_id = entry.get("id") or ""
        if not video_id:
            continue
        result.append(
            VideoEntry(
                video_id=video_id,
                title=(entry.get("title") or "").strip() or video_id,
                channel=(entry.get("channel") or entry.get("uploader") or "").strip(),
                duration=_format_duration(entry.get("duration")),
            )
        )
    return result


def fetch_transcript(video_id: str) -> str | None:
    """Baja la transcripción del video usando **yt-dlp** (no youtube-transcript-api).
    Devuelve el texto plano concatenado, o None si el video REALMENTE no tiene
    subtítulos utilizables en los idiomas aceptados (ver `_SUBTITLE_LANG_PREFS`).
    Import perezoso, mismo motivo que `fetch_playlist_entries`.

    ⚠️ POR QUÉ yt-dlp Y NO youtube-transcript-api (cambio 2026-09-01, bug real):
    YouTube empezó a bloquear a la librería `youtube-transcript-api` a nivel IP
    (excepción `IpBlocked`), incluso desde IPs residenciales y móviles -- probado
    el 2026-08-31/09-01, fallaba en TODOS los videos desde la conexión de casa y
    desde el hotspot 4G. yt-dlp imita mejor a un navegador (el mismo cliente con
    el que ya enumeramos la playlist sin problema) y esquiva ese bloqueo. Reusa
    la dependencia yt-dlp que el módulo YA tenía.

    Estrategia: 1) `extract_info` lista las pistas de subtítulos (manuales en
    `subtitles`, auto-generadas en `automatic_captions`); 2) se elige la mejor por
    preferencia de idioma (manuales antes que auto; es -> en -> pt); 3) se baja ese
    .vtt con el propio cliente de yt-dlp y se parsea a texto plano.

    Manejo de errores (mismo principio que antes, pedido explícito de Damian): un
    video sin subtítulos en los idiomas aceptados devuelve None y se saltea con
    gracia dejando el motivo en el log. Cualquier ERROR TÉCNICO (IpBlocked / red /
    extracción fallida) se deja PROPAGAR -- `extract_info`/`urlopen` levantan
    `DownloadError` u otra excepción -- para que `ingest_playlist` lo reporte con
    su tipo y mensaje, en vez de disfrazarlo de "sin transcripción"."""
    import yt_dlp  # import perezoso -- ver docstring

    url = f"https://www.youtube.com/watch?v={video_id}"
    # retries/extractor_retries: reintentos internos de yt-dlp ante fallos de red.
    # El reintento con backoff de acá abajo es la capa ESPECÍFICA para el 429.
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "retries": 5,
        "extractor_retries": 3,
        **_cookie_opts(),
    }

    for attempt in range(_TRANSCRIPT_MAX_RETRIES):
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # extract_info le pega a la red: si YouTube bloquea/limita, acá
                # levanta la excepción (429 se reintenta abajo; el resto propaga).
                info = ydl.extract_info(url, download=False)
                track = _select_subtitle_track(info)
                if track is None:
                    # DIAG (2026-11-03): loguear QUÉ ofreció YouTube para entender por qué
                    # no se eligió pista (sin subs reales / formato no-vtt / solo otros idiomas).
                    _subs = info.get("subtitles") or {}
                    _auto = info.get("automatic_captions") or {}
                    _es_fmts = [f.get("ext") for f in (_auto.get("es") or _subs.get("es") or [])]
                    logger.warning(
                        "transcript %s: sin pista aceptable. subtitles=%s automatic_captions=%s es_formatos=%s",
                        video_id, list(_subs.keys())[:15], list(_auto.keys())[:15], _es_fmts,
                    )
                    return None
                lang, sub_url = track
                # La bajada del .vtt también le pega a la red.
                raw_vtt = ydl.urlopen(sub_url).read().decode("utf-8", "replace")
        except Exception as exc:
            # Solo el 429 (rate-limit transitorio) se reintenta con espera
            # creciente. Cualquier OTRO error técnico se PROPAGA en el acto para
            # que `ingest_playlist` lo reporte con su motivo (ver docstring).
            if _is_rate_limited(exc) and attempt < _TRANSCRIPT_MAX_RETRIES - 1:
                wait = _TRANSCRIPT_BACKOFF_BASE * (2 ** attempt)  # 3s, 6s, 12s
                print(
                    f"[youtube_ingest] {video_id}: rate-limit 429, "
                    f"reintento {attempt + 1}/{_TRANSCRIPT_MAX_RETRIES - 1} en {wait:.0f}s"
                )
                time.sleep(wait)
                continue
            # DIAG (2026-11-03): dejar el error técnico real en el log antes de propagar.
            logger.warning("transcript %s: error técnico: %s: %s", video_id, type(exc).__name__, str(exc)[:300])
            raise

        text = _parse_vtt(raw_vtt)
        if text:
            print(f"[youtube_ingest] {video_id}: transcripción obtenida (yt-dlp, '{lang}')")
        return text or None

    # Inalcanzable en la práctica: el loop retorna o propaga. Guardia por las dudas.
    return None


def _select_subtitle_track(info: dict) -> tuple[str, str] | None:
    """Elige la mejor pista de subtítulos del dict de `yt_dlp.extract_info`.
    Prefiere subtítulos MANUALES sobre auto-generados y, dentro de cada grupo, el
    orden de idioma de `_SUBTITLE_LANG_PREFS` (comparado por prefijo). Devuelve
    `(codigo_idioma, url_del_vtt)` o None si no hay nada aceptable. Solo acepta el
    formato `vtt` (el único que `_parse_vtt` sabe leer)."""
    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}
    for source in (manual, auto):  # los manuales tienen prioridad sobre los auto
        for prefix in _SUBTITLE_LANG_PREFS:
            for lang, formats in source.items():
                if not lang.lower().startswith(prefix):
                    continue
                vtt_url = _pick_vtt_url(formats)
                if vtt_url:
                    return lang, vtt_url
    return None


def _pick_vtt_url(formats: list | None) -> str | None:
    """De la lista de formatos de una pista, devuelve la URL del formato `vtt`
    (el único que `_parse_vtt` entiende), o None si esa pista no ofrece vtt."""
    for fmt in formats or []:
        if fmt.get("ext") == "vtt" and fmt.get("url"):
            return fmt["url"]
    return None


# Líneas de cabecera/metadata WEBVTT que no son diálogo. Nota: el `\b` no sirve
# después de `:` (el colon no es char de palabra), por eso las claves con dos
# puntos (Kind:/Language:, las que agrega YouTube) se matchean aparte.
_VTT_META_RE = re.compile(r"^(?:WEBVTT|NOTE|STYLE|REGION)\b|^(?:Kind|Language):")
# Tags inline de las auto-captions, p.ej. <00:00:01.359><c> palabra</c>.
_VTT_TAG_RE = re.compile(r"<[^>]+>")


def _parse_vtt(raw: str) -> str:
    """Convierte un subtítulo WEBVTT en texto plano. Descarta la cabecera, los
    índices de cue, las líneas de timestamp (`00:00:01.000 --> ...`) y los tags
    inline; colapsa duplicados consecutivos (las auto-captions repiten la línea
    anterior en cada cue mientras el texto "rueda")."""
    lines: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or "-->" in line or line.isdigit():
            continue
        if _VTT_META_RE.match(line):
            continue
        line = _VTT_TAG_RE.sub("", line).strip()
        if not line:
            continue
        if not lines or lines[-1] != line:  # dedup de líneas repetidas seguidas
            lines.append(line)
    return " ".join(lines).strip()


async def _call_llm(messages: list[dict]) -> str:
    """Único punto que le pega al LLM de chat de Jarvis -- reusa el cliente
    async y el modelo ya configurados (`app/llm_client.py` +
    settings.lmstudio_model), no crea un cliente nuevo. Aislado en su propia
    función para que los tests lo mockeen sin simular la API de OpenAI."""
    response = await client.chat.completions.create(
        model=settings.lmstudio_model,
        messages=messages,
        temperature=0.3,
        max_tokens=settings.reserved_response_tokens,
    )
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Lógica del pipeline (100% testeable sin red).
# ---------------------------------------------------------------------------


def _format_duration(seconds) -> str:
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return ""
    if total <= 0:
        return ""
    minutes, sec = divmod(total, 60)
    return f"{minutes}:{sec:02d}"


def existing_video_ids() -> set[str]:
    """IDs de video que YA tienen nota en el vault, parseados del cuerpo de
    las notas del autor 'jarvis' (la línea `- Video: https://...watch?v=<ID>`).
    Es lo que hace idempotente al pipeline: se detecta por ID, no por título."""
    ids: set[str] = set()
    for note in vault.list_notes(author="jarvis"):
        for match in _VIDEO_ID_RE.finditer(note.content):
            ids.add(match.group(1))
    return ids


def select_new_videos(entries: list[VideoEntry], already: set[str]) -> list[VideoEntry]:
    """Filtra los videos de la playlist que todavía no están en el vault.
    Deduplica por ID dentro de la propia playlist también (una playlist puede
    listar el mismo video dos veces)."""
    new: list[VideoEntry] = []
    seen: set[str] = set()
    for entry in entries:
        if entry.video_id in already or entry.video_id in seen:
            continue
        seen.add(entry.video_id)
        new.append(entry)
    return new


def _summary_messages(entry: VideoEntry, transcript: str) -> list[dict]:
    """Prompt para el LLM: pedimos JSON estricto con título curado, categoría,
    resumen y temas clave -- el mismo esqueleto que tienen las notas
    existentes hechas con NotebookLM."""
    system = (
        "Sos el asistente Jarvis. Te paso la transcripción de un video de YouTube y tenés que "
        "resumirlo para el vault de conocimiento de Damian. Respondé SOLO con un objeto JSON válido "
        "(sin texto extra, sin markdown, sin ```), con estas claves exactas:\n"
        '  "title": un título curado y descriptivo en español para la nota (NO el título original '
        "del video, uno que describa el CONTENIDO real, como haría un editor).\n"
        '  "category": una sola palabra/frase corta en minúsculas para la categoría temática '
        "(ej. pentesting, programacion, osint, productividad, asistentes-ia, actualidad-ia).\n"
        '  "summary": un resumen denso de 4 a 6 oraciones, en español, en un solo párrafo.\n'
        '  "key_topics": una lista de 4 a 6 strings con los temas clave (frases cortas).'
    )
    user = (
        f'Título original del video: "{entry.title}"\n'
        f"Canal: {entry.channel or 'desconocido'}\n\n"
        f"Transcripción (puede estar recortada):\n{transcript[:_MAX_TRANSCRIPT_CHARS]}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _parse_summary(raw: str, entry: VideoEntry) -> dict:
    """Parsea el JSON que devolvió el LLM, tolerando que lo envuelva en un
    bloque ```json ... ``` o le agregue texto alrededor. Cae a defaults
    razonables si falta alguna clave, para nunca romper por un modelo que se
    salió del formato."""
    text = raw.strip()
    # Si vino envuelto en un fence markdown, quedarse con lo de adentro.
    fence = re.search(r"\{.*\}", text, re.DOTALL)
    if fence:
        text = fence.group(0)
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        data = {}

    title = (data.get("title") or "").strip() or entry.title
    category = (data.get("category") or "").strip().lower() or "general"
    summary = (data.get("summary") or "").strip() or "(sin resumen generado)"
    topics = data.get("key_topics") or []
    if not isinstance(topics, list):
        topics = []
    topics = [str(t).strip() for t in topics if str(t).strip()]
    return {"title": title, "category": category, "summary": summary, "key_topics": topics}


def _relevance_messages(entry: VideoEntry, transcript: str, topics: list[str]) -> list[dict]:
    """Prompt para el discernimiento de UTILIDAD: le pedimos al MISMO LLM que
    juzgue si el video le sirve al proyecto Jarvis, dados sus temas de interés.
    Pide JSON estricto -- mismo patrón que `_summary_messages` -- con veredicto,
    puntaje 1-5 y una justificación de una línea."""
    temas = "\n".join(f"  - {t}" for t in topics)
    system = (
        "Sos el asistente Jarvis evaluando si un video le sirve como información al PROYECTO Jarvis. "
        "Los temas de interés del proyecto son:\n"
        f"{temas}\n\n"
        "Te paso la transcripción de un video y tenés que juzgar qué tan útil/relevante es para esos temas. "
        "Respondé SOLO con un objeto JSON válido (sin texto extra, sin markdown, sin ```), con estas claves exactas:\n"
        '  "verdict": uno de exactamente estos tres valores: "útil", "dudoso", "no útil".\n'
        '  "score": un entero del 1 al 5 (1 = nada que ver con los temas, 5 = directamente sobre uno de ellos).\n'
        '  "reason": una sola oración corta en español justificando el veredicto.\n'
        "No filtres ni descartes nada: solo estás etiquetando. Un video poco relevante igual se guarda."
    )
    user = (
        f'Título original del video: "{entry.title}"\n'
        f"Canal: {entry.channel or 'desconocido'}\n\n"
        f"Transcripción (puede estar recortada):\n{transcript[:_MAX_TRANSCRIPT_CHARS]}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _normalize_verdict(raw_verdict: str, score: int) -> str:
    """Normaliza el veredicto que escribió el LLM a uno de _RELEVANCE_VERDICTS,
    tolerando variantes (sin tilde, 'util', mayúsculas, 'no-util'). Si no se
    reconoce, cae al veredicto derivado del puntaje, así nunca queda vacío."""
    text = (raw_verdict or "").strip().lower()
    normalized = text.replace("-", " ")
    normalized = "".join(c for c in unicodedata.normalize("NFKD", normalized) if not unicodedata.combining(c))
    normalized = " ".join(normalized.split())
    if normalized in ("no util", "no utl", "inutil", "no relevante", "irrelevante"):
        return "no útil"
    if normalized in ("util", "utl", "relevante"):
        return "útil"
    if normalized in ("dudoso", "dudosa", "quizas", "tal vez", "medio"):
        return "dudoso"
    # No se reconoció el texto -> derivar del puntaje.
    if score <= _LOW_RELEVANCE_SCORE:
        return "no útil"
    if score >= 4:
        return "útil"
    return "dudoso"


def _parse_relevance(raw: str, entry: VideoEntry) -> dict:
    """Parsea el JSON del discernimiento de relevancia, con la misma tolerancia
    que `_parse_summary` (fence markdown / texto alrededor / claves faltantes).
    Devuelve siempre {verdict, score, reason} válidos -- nunca rompe la corrida
    por un modelo que se salió del formato; en el peor caso cae a 'dudoso'/3."""
    text = raw.strip()
    fence = re.search(r"\{.*\}", text, re.DOTALL)
    if fence:
        text = fence.group(0)
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        data = {}

    # Puntaje: entero recortado a 1-5. Si no es parseable, default 3 (neutro).
    try:
        score = int(round(float(data.get("score"))))
    except (TypeError, ValueError):
        score = 3
    score = max(1, min(5, score))

    verdict = _normalize_verdict(str(data.get("verdict") or ""), score)

    reason = (data.get("reason") or "").strip()
    if not reason:
        reason = "(sin justificación generada)"
    # Una sola línea: colapsar saltos por si el modelo metió varias.
    reason = " ".join(reason.split())

    is_low = verdict == "no útil" or score <= _LOW_RELEVANCE_SCORE
    return {"verdict": verdict, "score": score, "reason": reason, "is_low": is_low}


def _build_note_content(entry: VideoEntry, summary: dict, relevance: dict) -> str:
    """Arma el Markdown de la nota replicando EXACTO el formato de las notas
    existentes (mismas secciones y wikilinks), cambiando solo la línea
    'Generado con:' a 'resumen automático'."""
    category = summary["category"]
    video_url = f"https://www.youtube.com/watch?v={entry.video_id}"
    duration = entry.duration or "desconocida"
    channel = entry.channel or "desconocido"

    parts = [
        f'Resumen automático generado a partir de la transcripción del video de YouTube '
        f'"{entry.title}", de la playlist personal de Damian "Info para Jarvis".',
        "",
        "## Fuente",
        f"- Video: {video_url}",
        f"- Canal: {channel}",
        f"- Duración: {duration}",
        "- Generado con: resumen automático",
        "",
        "## Resumen",
        summary["summary"],
        "",
        "## Temas clave",
    ]
    if summary["key_topics"]:
        parts.extend(f"- {topic}" for topic in summary["key_topics"])
    else:
        parts.append("- (no se extrajeron temas clave)")

    # ## Relevancia -- el discernimiento de utilidad para el proyecto. Es solo
    # una etiqueta: la nota se crea igual, incluso si es "no útil" (curaduría de
    # Damian). Para baja relevancia se antepone una advertencia visible.
    parts.extend(["", "## Relevancia"])
    if relevance["is_low"]:
        parts.append("⚠️ Marcada como baja relevancia — guardada igual por curaduría de Damian.")
    parts.extend(
        [
            f"- Veredicto: {relevance['verdict']}",
            f"- Puntaje: {relevance['score']}/5",
            f"- Razón: {relevance['reason']}",
        ]
    )

    parts.extend(
        [
            "",
            "## Notas relacionadas",
            f"- [[Índice: {category}]]",
            f"- [[{INDEX_NOTE_TITLE}]]",
        ]
    )
    return "\n".join(parts)


def _update_index(new_note_title: str, entry: VideoEntry, category: str) -> None:
    """Agrega el wikilink de la nota nueva al índice de la playlist y
    recalcula el conteo 'N videos.'. Idempotente: si el wikilink ya está, no
    hace nada."""
    try:
        index = vault.read_note(INDEX_NOTE_ID)
    except FileNotFoundError:
        # El índice debería existir siempre, pero si no está lo dejamos pasar
        # sin romper la ingesta (la nota igual quedó creada y linkeada al hub
        # de categoría).
        return

    wikilink = f"[[{new_note_title}]]"
    if wikilink in index.content:
        return  # ya listado -- idempotencia

    channel = entry.channel or "desconocido"
    bullet = f"- {wikilink} — {entry.title} ({channel}, categoría: {category})"

    content = index.content.rstrip("\n") + "\n" + bullet

    # Recalcular el conteo real de bullets de video y reescribir "N videos.".
    bullet_count = sum(1 for line in content.splitlines() if line.lstrip().startswith("- [["))
    content = re.sub(r"\b\d+\s+videos\.", f"{bullet_count} videos.", content)

    vault.save_note(
        title=index.title,
        content=content,
        author="jarvis",
        tags=index.tags,
        category=index.category,
        note_id=index.id,
    )


async def _process_entry(
    entry: VideoEntry,
    topics: list[str],
    min_relevance: int | None,
    result: IngestResult,
) -> None:
    """Procesa UN video (transcripción → relevancia → resumen → nota → índice) y
    acumula el desenlace en `result`. Es el cuerpo del loop de `ingest_playlist`,
    extraído para que `ingest_video` (un solo video) use EXACTAMENTE la misma
    lógica sin duplicarla. No tira: todo fallo se registra en `result` y vuelve."""
    try:
        transcript = fetch_transcript(entry.video_id)
    except Exception as exc:
        # ERROR TÉCNICO al bajar la transcripción (no "falta de subtítulos": eso lo
        # maneja fetch_transcript devolviendo None). Se registra el MOTIVO real y se
        # sigue, en vez de esconder el bug como si el video no tuviera subtítulos.
        reason = f"{type(exc).__name__}: {exc}"
        print(f"[youtube_ingest] ERROR técnico de transcripción en {entry.video_id} ({entry.title}): {reason}")
        result.transcript_errors.append({"video_id": entry.video_id, "title": entry.title, "error": reason})
        return

    if not transcript:
        # Sin transcripción NO se puede procesar -- independiente de la relevancia.
        result.skipped_no_transcript.append({"video_id": entry.video_id, "title": entry.title})
        return

    # Discernimiento de relevancia + resumen, ambos con el MISMO LLM.
    raw_relevance = await _call_llm(_relevance_messages(entry, transcript, topics))
    relevance = _parse_relevance(raw_relevance, entry)

    # Filtro OPCIONAL por --min-relevance (solo a pedido explícito de Damian).
    if min_relevance is not None and relevance["score"] < min_relevance:
        result.skipped_low_relevance.append(
            {
                "video_id": entry.video_id,
                "title": entry.title,
                "relevancia": relevance["verdict"],
                "relevancia_score": relevance["score"],
            }
        )
        return

    raw = await _call_llm(_summary_messages(entry, transcript))
    summary = _parse_summary(raw, entry)

    content = _build_note_content(entry, summary, relevance)
    # Baja relevancia -> tag extra (la nota se crea igual: es señal, no descarte).
    tags = ["info-para-jarvis", "video", summary["category"]]
    if relevance["is_low"]:
        tags.append("baja-relevancia")

    # Linkear al hub de categoría ANTES de guardar, así la nota nunca queda huérfana.
    vault.link_note_to_category_index(summary["title"], category=summary["category"], author="jarvis")
    note = vault.save_note(
        title=summary["title"],
        content=content,
        author="jarvis",
        tags=tags,
        category=summary["category"],
        extra={"relevancia": relevance["verdict"], "relevancia_score": relevance["score"]},
    )
    _update_index(note.title, entry, summary["category"])
    result.created.append(
        {
            "video_id": entry.video_id,
            "note_id": note.id,
            "title": note.title,
            "relevancia": relevance["verdict"],
            "relevancia_score": relevance["score"],
        }
    )


async def ingest_playlist(
    playlist_url: str = DEFAULT_PLAYLIST_URL,
    max_videos: int | None = None,
    relevance_topics: list[str] | None = None,
    min_relevance: int | None = None,
) -> IngestResult:
    """Corre el pipeline completo sobre una playlist. Async porque el resumen y
    el discernimiento de relevancia se generan con el LLM async de Jarvis.
    Idempotente: los videos ya presentes en el vault se saltan.

    `relevance_topics`: temas de interés contra los que se juzga la utilidad de
    cada video (default: DEFAULT_RELEVANCE_TOPICS).

    `min_relevance`: SOLO si Damian lo pide explícito -- saltea las notas con
    puntaje de relevancia menor a N (1-5). Default None = no filtra NADA: la
    relevancia es una etiqueta, no un filtro (ver filosofía en
    DEFAULT_RELEVANCE_TOPICS). Un video sin transcripción se salta aparte, eso
    NO es un juicio de relevancia."""
    playlist_url = (playlist_url or DEFAULT_PLAYLIST_URL).strip()
    topics = relevance_topics or DEFAULT_RELEVANCE_TOPICS
    entries = fetch_playlist_entries(playlist_url)
    already = existing_video_ids()

    result = IngestResult(playlist_url=playlist_url, total_in_playlist=len(entries))
    result.already_present = [e.video_id for e in entries if e.video_id in already]

    new_videos = select_new_videos(entries, already)
    if max_videos is not None:
        new_videos = new_videos[: max(0, int(max_videos))]

    for i, entry in enumerate(new_videos):
        # Respiro entre videos (menos el primero) para no gatillar el 429 de
        # YouTube por pegarle demasiado rápido. asyncio.sleep para no bloquear
        # el event loop del pipeline async.
        if i > 0:
            await asyncio.sleep(_DELAY_BETWEEN_VIDEOS)
        # Respiro entre videos aparte, el procesamiento de cada uno es idéntico al
        # de un video suelto -> helper compartido (ver _process_entry).
        await _process_entry(entry, topics, min_relevance, result)

    return result


def fetch_video_entry(video_url: str) -> VideoEntry | None:
    """Metadata (título/canal/duración) de UN video con yt-dlp, sin flat. Acepta
    una URL (watch?v=, youtu.be/) o directamente el video_id de 11 chars.
    Devuelve None si no se puede extraer el id. Import perezoso como el resto."""
    import yt_dlp

    raw = (video_url or "").strip()
    m = _VIDEO_ID_RE.search(raw)
    video_id = m.group(1) if m else (raw if re.fullmatch(r"[0-9A-Za-z_-]{11}", raw) else None)
    if not video_id:
        return None
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {"quiet": True, "skip_download": True, **_cookie_opts()}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return VideoEntry(
        video_id=video_id,
        title=(info.get("title") or "").strip() or video_id,
        channel=(info.get("channel") or info.get("uploader") or "").strip(),
        duration=_format_duration(info.get("duration")),
    )


async def ingest_video(
    video_url: str,
    relevance_topics: list[str] | None = None,
    min_relevance: int | None = None,
    force: bool = False,
) -> IngestResult:
    """Ingiere UN video suelto (no una playlist) al vault, con la MISMA lógica que
    `ingest_playlist` (transcripción → relevancia → resumen → nota → índice, vía
    `_process_entry`). Pensado para cuando Damian pasa links de videos individuales.
    Idempotente: si el video ya tiene nota, se saltea salvo `force=True`."""
    topics = relevance_topics or DEFAULT_RELEVANCE_TOPICS
    entry = fetch_video_entry(video_url)
    result = IngestResult(playlist_url=f"(video suelto) {video_url}", total_in_playlist=1 if entry else 0)

    if entry is None:
        result.transcript_errors.append(
            {"video_id": "", "title": video_url, "error": "no pude extraer el video_id/metadata de la URL"}
        )
        return result

    already = existing_video_ids()
    if entry.video_id in already and not force:
        result.already_present = [entry.video_id]
        return result

    await _process_entry(entry, topics, min_relevance, result)
    return result


def _main(argv: list[str] | None = None) -> int:
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(
        description="Ingesta automática de una playlist de YouTube al vault de Obsidian de Jarvis."
    )
    parser.add_argument(
        "playlist_url",
        nargs="?",
        default=DEFAULT_PLAYLIST_URL,
        help=f"URL de la playlist (default: la de Damian, {DEFAULT_PLAYLIST_URL}).",
    )
    parser.add_argument("--max-videos", type=int, default=None, help="Tope de videos nuevos a procesar.")
    parser.add_argument(
        "--min-relevance",
        type=int,
        default=None,
        metavar="N",
        help=(
            "OPCIONAL. Saltea las notas con puntaje de relevancia menor a N (1-5). "
            "Por DEFAULT no filtra nada: la relevancia es solo una etiqueta, todo se guarda. "
            "Usalo solo si querés explícitamente descartar lo de baja relevancia en esta corrida."
        ),
    )
    args = parser.parse_args(argv)

    # Punto de entrada DESATENDIDO: esta CLI la corre un scheduler (ingesta
    # diaria de la playlist), sin un humano mirando. Declara modo AUTÓNOMO
    # explícitamente -- coincide con el default fail-safe del ContextVar, pero
    # dejarlo explícito documenta la intención y loguea el modo/roots efectivos
    # de la corrida. Ver app/operation_mode.py.
    from ..operation_mode import OperationMode, operating_as

    with operating_as(OperationMode.AUTONOMOUS, source="cli_youtube_ingestion"):
        result = asyncio.run(
            ingest_playlist(args.playlist_url, max_videos=args.max_videos, min_relevance=args.min_relevance)
        )

    breakdown = result.relevance_breakdown()
    breakdown_str = ", ".join(f"{v}: {breakdown[v]}" for v in _RELEVANCE_VERDICTS)

    print(f"Playlist: {result.playlist_url}")
    print(f"  Videos en la playlist: {result.total_in_playlist}")
    print(f"  Ya presentes en el vault: {len(result.already_present)}")
    print(f"  Notas nuevas creadas: {len(result.created)} ({breakdown_str})")
    for c in result.created:
        print(f"    + [{c['relevancia']} {c['relevancia_score']}/5] {c['title']}  ({c['video_id']})")
    print(f"  Saltados sin transcripción: {len(result.skipped_no_transcript)}")
    for s in result.skipped_no_transcript:
        print(f"    - {s['title']}  ({s['video_id']})")
    if result.transcript_errors:
        print(f"  Errores TÉCNICOS de transcripción: {len(result.transcript_errors)}")
        for e in result.transcript_errors:
            print(f"    ! {e['title']}  ({e['video_id']}): {e['error']}")
    if result.skipped_low_relevance:
        print(f"  Saltados por --min-relevance {args.min_relevance}: {len(result.skipped_low_relevance)}")
        for s in result.skipped_low_relevance:
            print(f"    - [{s['relevancia']} {s['relevancia_score']}/5] {s['title']}  ({s['video_id']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
