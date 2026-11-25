"""Fechas y línea de tiempo.

`normalize_timestamp` devuelve (ISO sin zona, notas). No adivina: si el formato es ambiguo o falta el año, lo dice en
las notas en vez de callarse. Convención: las fechas con barras son día/mes/año (Argentina).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

_FORMATS = (
    "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
    "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%y %H:%M:%S", "%d/%m/%y %H:%M", "%d/%m/%Y", "%d/%m/%y",
    "%d/%b/%Y:%H:%M:%S %z",
)
_SYSLOG = re.compile(r"^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}$")


def _ambiguous(text: str) -> bool:
    """dd/mm con los dos números <= 12: también podría ser mes/día."""
    a, b = text.split("/")[:2]
    return a.strip().isdigit() and b.strip().isdigit() and int(a) <= 12 and int(b) <= 12


def normalize_timestamp(raw: str | None, *, assume_year: int | None = None) -> tuple[str | None, list[str]]:
    """(ISO UTC sin zona | None, notas). None = no se pudo interpretar (y se dice por qué)."""
    text = (raw or "").strip()
    if not text:
        return None, ["sin fecha"]
    notes: list[str] = []
    if _SYSLOG.match(text):
        year = assume_year or datetime.now(UTC).year
        squeezed = re.sub(r"\s+", " ", text)
        try:
            dt = datetime.strptime(f"{year} {squeezed}", "%Y %b %d %H:%M:%S")
        except ValueError:
            return None, [f"fecha no interpretable: {text!r}"]
        return dt.isoformat(timespec="seconds"), [f"el log no trae año: se asumió {year}"]
    iso = text.replace("Z", "+00:00") if text.endswith("Z") else text
    for fmt in _FORMATS:
        try:
            dt = datetime.strptime(iso, fmt)
        except ValueError:
            continue
        if dt.tzinfo is not None:
            dt = dt.astimezone(UTC).replace(tzinfo=None)
        else:
            notes.append("sin zona horaria: se tomó como está")
        if fmt.startswith("%d/%m") and _ambiguous(text):
            notes.append("fecha ambigua: se leyó día/mes")
        return dt.isoformat(timespec="seconds"), notes
    return None, [f"fecha no interpretable: {text!r}"]


def build_timeline(events: list[dict], *, gap_hours: float = 24.0) -> dict:
    """Los eventos ordenados, y los huecos de más de `gap_hours` entre uno y el siguiente."""
    rows = []
    for e in events:
        ts = e["campos"].get("timestamp_utc")
        if ts:
            rows.append({"id": e["id"], "at": ts, "text": e["campos"].get("descripcion", ""), "source": e["campos"].get("fuente", "")})
    rows.sort(key=lambda r: (r["at"], r["id"]))
    gaps = []
    for a, b in zip(rows, rows[1:], strict=False):
        delta = datetime.fromisoformat(b["at"]) - datetime.fromisoformat(a["at"])
        if delta > timedelta(hours=gap_hours):
            gaps.append({"from": a["at"], "to": b["at"], "hours": round(delta.total_seconds() / 3600, 1)})
    return {"events": rows, "gaps": gaps, "first": rows[0]["at"] if rows else None, "last": rows[-1]["at"] if rows else None}
