"""Texto: normalización, tokens y extractos. Puro, sin dependencias."""

from __future__ import annotations

import re
import unicodedata

_WORD = re.compile(r"[a-z0-9ñ]+")
STOPWORDS = frozenset(
    "de la el los las un una unos unas y o a en que es por con para del al se su sus lo le les mi tu me te como mas "
    "pero sin sobre este esta esto ese esa eso son fue ser hay muy ya no si".split())


def strip_accents(text: str) -> str:
    nfd = unicodedata.normalize("NFD", text or "")
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def norm(text: str) -> str:
    return strip_accents(text).lower()


def tokens(text: str, *, min_len: int = 3, drop_stop: bool = True) -> list[str]:
    out = [w for w in _WORD.findall(norm(text)) if len(w) >= min_len or w.isdigit()]
    return [w for w in out if not (drop_stop and w in STOPWORDS)]


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", norm(title)).strip("-")
    return slug or "nota"


def extracto_relevante(content: str, query: str, max_chars: int = 380) -> str:
    """Las oraciones de `content` que más tienen que ver con `query`, COPIADAS tal cual y en su orden original (nunca un
    resumen: cifras, nombres y fechas quedan como están). Determinista: cuenta términos de la consulta (de 4+ letras) por
    oración; si ninguna matchea, el comienzo de la nota. Acotado a `max_chars`."""
    texto = " ".join((content or "").split())
    if len(texto) <= max_chars:
        return texto
    terminos = {w for w in _WORD.findall(norm(query)) if len(w) >= 4}
    oraciones = [o for o in re.split(r"(?<=[.!?…])\s+", texto) if o]
    puntajes = [sum(1 for t in terminos if t in norm(o)) for o in oraciones]
    if not terminos or max(puntajes, default=0) == 0:
        return texto[: max_chars - 1].rstrip() + "…"
    elegidas: set[int] = set()
    usado = 0
    for i in sorted(range(len(oraciones)), key=lambda k: (-puntajes[k], k)):
        if puntajes[i] == 0 or usado + len(oraciones[i]) + 1 > max_chars:
            continue
        elegidas.add(i)
        usado += len(oraciones[i]) + 1
    if not elegidas:   # la mejor oración sola ya no entra: se recorta
        mejor = max(range(len(oraciones)), key=lambda k: puntajes[k])
        return oraciones[mejor][: max_chars - 1].rstrip() + "…"
    return " ".join(oraciones[i] for i in sorted(elegidas))
