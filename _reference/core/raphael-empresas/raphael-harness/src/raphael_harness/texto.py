"""Utilidades de texto y fechas en español rioplatense, compartidas por todas las brigadas."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta

MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
         "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
MESES_NOMBRE = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
                "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_DIAS_N = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]

R_MES_EN_LETRAS = re.compile(r"\b(" + "|".join(MESES) + r")\b")


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes ("Publicá" -> "publica", "baño" -> "bano")."""
    d = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in d if not unicodedata.combining(c)).lower()


def limpio(texto: str, n: int = 200) -> str:
    return " ".join((texto or "").split())[:n].strip(" .")


def es_pregunta(texto: str) -> bool:
    t = normalizar(texto).strip()
    return "?" in texto or bool(re.match(r"(hacen|tienen|tenes|cuanto|como|donde|cuando|que|aceptan|puedo|se puede)\b", t))


def dia_semana(normalizado: str, hoy: date) -> str | None:
    """'el jueves', 'este sabado', 'el proximo lunes' -> la próxima fecha ISO de ese día (nunca hoy)."""
    m = re.search(r"\b(" + "|".join(_DIAS_N) + r")\b", normalizado)
    if not m:
        return None
    objetivo = _DIAS_N.index(m.group(1))
    adelante = (objetivo - hoy.weekday()) % 7 or 7
    return (hoy + timedelta(days=adelante)).isoformat()


def parse_fecha(normalizado: str, hoy: date) -> str | None:
    """Fecha ISO a partir de texto normalizado: '20/12', 'el 5 de enero', 'en 15 dias', 'manana', 'el jueves'."""
    m = re.search(r"\b(\d{1,2})\s*(?:/|-)\s*(\d{1,2})(?:\s*(?:/|-)\s*(\d{2,4}))?\b", normalizado)
    if m:
        d, mes, a = int(m.group(1)), int(m.group(2)), m.group(3)
    else:
        m = re.search(r"\b(\d{1,2}) de (" + "|".join(MESES) + r")(?: de (\d{4}))?\b", normalizado)
        if m:
            d, mes, a = int(m.group(1)), MESES[m.group(2)], m.group(3)
        else:
            m = re.search(r"\ben (\d{1,3}) (dias?|semanas?|mes(?:es)?)\b", normalizado)
            if m:
                k = m.group(2)
                n = int(m.group(1)) * (7 if k.startswith("semana") else 30 if k.startswith("mes") else 1)
                return (hoy + timedelta(days=n)).isoformat()
            if re.search(r"\bpasado manana\b", normalizado):
                return (hoy + timedelta(days=2)).isoformat()
            if re.search(r"\bmanana\b", normalizado):
                return (hoy + timedelta(days=1)).isoformat()
            return dia_semana(normalizado, hoy)
    try:
        if a:
            return date(int(a) + (2000 if int(a) < 100 else 0), mes, d).isoformat()
        f = date(hoy.year, mes, d)
        return (f if f >= hoy else date(hoy.year + 1, mes, d)).isoformat()
    except ValueError:
        return None


def parse_hora(normalizado: str) -> str | None:
    """'a las 16', '16:30', '4 de la tarde', '11hs' -> 'HH:MM'."""
    for m in re.finditer(r"\b(\d{1,2})(?::(\d{2}))?\s*(hs|h|horas)?\b(?:\s*(de la (tarde|noche|manana)))?", normalizado):
        h, mi, suf, tarde = int(m.group(1)), int(m.group(2) or 0), m.group(3), m.group(5)
        antes = normalizado[max(0, m.start() - 7):m.start()]
        despues = normalizado[m.end():m.end() + 3]
        if despues.startswith(("/", "-")) or re.match(r"\s*de\s+[a-z]", normalizado[m.end():]) and not tarde:
            continue                                  # es una fecha (20/12, 5 de enero), no una hora
        es_hora = m.group(2) or suf or tarde or re.search(r"(a las|las|a la)\s*$", antes)
        if es_hora and 0 <= h <= 23 and 0 <= mi < 60:
            if tarde in ("tarde", "noche") and h < 12:
                h += 12
            return f"{h:02d}:{mi:02d}"
    return None


def fecha_en_palabras(iso: str, hoy: date) -> str:
    d = date.fromisoformat(iso)
    anio = f" de {d.year}" if d.year != hoy.year else ""
    return f"{DIAS[d.weekday()]} {d.day} de {MESES_NOMBRE[d.month - 1]}{anio}"


def fecha_corta(iso: str | None, hoy: date) -> str:
    if not iso:
        return "sin fecha"
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{d.day:02d}/{d.month:02d}" + (f"/{d.year % 100:02d}" if d.year != hoy.year else "")


def plata(v: float | None) -> str:
    return "$ " + f"{(v or 0):,.0f}".replace(",", ".")


def primer_nombre(nombre: str) -> str:
    return (nombre or "").split()[0] if (nombre or "").split() else ""
