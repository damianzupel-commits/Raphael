"""Leer una página web con cuidado: solo http/https, nunca la propia máquina ni la red local, sin credenciales en la URL,
sin seguir redirecciones (una redirección a una dirección interna es la forma clásica de colar un pedido), con tope de
tamaño. El contenido de la página es DATO: se lo reduce a texto y nada de lo que diga se ejecuta ni se obedece."""

from __future__ import annotations

import html
import ipaddress
import re
import socket
import urllib.error
import urllib.parse
import urllib.request

from .env import Env

MAX_PAGE_BYTES = 1_500_000
_SCRIPT = re.compile(r"<(script|style|noscript|template)\b.*?</\1>", re.I | re.S)
_TAGS = re.compile(r"<[^>]+>")
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


class WebError(Exception):
    """No se pudo leer la página. El mensaje se puede mostrar."""


def check_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url.strip())
    if parts.scheme not in ("http", "https"):
        raise WebError("solo se leen direcciones http o https")
    if parts.username or parts.password:
        raise WebError("la dirección trae usuario o clave: no se lee")
    host = parts.hostname or ""
    if not host or host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
        raise WebError("no se leen direcciones de la propia máquina ni de la red local")
    try:
        infos = socket.getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except OSError:
        raise WebError(f"no se pudo resolver {host}") from None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise WebError("la dirección apunta a la red local o interna: no se lee")
    return url.strip()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None


def default_fetch(url: str, params: dict[str, str], headers: dict[str, str], timeout: float = 15.0) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "Raphael-Investigacion/2.0", "Accept": "text/html,text/plain", **headers})  # noqa: S310
    try:
        with urllib.request.build_opener(_NoRedirect).open(req, timeout=timeout) as resp:
            return resp.status, resp.read(MAX_PAGE_BYTES).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ConnectionError(type(exc).__name__) from None


def to_text(raw: str) -> tuple[str, str]:
    """(título, texto) de un HTML."""
    title = html.unescape(_TAGS.sub("", m.group(1))).strip() if (m := _TITLE.search(raw)) else ""
    body = html.unescape(_TAGS.sub(" ", _SCRIPT.sub(" ", raw)))
    return title[:200], re.sub(r"\s+", " ", body).strip()


def fetch_page(env: Env, url: str, *, guard: bool = True) -> dict:
    """{url, status, title, text, retrieved_at}. Lanza WebError si no se puede (o no se debe)."""
    if guard:
        check_url(url)
    getter = env.http_get or default_fetch
    try:
        status, raw = getter(url, {}, {})
    except ConnectionError as exc:
        raise WebError(f"sin conexión ({exc})") from None
    if 300 <= status < 400:
        raise WebError(f"la página redirige (HTTP {status}): no se sigue; pedí la dirección final")
    if status != 200:
        raise WebError(f"la página respondió HTTP {status}")
    title, text = to_text(raw)
    return {"url": url, "status": status, "title": title, "text": text[:200_000], "retrieved_at": env.iso()}
