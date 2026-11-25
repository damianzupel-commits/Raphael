"""Adaptador real de YouTube con `yt-dlp` (opcional: se importa al usarlo). NO PROBADO contra YouTube real (la nube no
tiene red de salida): corré `python -m raphael_ingesta.adapters.youtube <video o lista>` una vez en la PC.

Subtítulos: prefiere manuales sobre automáticos y es -> en -> pt. Un video sin subtítulos es `NoContent` (se saltea, no
rompe); cualquier otro error técnico se informa con su motivo, nunca disfrazado de "sin subtítulos". El 429 se reintenta
con espera creciente.

Cookies, si YouTube pide "confirmar que no sos un bot": `YT_COOKIES_FILE` (cookies.txt) o `YT_COOKIES_BROWSER` (firefox)."""

from __future__ import annotations

import os
import re
import time

from ..model import Entry, Item, NoContent, SourceError
from ..text import one_line, parse_vtt

VIDEO_ID = re.compile(r"(?:v=|/shorts/|/embed/|youtu\.be/)([0-9A-Za-z_-]{11})")
BARE_VIDEO_ID = re.compile(r"^[0-9A-Za-z_-]{11}$")
LANGS = ("es", "en", "pt")
RETRIES = 4
BACKOFF = 3.0


def video_id_of(text: str) -> str | None:
    t = (text or "").strip()
    m = VIDEO_ID.search(t)
    return m.group(1) if m else (t if BARE_VIDEO_ID.match(t) else None)


def is_list_url(text: str) -> bool:
    """Una playlist o un canal (no un video suelto)."""
    t = (text or "").lower()
    return "youtube.com" in t and (
        "list=" in t and "v=" not in t or "/playlist" in t or "/@" in t or "/channel/" in t or "/c/" in t
    )


def format_duration(seconds) -> str:
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return ""
    return f"{total // 60}:{total % 60:02d}" if total > 0 else ""


def pick_track(info: dict) -> tuple[str, str] | None:
    """(idioma, url del .vtt) de la mejor pista: manuales antes que automáticas; dentro de cada grupo es, en, pt."""
    for group in (info.get("subtitles") or {}, info.get("automatic_captions") or {}):
        for prefix in LANGS:
            for lang, formats in group.items():
                if lang.lower().startswith(prefix):
                    for f in formats or []:
                        if f.get("ext") == "vtt" and f.get("url"):
                            return lang, f["url"]
    return None


def rate_limited(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "too many requests" in msg


def _cookies() -> dict:
    f = os.environ.get("YT_COOKIES_FILE", "").strip()
    if f:
        return {"cookiefile": f}
    b = os.environ.get("YT_COOKIES_BROWSER", "").strip().lower()
    return {"cookiesfrombrowser": (b,)} if b else {}


class RealYouTube:
    def __init__(self, sleep=time.sleep) -> None:
        self._sleep = sleep

    @staticmethod
    def _ydl(**opts):
        try:
            import yt_dlp
        except ImportError:
            raise SourceError("falta instalar yt-dlp (pip install yt-dlp) para leer YouTube") from None
        return yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, **_cookies(), **opts})

    def list_playlist(self, url: str) -> list[Entry]:
        try:
            with self._ydl(extract_flat=True) as ydl:
                info = ydl.extract_info(url, download=False)
        except SourceError:
            raise
        except Exception as exc:  # noqa: BLE001 - yt-dlp levanta tipos propios
            raise SourceError(f"no pude leer la lista: {one_line(str(exc), 160)}", retriable=rate_limited(exc)) from None
        out = []
        for e in (info or {}).get("entries") or []:
            vid = (e or {}).get("id") or ""
            if vid:
                out.append(
                    Entry(
                        source_id=vid,
                        title=one_line(e.get("title") or vid, 300),
                        url=f"https://www.youtube.com/watch?v={vid}",
                        channel=one_line(e.get("channel") or e.get("uploader") or "", 100),
                        duration=format_duration(e.get("duration")),
                    )
                )
        return out

    def fetch_video(self, video_id: str) -> Item:
        url = f"https://www.youtube.com/watch?v={video_id}"
        for attempt in range(RETRIES):
            try:
                with self._ydl(retries=3, extractor_retries=2) as ydl:
                    info = ydl.extract_info(url, download=False)
                    track = pick_track(info)
                    if track is None:
                        raise NoContent("el video no tiene subtítulos en español, inglés ni portugués")
                    raw = ydl.urlopen(track[1]).read().decode("utf-8", "replace")
            except SourceError:
                raise
            except Exception as exc:  # noqa: BLE001
                if rate_limited(exc) and attempt < RETRIES - 1:
                    self._sleep(BACKOFF * 2**attempt)
                    continue
                raise SourceError(f"YouTube falló: {one_line(str(exc), 160)}", retriable=rate_limited(exc)) from None
            text = parse_vtt(raw)
            if not text:
                raise NoContent("los subtítulos vinieron vacíos")
            ud = str(info.get("upload_date") or "")
            return Item(
                source="youtube",
                source_id=video_id,
                title=one_line(info.get("title") or video_id, 300),
                url=url,
                text=text,
                authors=[one_line(info.get("channel") or info.get("uploader") or "", 100)],
                published=f"{ud[:4]}-{ud[4:6]}-{ud[6:8]}" if len(ud) == 8 else "",
                extra={"duration": format_duration(info.get("duration")), "lang": track[0]},
            )
        raise SourceError("YouTube limitó los pedidos (429)", retriable=True)


if __name__ == "__main__":  # prueba manual
    import sys

    arg = sys.argv[1]
    yt = RealYouTube()
    if video_id_of(arg):
        it = yt.fetch_video(video_id_of(arg))
        print(it.title, len(it.text), "caracteres")
    else:
        for en in yt.list_playlist(arg)[:5]:
            print(en.source_id, en.title)
