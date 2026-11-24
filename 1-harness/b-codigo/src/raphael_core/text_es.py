"""Utilidades de texto y fechas en español rioplatense, compartidas por todas las brigadas.

Portado de `raphael_harness.texto` (Empresas 0.4). Mismo comportamiento; nombres en inglés.
Los nombres viejos siguen en `raphael_core.compat.v1.texto`.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta

MONTHS = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
          "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
MONTH_NAMES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
               "noviembre", "diciembre"]
WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_WEEKDAYS_PLAIN = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]

RE_MONTH_IN_WORDS = re.compile(r"\b(" + "|".join(MONTHS) + r")\b")


def normalize(text: str) -> str:
    """Minúsculas y sin tildes ("Publicá" -> "publica", "baño" -> "bano")."""
    d = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in d if not unicodedata.combining(c)).lower()


def clean(text: str, n: int = 200) -> str:
    return " ".join((text or "").split())[:n].strip(" .")


def is_question(text: str) -> bool:
    t = normalize(text).strip()
    return "?" in text or bool(re.match(r"(hacen|tienen|tenes|cuanto|como|donde|cuando|que|aceptan|puedo|se puede)\b", t))


def next_weekday(normalized: str, today: date) -> str | None:
    """'el jueves', 'este sabado', 'el proximo lunes' -> la próxima fecha ISO de ese día (nunca hoy)."""
    m = re.search(r"\b(" + "|".join(_WEEKDAYS_PLAIN) + r")\b", normalized)
    if not m:
        return None
    target = _WEEKDAYS_PLAIN.index(m.group(1))
    ahead = (target - today.weekday()) % 7 or 7
    return (today + timedelta(days=ahead)).isoformat()


def parse_date(normalized: str, today: date) -> str | None:
    """Fecha ISO a partir de texto normalizado: '20/12', 'el 5 de enero', 'en 15 dias', 'manana', 'el jueves'."""
    m = re.search(r"\b(\d{1,2})\s*(?:/|-)\s*(\d{1,2})(?:\s*(?:/|-)\s*(\d{2,4}))?\b", normalized)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), m.group(3)
    else:
        m = re.search(r"\b(\d{1,2}) de (" + "|".join(MONTHS) + r")(?: de (\d{4}))?\b", normalized)
        if m:
            day, month, year = int(m.group(1)), MONTHS[m.group(2)], m.group(3)
        else:
            m = re.search(r"\ben (\d{1,3}) (dias?|semanas?|mes(?:es)?)\b", normalized)
            if m:
                unit = m.group(2)
                n = int(m.group(1)) * (7 if unit.startswith("semana") else 30 if unit.startswith("mes") else 1)
                return (today + timedelta(days=n)).isoformat()
            if re.search(r"\bpasado manana\b", normalized):
                return (today + timedelta(days=2)).isoformat()
            if re.search(r"\bmanana\b", normalized):
                return (today + timedelta(days=1)).isoformat()
            return next_weekday(normalized, today)
    try:
        if year:
            return date(int(year) + (2000 if int(year) < 100 else 0), month, day).isoformat()
        d = date(today.year, month, day)
        return (d if d >= today else date(today.year + 1, month, day)).isoformat()
    except ValueError:
        return None


def parse_time(normalized: str) -> str | None:
    """'a las 16', '16:30', '4 de la tarde', '11hs' -> 'HH:MM'."""
    for m in re.finditer(r"\b(\d{1,2})(?::(\d{2}))?\s*(hs|h|horas)?\b(?:\s*(de la (tarde|noche|manana)))?", normalized):
        h, mi, suffix, part = int(m.group(1)), int(m.group(2) or 0), m.group(3), m.group(5)
        before = normalized[max(0, m.start() - 7):m.start()]
        after = normalized[m.end():m.end() + 3]
        if after.startswith(("/", "-")) or re.match(r"\s*de\s+[a-z]", normalized[m.end():]) and not part:
            continue                                  # es una fecha (20/12, 5 de enero), no una hora
        is_time = m.group(2) or suffix or part or re.search(r"(a las|las|a la)\s*$", before)
        if is_time and 0 <= h <= 23 and 0 <= mi < 60:
            if part in ("tarde", "noche") and h < 12:
                h += 12
            return f"{h:02d}:{mi:02d}"
    return None


def date_in_words(iso: str, today: date) -> str:
    d = date.fromisoformat(iso)
    year = f" de {d.year}" if d.year != today.year else ""
    return f"{WEEKDAYS[d.weekday()]} {d.day} de {MONTH_NAMES[d.month - 1]}{year}"


def short_date(iso: str | None, today: date) -> str:
    if not iso:
        return "sin fecha"
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{d.day:02d}/{d.month:02d}" + (f"/{d.year % 100:02d}" if d.year != today.year else "")


def money(v: float | None) -> str:
    return "$ " + f"{(v or 0):,.0f}".replace(",", ".")


def first_name(name: str) -> str:
    return (name or "").split()[0] if (name or "").split() else ""
