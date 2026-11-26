"""Adaptador real de las fuentes públicas (OpenAlex, Crossref, GDELT, Fed, FRED, Banco Mundial, ReliefWeb, UCDP, MIT, Harvard).

Los parsers son funciones puras: texto o JSON adentro, entradas afuera. Están probados con ejemplos escritos a mano a partir
de la documentación de cada fuente; los pedidos a la red real NO se probaron en la nube (sin salida): corré
`python c-salud/mantenimiento/probar_real.py --fuentes` una vez en la PC y mirá qué dice cada una.

Cortesía con cada fuente: un pedido por vez, pausa mínima entre pedidos, tope de ítems por corrida, y el email de contacto
(INGESTA_CONTACTO_EMAIL, solo en el entorno de la PC) donde la fuente lo pide. Las claves salen de variables de entorno; si
falta una obligatoria no se toca la red. Solo se guardan título, resumen y metadatos con el enlace original."""

from __future__ import annotations

import os
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from urllib.parse import quote, urlencode

from ..fichas import FICHAS, Ficha, ficha_de
from ..model import Entry, Item, SourceError
from ..text import html_to_text, one_line

SOURCE = "fuentes"
_ATOM = "{http://www.w3.org/2005/Atom}"


def _entry(ficha: Ficha, ext_id: str, title: str, url: str, text: str, *, authors=(), published: str = "", **extra) -> Entry:
    sid = f"{ficha.id}/{ext_id}"
    item = Item(
        source=SOURCE,
        source_id=sid,
        title=one_line(title, 300) or sid,
        url=url,
        text=" ".join((text or "").split()),
        authors=[one_line(a, 100) for a in authors if a],
        published=(published or "")[:10],
        extra={"ficha": ficha.id, "credito": ficha.credito, **extra},
    )
    return Entry(source_id=sid, title=item.title, url=url, item=item)


def _plain(html: str) -> str:
    return html_to_text(f"<p>{html or ''}</p>")[1]


# --- parsers (puros) -------------------------------------------------------------------------------------------------------
def parse_rss(ficha: Ficha, xml_text: str, limit: int) -> list[Entry]:
    """RSS 2.0 o Atom: título, enlace, fecha y la bajada (sin HTML)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    out: list[Entry] = []
    for it in list(root.iter("item")) + list(root.iter(f"{_ATOM}entry")):
        link = (it.findtext("link") or "").strip()
        if not link:
            a = it.find(f"{_ATOM}link")
            link = (a.get("href") if a is not None else "") or ""
        title = it.findtext("title") or it.findtext(f"{_ATOM}title") or ""
        desc = it.findtext("description") or it.findtext(f"{_ATOM}summary") or it.findtext(f"{_ATOM}content") or ""
        when = it.findtext("pubDate") or it.findtext(f"{_ATOM}updated") or it.findtext(f"{_ATOM}published") or ""
        guid = (it.findtext("guid") or it.findtext(f"{_ATOM}id") or link).strip()
        if link and guid:
            out.append(_entry(ficha, guid, title, link, _plain(desc), published=_iso(when)))
        if len(out) >= limit:
            break
    return out


_RFC = re.compile(r"(\d{1,2}) (\w{3}) (\d{4})")
_MES = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}


def _iso(stamp: str) -> str:
    """Fecha de un RSS ('Wed, 25 Nov 2026 10:00:00 GMT') o Atom ('2026-11-25T10:00:00Z') a AAAA-MM-DD; '' si no se entiende."""
    s = (stamp or "").strip()
    if re.match(r"\d{4}-\d{2}-\d{2}", s):
        return s[:10]
    m = _RFC.search(s)
    return f"{m.group(3)}-{_MES[m.group(2)]:02d}-{int(m.group(1)):02d}" if m and m.group(2) in _MES else ""


def _abstract(inv: dict | None) -> str:
    """OpenAlex manda el abstract como índice invertido {palabra: [posiciones]}: se rearma el texto."""
    if not inv:
        return ""
    words: dict[int, str] = {}
    for w, pos in inv.items():
        for p in pos:
            words[p] = w
    return " ".join(words[i] for i in sorted(words))


def parse_openalex(ficha: Ficha, data: dict) -> list[Entry]:
    out = []
    for w in data.get("results") or []:
        wid = str(w.get("id") or "").rsplit("/", 1)[-1]
        if not wid:
            continue
        authors = [(a.get("author") or {}).get("display_name", "") for a in (w.get("authorships") or [])[:8]]
        url = w.get("doi") or w.get("id") or ""
        out.append(
            _entry(
                ficha,
                wid,
                w.get("display_name") or w.get("title") or "",
                url,
                _abstract(w.get("abstract_inverted_index")),
                authors=authors,
                published=w.get("publication_date") or "",
            )
        )
    return out


def parse_crossref(ficha: Ficha, data: dict) -> list[Entry]:
    out = []
    for w in (data.get("message") or {}).get("items") or []:
        doi = w.get("DOI")
        if not doi:
            continue
        parts = ((w.get("issued") or {}).get("date-parts") or [[]])[0]
        when = "-".join(f"{int(p):02d}" if i else str(p) for i, p in enumerate(parts[:3])) if parts and parts[0] else ""
        authors = [" ".join(x for x in (a.get("given"), a.get("family")) if x) for a in (w.get("author") or [])[:8]]
        title = (w.get("title") or [""])[0]
        out.append(
            _entry(
                ficha,
                doi,
                title,
                w.get("URL") or f"https://doi.org/{doi}",
                _plain(w.get("abstract") or ""),
                authors=authors,
                published=when,
            )
        )
    return out


def parse_gdelt(ficha: Ficha, data: dict) -> list[Entry]:
    """GDELT no trae el artículo: solo título, dominio, país, idioma y enlace (eso es lo que se guarda)."""
    out = []
    for a in data.get("articles") or []:
        url = a.get("url") or ""
        if not url:
            continue
        seen = str(a.get("seendate") or "")
        when = f"{seen[:4]}-{seen[4:6]}-{seen[6:8]}" if len(seen) >= 8 and seen[:8].isdigit() else ""
        text = (
            f"Titular publicado por {a.get('domain', 'un sitio')} "
            f"({a.get('sourcecountry', 's/d')}, idioma {a.get('language', 's/d')})."
        )
        out.append(
            _entry(
                ficha,
                re.sub(r"\W+", "-", url)[:120],
                a.get("title") or url,
                url,
                text,
                published=when,
                dominio=a.get("domain", ""),
            )
        )
    return out


def parse_worldbank(ficha: Ficha, data) -> list[Entry]:
    """Una nota por indicador y país con sus últimos valores (no una por año)."""
    rows = [r for r in (data[1] if isinstance(data, list) and len(data) > 1 and data[1] else []) if r.get("value") is not None]
    if not rows:
        return []
    ind, pais = rows[0].get("indicator") or {}, rows[0].get("country") or {}
    serie = "; ".join(f"{r['date']}: {r['value']}" for r in rows)
    url = f"https://data.worldbank.org/indicator/{ind.get('id', '')}"
    return [
        _entry(
            ficha,
            f"{pais.get('id', '')}/{ind.get('id', '')}/{rows[0]['date']}",
            f"{ind.get('value', ind.get('id', ''))} — {pais.get('value', '')}",
            url,
            f"Últimos valores (más nuevo primero) — {serie}.",
            published=f"{rows[0]['date']}-01-01",
        )
    ]


def parse_reliefweb(ficha: Ficha, data: dict) -> list[Entry]:
    out = []
    for r in data.get("data") or []:
        f = r.get("fields") or {}
        if not f.get("url"):
            continue
        out.append(
            _entry(
                ficha,
                str(r.get("id")),
                f.get("title") or "",
                f["url"],
                _plain(f.get("body") or ""),
                published=((f.get("date") or {}).get("created") or ""),
            )
        )
    return out


def parse_fred(ficha: Ficha, data: dict, series: str) -> list[Entry]:
    obs = [o for o in data.get("observations") or [] if o.get("value") not in (None, ".")]
    if not obs:
        return []
    serie = "; ".join(f"{o['date']}: {o['value']}" for o in obs)
    return [
        _entry(
            ficha,
            f"{series}/{obs[0]['date']}",
            f"FRED {series}",
            f"https://fred.stlouisfed.org/series/{series}",
            f"Últimas observaciones (más nueva primero) — {serie}.",
            published=obs[0]["date"],
        )
    ]


def parse_ucdp(ficha: Ficha, data: dict) -> list[Entry]:
    out = []
    for e in data.get("Result") or []:
        if e.get("id") is None:
            continue
        lugar = ", ".join(x for x in (e.get("where_coordinates"), e.get("adm_1"), e.get("country")) if x)
        text = (
            f"Evento de violencia organizada: {e.get('side_a', 's/d')} contra {e.get('side_b', 's/d')} en {lugar or 's/d'}. "
            f"Muertes (estimación central): {e.get('best', 's/d')}."
        )
        out.append(
            _entry(
                ficha,
                str(e["id"]),
                f"{e.get('side_a', '')} vs {e.get('side_b', '')} — {e.get('country', '')}",
                "https://ucdp.uu.se/",
                text,
                published=str(e.get("date_start") or ""),
            )
        )
    return out


# --- el adaptador real -----------------------------------------------------------------------------------------------------
class RealFuentes:
    def __init__(
        self,
        get: Callable[[str, dict], str] | None = None,
        env=None,
        sleep=time.sleep,
        clock=time.monotonic,
        timeout: float = 30.0,
    ) -> None:
        self._get = get or self._http_get
        self.env = os.environ if env is None else env
        self.timeout, self._sleep, self._clock = timeout, sleep, clock
        self._last: dict[str, float] = {}

    # `get(url, headers) -> texto`: lo enchufa el test; el real usa httpx
    def _http_get(self, url: str, headers: dict) -> str:
        import httpx

        try:
            r = httpx.get(url, timeout=self.timeout, headers=headers, follow_redirects=True)
        except httpx.HTTPError as exc:
            raise SourceError(f"no pude hablar con la fuente ({type(exc).__name__})", retriable=True) from None
        if r.status_code != 200:
            raise SourceError(f"la fuente respondió {r.status_code}", retriable=r.status_code in (429, 500, 502, 503))
        return r.text

    def _email(self) -> str:
        return (self.env.get("INGESTA_CONTACTO_EMAIL") or "").strip()

    def _pedir(self, ficha: Ficha, url: str, headers: dict | None = None) -> str:
        wait = ficha.pausa - (self._clock() - self._last.get(ficha.id, -1e9))
        if wait > 0:
            self._sleep(wait)
        self._last[ficha.id] = self._clock()
        ua = "RaphaelIngesta/2.0 (asistente personal" + (f"; contacto: {self._email()}" if self._email() else "") + ")"
        return self._get(url, {"User-Agent": ua, **(headers or {})})

    def _json(self, ficha: Ficha, url: str, headers: dict | None = None):
        import json

        try:
            return json.loads(self._pedir(ficha, url, headers))
        except ValueError:
            raise SourceError(f"{ficha.nombre} no devolvió JSON válido") from None

    def search(self, ref: str, limit: int) -> list[Entry]:
        try:
            ficha, q = ficha_de(ref)
        except ValueError as exc:
            raise SourceError(str(exc)) from None
        if not ficha.listo:
            raise SourceError(f"{ficha.nombre} todavía no tiene adaptador ({ficha.nota})")
        falta = [k for k in ficha.claves if not (self.env.get(k) or "").strip()]
        if falta:
            raise SourceError(f"falta {', '.join(falta)} en el entorno de la PC (raphael.env)")
        q = q or ficha.consulta
        n = max(1, min(int(limit), 50))
        return getattr(self, f"_{ficha.id}")(ficha, q, n)

    # --- una función por fuente: arma el pedido y llama a su parser ---
    def _openalex(self, f: Ficha, q: str, n: int):
        p = {"search": q, "per-page": n, "sort": "publication_date:desc"}
        if self._email():
            p["mailto"] = self._email()
        if self.env.get("OPENALEX_API_KEY"):
            p["api_key"] = self.env["OPENALEX_API_KEY"]
        return parse_openalex(f, self._json(f, f"https://api.openalex.org/works?{urlencode(p)}"))

    def _crossref(self, f: Ficha, q: str, n: int):
        p = {"query": q, "rows": n, "sort": "published", "order": "desc"}
        if self._email():
            p["mailto"] = self._email()
        return parse_crossref(f, self._json(f, f"https://api.crossref.org/works?{urlencode(p)}"))

    def _gdelt(self, f: Ficha, q: str, n: int):
        p = {"query": q, "mode": "artlist", "format": "json", "maxrecords": min(n, 250), "sort": "datedesc"}
        return parse_gdelt(f, self._json(f, f"https://api.gdeltproject.org/api/v2/doc/doc?{urlencode(p)}"))

    def _fed(self, f: Ficha, q: str, n: int):
        name = re.sub(r"[^A-Za-z0-9_.]", "", q) or f.consulta  # solo el nombre del feed: no se arma una URL con texto libre
        return parse_rss(f, self._pedir(f, f"https://www.federalreserve.gov/feeds/{name}"), n)

    def _mit(self, f: Ficha, q: str, n: int):
        path = re.sub(r"[^A-Za-z0-9_./-]", "", q).strip("/") or f.consulta
        return parse_rss(f, self._pedir(f, f"https://news.mit.edu/rss/{path}"), n)

    def _harvard(self, f: Ficha, q: str, n: int):
        path = re.sub(r"[^A-Za-z0-9_./-]", "", q).strip("/") or f.consulta
        return parse_rss(f, self._pedir(f, f"https://news.harvard.edu/gazette/{path.removeprefix('gazette/')}"), n)

    def _fred(self, f: Ficha, q: str, n: int):
        sid = re.sub(r"[^A-Za-z0-9_]", "", q)
        p = {
            "series_id": sid,
            "api_key": self.env["FRED_API_KEY"],
            "file_type": "json",
            "sort_order": "desc",
            "limit": min(n, 12),
        }
        return parse_fred(f, self._json(f, f"https://api.stlouisfed.org/fred/series/observations?{urlencode(p)}"), sid)

    def _bancomundial(self, f: Ficha, q: str, n: int):
        pais, _, ind = q.partition("/")
        pais, ind = re.sub(r"[^A-Za-z0-9;]", "", pais), re.sub(r"[^A-Za-z0-9_.]", "", ind)
        if not pais or not ind:
            raise SourceError("el Banco Mundial se consulta como PAÍS/INDICADOR (por ejemplo WLD/NY.GDP.MKTP.CD)")
        url = (
            f"https://api.worldbank.org/v2/country/{pais}/indicator/{ind}?{urlencode({'format': 'json', 'per_page': min(n, 10)})}"
        )
        return parse_worldbank(f, self._json(f, url))

    def _reliefweb(self, f: Ficha, q: str, n: int):
        p = [("appname", self.env["RELIEFWEB_APPNAME"]), ("query[value]", q), ("limit", n), ("sort[]", "date:desc")]
        p += [("fields[include][]", x) for x in ("title", "url", "date.created", "body")]
        return parse_reliefweb(f, self._json(f, f"https://api.reliefweb.int/v2/reports?{urlencode(p)}"))

    def _ucdp(self, f: Ficha, q: str, n: int):
        ver = re.sub(r"[^0-9.]", "", self.env.get("UCDP_VERSION", "")) or "26.1"
        url = f"https://ucdpapi.pcr.uu.se/api/gedevents/{quote(ver)}?{urlencode({'pagesize': n, 'page': 0})}"
        return parse_ucdp(f, self._json(f, url, {"x-ucdp-access-token": self.env["UCDP_TOKEN"]}))


def sources() -> list[str]:
    return [f.id for f in FICHAS.values() if f.listo and f.id != "arxiv"]


if __name__ == "__main__":  # prueba manual: una búsqueda por cada fuente lista
    for fid in sources():
        try:
            es = RealFuentes().search(fid, 2)
            print(fid, "OK", [e.title[:50] for e in es])
        except SourceError as exc:
            print(fid, "FALLA", exc.reason)
