"""Traer páginas web: el sensor web de Raphael. Portado de `tools/web_get.py` (624 líneas de JarvisRemote).

Este módulo es solo el ADAPTADOR (`WebFetcher`): trae una página con un "piso" y devuelve texto y elementos. El escalado
entre pisos, la caché, la deny-list y la guarda de red están en `webreader.py`.

Pisos (de más barato a más caro):
  fast     HTTP simple con la biblioteca estándar. No necesita nada instalado.
  stealth  Scrapling StealthyFetcher (salta antibots). Opcional: `pip install scrapling`.
  dynamic  Scrapling DynamicFetcher (navegador real con JS). Opcional.
Sin Scrapling, los pisos stealth y dynamic avisan que no están y la subida se corta en `fast`.

Cambio respecto de JarvisRemote: el piso `fast` usaba Scrapling; acá usa `urllib` + `html.parser`, así `web_get` funciona
sin instalar nada. Cada salto de una redirección se vuelve a validar (`check_url`), para que una página pública no pueda
mandar a la red local.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Protocol
from urllib.parse import urljoin

from . import AdapterUnavailable

MODES = ("fast", "stealth", "dynamic")
USER_AGENT = "Mozilla/5.0 (compatible; Raphael/1.0)"
MAX_BYTES = 5_000_000
MAX_REDIRECTS = 5
INTERACTIVE_CAP = 60


@dataclass
class FetchedPage:
    url: str
    status: int | None
    text: str
    elements: list[dict] = field(default_factory=list)   # [{"ref","kind","label",...}]
    mode: str = "fast"


class WebFetcher(Protocol):
    def fetch(self, url: str, mode: str, proxy: str | None, check_url: Callable[[str], None]) -> FetchedPage: ...


# --- HTML -> texto y elementos ---------------------------------------------------------------------------------------
class _Extractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "template", "svg", "head"}
    KINDS = {"a": "link", "button": "button", "input": "input", "textarea": "textarea", "select": "select"}
    BLOCKS = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "header", "footer"}

    def __init__(self, base: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base = base
        self.parts: list[str] = []
        self.elements: list[dict] = []
        self._skip = 0
        self._open: dict | None = None   # el link o botón que se está leyendo (su texto es su etiqueta)

    def handle_starttag(self, tag: str, attrs: list) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag in self.SKIP:
            self._skip += 1
            return
        if tag in self.BLOCKS:
            self.parts.append("\n")
        kind = self.KINDS.get(tag)
        if kind is None or len(self.elements) >= INTERACTIVE_CAP:
            return
        if tag == "input" and a.get("type", "text").lower() == "hidden":
            return
        item = {"ref": f"e{len(self.elements) + 1}", "kind": kind,
                "label": (a.get("aria-label") or a.get("placeholder") or a.get("name") or a.get("value") or "")[:80]}
        if kind == "link" and a.get("href"):
            item["href"] = urljoin(self.base, a["href"])[:200]
        if kind == "input":
            item["input_type"] = a.get("type") or "text"
            if a.get("name"):
                item["name"] = a["name"]
        self.elements.append(item)
        if tag in ("a", "button"):
            self._open = item

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        elif tag in ("a", "button"):
            self._open = None
        if tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        self.parts.append(data)
        if self._open is not None and not self._open["label"].strip():
            self._open["label"] = " ".join(data.split())[:80]

    def result(self) -> tuple[str, list[dict]]:
        lines = [" ".join(line.split()) for line in "".join(self.parts).split("\n")]
        return "\n".join(line for line in lines if line), self.elements


def html_to_page(html: str, url: str) -> tuple[str, list[dict]]:
    ex = _Extractor(url)
    ex.feed(html)
    ex.close()
    return ex.result()


# --- real -------------------------------------------------------------------------------------------------------------
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return None


class RealWebFetcher:
    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout

    def fetch(self, url: str, mode: str, proxy: str | None, check_url: Callable[[str], None]) -> FetchedPage:
        if mode == "fast":
            return self._fast(url, proxy, check_url)
        if mode in ("stealth", "dynamic"):
            return self._scrapling(url, mode, proxy)
        raise ValueError(f"piso desconocido: {mode!r}")

    def _fast(self, url: str, proxy: str | None, check_url: Callable[[str], None]) -> FetchedPage:
        handlers: list = [_NoRedirect()]
        if proxy:
            handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        opener = urllib.request.build_opener(*handlers)
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            check_url(current)
            req = urllib.request.Request(current, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
            try:
                resp = opener.open(req, timeout=self.timeout)
            except urllib.error.HTTPError as err:
                if err.code in (301, 302, 303, 307, 308) and err.headers.get("Location"):
                    current = urljoin(current, err.headers["Location"])
                    continue
                return FetchedPage(current, err.code, self._decode(err), mode="fast")
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                raise AdapterUnavailable(f"No se pudo traer {current}: {exc}") from exc
            with resp:
                body = resp.read(MAX_BYTES)
                charset = resp.headers.get_content_charset() or "utf-8"
                ctype = resp.headers.get_content_type()
                status = resp.status
            html = body.decode(charset, errors="replace")
            if "html" in ctype:
                text, elements = html_to_page(html, current)
            else:
                text, elements = html, []
            return FetchedPage(current, status, text, elements, mode="fast")
        raise AdapterUnavailable(f"Demasiadas redirecciones (más de {MAX_REDIRECTS}) desde {url}")

    @staticmethod
    def _decode(err: urllib.error.HTTPError) -> str:
        try:
            return err.read(MAX_BYTES).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            return ""

    def _scrapling(self, url: str, mode: str, proxy: str | None) -> FetchedPage:
        try:
            from scrapling.fetchers import DynamicFetcher, StealthyFetcher
        except ImportError:
            raise AdapterUnavailable("Scrapling no está instalado: no se puede subir al piso "
                                     f"'{mode}'. En la PC: pip install scrapling (extra 'web' del paquete).") from None
        kw = {"proxy": proxy} if proxy else {}
        fetcher = StealthyFetcher if mode == "stealth" else DynamicFetcher
        try:
            page = fetcher.fetch(url, **kw)
        except Exception as exc:  # noqa: BLE001
            raise AdapterUnavailable(f"El piso '{mode}' falló: {exc!r}") from exc
        text = page.get_all_text() if hasattr(page, "get_all_text") else str(page)
        return FetchedPage(getattr(page, "url", url), getattr(page, "status", None), text or "", [], mode=mode)


# --- simulado ---------------------------------------------------------------------------------------------------------
class MockWebFetcher:
    """Páginas en memoria: `pages = {url: {"text", "status", "elements", "blocked_until": "stealth"}}`.

    `blocked_until` simula un sitio antibot: los pisos más baratos devuelven 403 y una página vacía."""

    def __init__(self, pages: dict[str, dict] | None = None) -> None:
        self.pages = dict(pages or {})
        self.calls: list[tuple[str, str]] = []

    def fetch(self, url: str, mode: str, proxy: str | None, check_url: Callable[[str], None]) -> FetchedPage:
        check_url(url)
        self.calls.append((url, mode))
        page = self.pages.get(url)
        if page is None:
            return FetchedPage(url, 404, "", [], mode=mode)
        gate = page.get("blocked_until")
        if gate and MODES.index(mode) < MODES.index(gate):
            return FetchedPage(url, 403, "Just a moment... Cloudflare", [], mode=mode)
        return FetchedPage(url, page.get("status", 200), page.get("text", ""), list(page.get("elements", [])), mode=mode)
