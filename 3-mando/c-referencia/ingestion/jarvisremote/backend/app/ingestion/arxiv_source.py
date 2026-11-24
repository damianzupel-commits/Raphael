"""Fuente de intel: arXiv (ciencia) — primera fuente de Raphael Intel (Fase 0 del
spec, ver docs/SPEC-RAPHAEL-INTEL.md). Trae los papers más recientes de las
categorías que te interesan, los resume con tu LLM y los guarda en el vault.

Elegida como piloto porque la API de arXiv es limpia y pública (Atom, sin key) y
alimenta directo a Fénix (neurociencia/biotec).

┌─────────────────────────────────────────────────────────────────────────┐
│ ⚠️  NO PROBADO CONTRA arXiv REAL. Se escribió con el sandbox sin red, así │
│ que el fetch nunca corrió end-to-end contra la API real. El PARSEO del    │
│ Atom, la deduplicación y el armado de nota SÍ están testeados (ver        │
│ tests/test_arxiv_source.py y tests/test_intel_base.py). Corré la CLI UNA  │
│ vez en tu PC (con red y el LLM levantado) para validar el fetch real.     │
└─────────────────────────────────────────────────────────────────────────┘

Uso:
  CLI:  python -m app.ingestion.arxiv_source --limit 5
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from urllib.parse import urlencode

from .base import IntelItem, existing_source_ids, ingest_source

ARXIV_API = "http://export.arxiv.org/api/query"

# Categorías de arranque (configurable por --query). Elegidas para Damian:
#   cs.AI / cs.LG  -> IA y agentes
#   cs.CR          -> criptografía y seguridad
#   q-bio.NC       -> neuronas y cognición (connectómica -> Fénix)
DEFAULT_CATEGORIES = ("cs.AI", "cs.LG", "cs.CR", "q-bio.NC")
DEFAULT_QUERY = " OR ".join(f"cat:{c}" for c in DEFAULT_CATEGORIES)
DEFAULT_LIMIT = 10

# Un arXiv ID nuevo-estilo: AAMM.NNNNN (4 dígitos año-mes, 4-5 de secuencia).
# Se usa para dedup (parseando el cuerpo de las notas ya guardadas) y para
# extraer el id del <id> del Atom (que viene como .../abs/2401.12345v1).
_ARXIV_ID_RE = re.compile(r"arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5})")

_ATOM = "{http://www.w3.org/2005/Atom}"


def parse_atom(xml_text: str) -> list[IntelItem]:
    """Parsea la respuesta Atom de la API de arXiv a IntelItems. Puro y
    determinista (sin red) -- el punto testeable de esta fuente."""
    items: list[IntelItem] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    for entry in root.findall(f"{_ATOM}entry"):
        raw_id = (entry.findtext(f"{_ATOM}id") or "").strip()
        m = _ARXIV_ID_RE.search(raw_id) or re.search(r"abs/([0-9]{4}\.[0-9]{4,5})", raw_id)
        if not m:
            continue
        arxiv_id = m.group(1)
        title = " ".join((entry.findtext(f"{_ATOM}title") or "").split())
        abstract = " ".join((entry.findtext(f"{_ATOM}summary") or "").split())
        published = (entry.findtext(f"{_ATOM}published") or "")[:10]
        authors = [
            (a.findtext(f"{_ATOM}name") or "").strip()
            for a in entry.findall(f"{_ATOM}author")
        ]
        authors = [a for a in authors if a]
        items.append(
            IntelItem(
                source_id=arxiv_id,
                title=title or arxiv_id,
                url=f"https://arxiv.org/abs/{arxiv_id}",
                source="arxiv",
                domain="ciencia",
                text=abstract,
                authors=authors,
                published=published,
            )
        )
    return items


def _http_get(url: str, timeout: float = 30.0) -> str:
    """Trae el XML de la API. Aislado para poder mockearlo en tests."""
    import urllib.request

    req = urllib.request.Request(
        url, headers={"User-Agent": "RaphaelIntel/0.1 (personal research)"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 -- URL fija de arXiv
        return resp.read().decode("utf-8", "replace")


class ArxivSource:
    """Fuente arXiv. Cumple el Protocol `SourceIngester`."""

    name = "arxiv"
    domain = "ciencia"

    def __init__(self, http_get=None) -> None:
        self._http_get = http_get or _http_get

    def fetch(self, query: str, limit: int) -> list[IntelItem]:
        params = urlencode(
            {
                "search_query": query or DEFAULT_QUERY,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
                "start": 0,
                "max_results": max(1, int(limit)),
            }
        )
        xml_text = self._http_get(f"{ARXIV_API}?{params}")
        return parse_atom(xml_text)


async def ingest_arxiv(query: str | None = None, limit: int = DEFAULT_LIMIT) -> dict:
    """Corre la ingesta de arXiv end-to-end contra el vault real. Idempotente:
    los papers que ya tienen nota se saltan."""
    already = existing_source_ids(_ARXIV_ID_RE)
    result = await ingest_source(ArxivSource(), query or DEFAULT_QUERY, limit, already_ids=already)
    return result.to_dict()


def _main(argv: list[str] | None = None) -> int:
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Ingesta de papers de arXiv al vault de Raphael.")
    parser.add_argument("--query", default=None, help=f"Query arXiv (default: {DEFAULT_QUERY}).")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="Cuántos papers nuevos traer.")
    args = parser.parse_args(argv)

    from ..operation_mode import OperationMode, operating_as

    with operating_as(OperationMode.AUTONOMOUS, source="cli_arxiv_ingestion"):
        result = asyncio.run(ingest_arxiv(args.query, limit=args.limit))

    print(f"Fuente: {result['source']} ({result['domain']})")
    print(f"  Papers traídos: {result['total_fetched']}")
    print(f"  Ya presentes: {result['already_present_count']}")
    print(f"  Notas nuevas: {result['created_count']}")
    for c in result["created"]:
        print(f"    + {c['title']}  ({c['source_id']})")
    if result["errors"]:
        print(f"  Errores: {result['errors_count']}")
        for e in result["errors"]:
            print(f"    ! {e['title']}  ({e['source_id']}): {e['error']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
