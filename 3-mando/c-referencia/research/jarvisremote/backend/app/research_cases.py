"""Casos de investigación/research retenidos (2026-10-12, pedido de Damian).

Cuando el usuario pide algo difícil ("investiga la guerra en Medio Oriente", "resolvé el
problema del milenio"), se crea un CASO que queda retenido y aparece en la brigada de
Investigación del panel, con varios en paralelo. Esto es distinto del case_store forense de
app/investigation/ (ese es para evidencia digital, pesado): acá es un registro liviano de
"hilos de investigación abiertos".

Persistido en backend/data/research_cases.json. Best-effort: si el disco falla, no rompe el
turno del chat.
"""

from __future__ import annotations

import json
import threading
import time
import unicodedata
import uuid
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "data" / "research_cases.json"
_LOCK = threading.Lock()
_CAP = 100

# Verbos/expresiones que marcan un pedido de investigación explícito (sin acentos, minúsculas).
_RESEARCH_MARKERS = (
    "investiga", "investigar", "investigacion", "research", "indaga", "indagar",
    "averigua a fondo", "analiza a fondo", "profundiza en", "resolve el problema",
    "resolver el problema",
)


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
    return t.lower().strip()


def looks_like_research(message: str) -> bool:
    """Heurística: ¿el mensaje es un pedido explícito de investigar algo? Pensada para ser
    predecible para el usuario (si decís 'investiga ...', se crea un caso)."""
    n = _norm(message)
    return any(m in n for m in _RESEARCH_MARKERS)


def _load() -> dict:
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"cases": []}


def _save(data: dict) -> None:
    try:
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        _PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def create(title: str) -> dict | None:
    """Crea un caso con el título (la pregunta). Dedup: si ya hay uno ABIERTO con el mismo
    título, devuelve ese en vez de duplicar. Devuelve el caso, o None si el título es vacío."""
    title = (title or "").strip()
    if not title:
        return None
    with _LOCK:
        data = _load()
        cases = data.setdefault("cases", [])
        for c in cases:
            if c.get("status") == "abierta" and c.get("title") == title:
                return c
        now = time.time()
        case = {
            "id": uuid.uuid4().hex[:12],
            "title": title,
            "status": "abierta",
            "created_at": now,
            "updated_at": now,
            "findings": 0,
            "last": "",
        }
        cases.insert(0, case)
        del cases[_CAP:]
        _save(data)
        return case


def add_finding(case_id: str, text: str) -> None:
    with _LOCK:
        data = _load()
        for c in data.get("cases", []):
            if c.get("id") == case_id:
                c["findings"] = int(c.get("findings", 0)) + 1
                c["last"] = (text or "")[:300]
                c["updated_at"] = time.time()
                break
        _save(data)


def set_status(case_id: str, status: str) -> list[dict]:
    status = "cerrada" if status == "cerrada" else "abierta"
    with _LOCK:
        data = _load()
        for c in data.get("cases", []):
            if c.get("id") == case_id:
                c["status"] = status
                c["updated_at"] = time.time()
                break
        _save(data)
        return _sorted(data.get("cases", []))


def _sorted(cases: list[dict]) -> list[dict]:
    # Abiertas primero, luego por más reciente.
    return sorted(cases, key=lambda c: (c.get("status") == "cerrada", -float(c.get("updated_at", 0))))


def list_cases() -> list[dict]:
    return _sorted(_load().get("cases", []))
