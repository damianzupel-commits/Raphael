"""Tools de la brigada de ejemplo. Sin red: datos fijos, para que la suite de contrato corra en cualquier lado."""

from __future__ import annotations

NOTED: list[dict] = []


def read_agenda(day: str = "hoy") -> dict:
    """Lee los eventos del día."""
    return {"day": day, "events": [{"title": "Cumpleaños de Ana", "time": "20:00"}]}


def note_gift(person: str, idea: str) -> dict:
    """Anota un regalo para comprar (tiene costo: pide aprobación)."""
    NOTED.append({"person": person, "idea": idea})
    return {"status": "anotado", "person": person, "idea": idea}


def scan_network(target: str = "192.168.0.0/24") -> dict:
    """Escaneo activo de ejemplo: no escanea nada, solo existe para probar que en la nube no se carga."""
    return {"target": target, "hosts": []}
