"""Adaptador real de la web: pide la página con httpx, solo a sitios públicos (también en cada redirección), con tope de
tamaño y de tiempo, y le saca el HTML. NO PROBADO contra sitios reales en la nube (sin red de salida): corré
`python -m raphael_ingesta.adapters.web <url>` una vez en la PC."""

from __future__ import annotations

import hashlib
from urllib.parse import urljoin

from ..model import Item, NoContent, SourceError
from ..safeurl import validate_public_url
from ..text import html_to_text, one_line

MAX_BYTES = 2_000_000
MAX_REDIRECTS = 5
UA = "RaphaelIngesta/2.0 (asistente personal; lectura de paginas publicas)"


def web_id(url: str) -> str:
    """Id estable de una página: la URL pedida sin el `#fragmento`."""
    return hashlib.sha256((url or "").strip().split("#")[0].encode()).hexdigest()[:16]


class RealWeb:
    def __init__(self, timeout: float = 20.0, validate=validate_public_url, client=None) -> None:
        self.timeout = timeout
        self._validate = validate
        self._client = client

    def _get(self, url: str) -> tuple[str, str]:
        import httpx

        client = self._client or httpx.Client(timeout=self.timeout, follow_redirects=False, headers={"User-Agent": UA})
        try:
            for _ in range(MAX_REDIRECTS + 1):
                url = self._validate(url)
                with client.stream("GET", url) as r:
                    if r.is_redirect and r.headers.get("location"):
                        url = urljoin(url, r.headers["location"])
                        continue
                    if r.status_code in (429, 500, 502, 503, 504):
                        raise SourceError(f"el sitio respondió {r.status_code}", retriable=True)
                    if r.status_code >= 400:
                        raise SourceError(f"el sitio respondió {r.status_code}")
                    kind = r.headers.get("content-type", "").split(";")[0].strip().lower()
                    if kind and not (kind.startswith("text/") or "xml" in kind or kind == "application/xhtml+xml"):
                        raise NoContent(f"no es una página de texto ({kind})")
                    data = b""
                    for chunk in r.iter_bytes():
                        data += chunk
                        if len(data) > MAX_BYTES:
                            break
                    return url, data[:MAX_BYTES].decode(r.encoding or "utf-8", "replace")
            raise SourceError("demasiadas redirecciones")
        except httpx.HTTPError as exc:
            raise SourceError(f"no pude traer la página ({type(exc).__name__})", retriable=True) from None

    def fetch(self, url: str) -> Item:
        final, html = self._get(url)
        title, body, meta = html_to_text(html)
        if len(body) < 80:
            raise NoContent("la página casi no tiene texto (puede cargarse con JavaScript)")
        return Item(
            source="web",
            source_id=web_id(url),
            title=one_line(meta.get("og:title") or title or final, 300),
            url=final,
            text=body,
            authors=[one_line(meta["author"], 100)] if meta.get("author") else [],
            published=(meta.get("article:published_time") or meta.get("date") or "")[:10],
        )


if __name__ == "__main__":  # prueba manual
    import sys

    it = RealWeb().fetch(sys.argv[1])
    print(it.title, len(it.text), "caracteres")
