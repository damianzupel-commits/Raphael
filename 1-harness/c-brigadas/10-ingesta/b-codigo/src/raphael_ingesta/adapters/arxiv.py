"""Adaptador real de arXiv: la API pública (Atom, sin clave). El parseo del Atom está probado; el pedido a la red real
NO se probó en la nube (sin red de salida): corré `python -m raphael_ingesta.adapters.arxiv` una vez en la PC."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

from ..model import Entry, Item, NoContent, SourceError
from ..text import one_line

API = "https://export.arxiv.org/api/query"
ID_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/((?:[0-9]{4}\.[0-9]{4,5})|(?:[a-z-]+(?:\.[A-Z]{2})?/[0-9]{7}))", re.I)
BARE_ID = re.compile(r"^(?:arxiv:)?([0-9]{4}\.[0-9]{4,5})(?:v\d+)?$", re.I)
_NS = "{http://www.w3.org/2005/Atom}"


def arxiv_id_of(text: str) -> str | None:
    """El id de arXiv de una URL (abs o pdf) o de un id suelto (2401.12345, con o sin versión)."""
    t = (text or "").strip()
    m = ID_RE.search(t)
    if m:
        return re.sub(r"v\d+$", "", m.group(1))
    m = BARE_ID.match(t)
    return m.group(1) if m else None


def parse_atom(xml_text: str) -> list[Entry]:
    """Atom de arXiv a entradas con su ítem ya armado (la búsqueda trae el abstract). Puro: sin red."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    out: list[Entry] = []
    for e in root.findall(f"{_NS}entry"):
        m = ID_RE.search((e.findtext(f"{_NS}id") or "").strip())
        if not m:
            continue
        aid = re.sub(r"v\d+$", "", m.group(1))
        title = one_line(e.findtext(f"{_NS}title") or "", 300) or aid
        authors = [one_line(a.findtext(f"{_NS}name") or "", 100) for a in e.findall(f"{_NS}author")]
        item = Item(
            source="arxiv",
            source_id=aid,
            title=title,
            url=f"https://arxiv.org/abs/{aid}",
            text=" ".join((e.findtext(f"{_NS}summary") or "").split()),
            authors=[a for a in authors if a],
            published=(e.findtext(f"{_NS}published") or "")[:10],
        )
        out.append(Entry(source_id=aid, title=title, url=item.url, item=item))
    return out


class RealArxiv:
    def __init__(self, get=None, timeout: float = 30.0) -> None:
        self._get = get or self._http_get
        self.timeout = timeout

    def _http_get(self, url: str) -> str:
        import httpx

        try:
            r = httpx.get(url, timeout=self.timeout, headers={"User-Agent": "RaphaelIngesta/2.0 (asistente personal)"})
        except httpx.HTTPError as exc:
            raise SourceError(f"no pude hablar con arXiv ({type(exc).__name__})", retriable=True) from None
        if r.status_code != 200:
            raise SourceError(f"arXiv respondió {r.status_code}", retriable=r.status_code in (429, 500, 502, 503))
        return r.text

    def search(self, query: str, limit: int) -> list[Entry]:
        params = {
            "search_query": query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "start": 0,
            "max_results": max(1, min(int(limit), 50)),
        }
        return parse_atom(self._get(f"{API}?{urlencode(params)}"))

    def fetch(self, arxiv_id: str) -> Item:
        found = parse_atom(self._get(f"{API}?{urlencode({'id_list': arxiv_id})}"))
        if not found or found[0].item is None:
            raise NoContent(f"arXiv no devolvió el paper {arxiv_id}")
        return found[0].item


if __name__ == "__main__":  # prueba manual
    for ent in RealArxiv().search("cat:cs.AI", 2):
        print(ent.source_id, ent.title)
