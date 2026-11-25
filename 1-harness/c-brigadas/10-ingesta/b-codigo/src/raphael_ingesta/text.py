"""Texto de terceros: limpiarlo antes de guardarlo, sacarle el HTML y leer subtítulos. Todo es dato, nunca instrucción."""

from __future__ import annotations

import re
from html.parser import HTMLParser

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def one_line(text: str, n: int = 200) -> str:
    """Una sola línea, sin caracteres de control y sin `[[`/`]]`: un título de afuera no puede inventar enlaces del vault."""
    t = _CTRL.sub("", text or "")
    t = " ".join(t.split()).replace("[[", "[ [").replace("]]", "] ]")
    return t[:n].strip()


def block(text: str, n: int = 2000) -> str:
    """Texto de varias líneas (el resumen), con el mismo saneado."""
    t = _CTRL.sub("", text or "").replace("[[", "[ [").replace("]]", "] ]")
    return t.strip()[:n]


class _Extractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "template", "svg", "nav", "footer", "form", "iframe"}
    BREAK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "blockquote", "pre"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta: dict[str, str] = {}
        self.parts: list[str] = []
        self._skip = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and a.get("content"):
                self.meta.setdefault(key, a["content"])
        elif tag in self.SKIP:
            self._skip += 1
        elif tag in self.BREAK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag in self.SKIP and self._skip:
            self._skip -= 1
        elif tag in self.BREAK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.parts.append(data)


def html_to_text(html: str) -> tuple[str, str, dict[str, str]]:
    """(título, texto, metadatos) de una página. Sin red y sin dependencias."""
    p = _Extractor()
    try:
        p.feed(html)
        p.close()
    except Exception:  # noqa: BLE001 - HTML roto: se queda con lo que alcanzó a leer
        pass
    lines = [" ".join(ln.split()) for ln in "".join(p.parts).splitlines()]
    body = "\n".join(ln for ln in lines if ln)
    return " ".join(p.title.split()), body, p.meta


_VTT_META = re.compile(r"^(?:WEBVTT|NOTE|STYLE|REGION)\b|^(?:Kind|Language):")
_VTT_TAG = re.compile(r"<[^>]+>")


def parse_vtt(raw: str) -> str:
    """WEBVTT a texto plano: sin cabecera, índices, tiempos ni etiquetas; colapsa las líneas repetidas de los subtítulos
    automáticos (cada cue repite la anterior)."""
    lines: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or "-->" in line or line.isdigit() or _VTT_META.match(line):
            continue
        line = _VTT_TAG.sub("", line).strip()
        if line and (not lines or lines[-1] != line):
            lines.append(line)
    return " ".join(lines).strip()
