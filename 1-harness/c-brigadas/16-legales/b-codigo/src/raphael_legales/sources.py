"""Adaptador de fuentes normativas: consulta la fuente oficial EN EL MOMENTO (no de memoria).

Tres implementaciones con la misma interfaz `check(norm, url) -> SourceCheck`:
- `HttpSources`: la real. Trae la página (solo https, tope de tamaño y de tiempo), comprueba que sea la norma esperada
  y guarda la fecha y una huella del texto. Eso prueba que la fuente responde y que cambió o no desde la última vez;
  NO prueba que un resumen nuestro siga vigente: la persona (o un abogado) lo confirma leyendo la fuente.
- `MockSources`: páginas inventadas para los tests, sin red.
- `OffSources`: sin consulta. Todo sale "sin verificar" y se avisa.
"""

from __future__ import annotations

import hashlib
import re
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Protocol

from raphael_core.text_es import normalize

from .norms import Norm

MAX_BYTES = 2_000_000
UA = "Raphael-Legales/2.0 (verificador de fuentes)"


@dataclass(frozen=True)
class SourceCheck:
    norm: str
    url: str
    ok: bool
    mode: str
    checked_at: str
    sha256: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class Sources(Protocol):
    mode: str

    def check(self, norm: Norm, url: str, now: datetime) -> SourceCheck: ...


def _text_of(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    return " ".join(re.sub(r"(?s)<[^>]+>", " ", html).split())


def _judge(norm: Norm, url: str, mode: str, body: str, now: datetime) -> SourceCheck:
    text = _text_of(body)
    low = normalize(text)
    if not any(normalize(w) in low for w in norm.expect):
        return SourceCheck(norm.id, url, False, mode, now.isoformat(timespec="seconds"),
                           error="la página no parece ser la norma esperada")
    return SourceCheck(norm.id, url, True, mode, now.isoformat(timespec="seconds"),
                       sha256=hashlib.sha256(text.encode("utf-8")).hexdigest())


class HttpSources:
    mode = "real"

    def __init__(self, timeout: float = 10.0, fetch: Callable[[str, float], str] | None = None) -> None:
        self.timeout = timeout
        self._fetch = fetch or self._urllib

    @staticmethod
    def _urllib(url: str, timeout: float) -> str:
        req = urllib.request.Request(url, headers={"User-Agent": UA})   # noqa: S310 (https verificado antes)
        with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310
            return r.read(MAX_BYTES).decode("utf-8", errors="replace")

    def check(self, norm: Norm, url: str, now: datetime) -> SourceCheck:
        if not url.lower().startswith("https://"):
            return SourceCheck(norm.id, url, False, self.mode, now.isoformat(timespec="seconds"), error="solo se consultan URLs https")
        try:
            body = self._fetch(url, self.timeout)
        except Exception as exc:   # noqa: BLE001  (red caída, DNS, 4xx/5xx: la brigada sigue y avisa)
            return SourceCheck(norm.id, url, False, self.mode, now.isoformat(timespec="seconds"),
                               error=f"no se pudo consultar: {type(exc).__name__}")
        return _judge(norm, url, self.mode, body, now)


class MockSources:
    """`pages`: url -> texto (o una Exception para simular que la fuente cae). URL desconocida = error."""

    mode = "mock"

    def __init__(self, pages: dict[str, str | Exception] | None = None, default: str | None = None) -> None:
        self.pages = pages if pages is not None else {}
        self.default = default
        self.calls: list[str] = []

    def check(self, norm: Norm, url: str, now: datetime) -> SourceCheck:
        self.calls.append(norm.id)
        page = self.pages.get(url, self.default if self.default is not None else " ".join(norm.expect))
        if isinstance(page, Exception):
            return SourceCheck(norm.id, url, False, self.mode, now.isoformat(timespec="seconds"),
                               error=f"no se pudo consultar: {type(page).__name__}")
        return _judge(norm, url, self.mode, page, now)


class OffSources:
    mode = "off"

    def check(self, norm: Norm, url: str, now: datetime) -> SourceCheck:
        return SourceCheck(norm.id, url, False, self.mode, now.isoformat(timespec="seconds"),
                           error="la consulta de fuentes está apagada (fuentes.modo = off)")


def build_sources(mode: str, timeout: float = 10.0) -> Sources:
    return {"real": lambda: HttpSources(timeout), "mock": MockSources, "off": OffSources}[mode]()
