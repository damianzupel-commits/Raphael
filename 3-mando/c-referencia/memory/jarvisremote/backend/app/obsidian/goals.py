"""Metas persistentes de Raphael (Etapa C, ver `vision/ETAPAS-BCD-diseno.md`).

Objetivos que Damian fija y que PERSISTEN entre sesiones, dándole a Raphael dirección
propia: sesgan qué prioriza la curiosidad y hacia dónde apunta la proactividad. Un
cerebro con metas, no solo reactivo.

Store simple en JSON (profile-aware, junto al índice de embeddings). PROCESADOR: tier 0.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from ..config import settings
from . import profile


def _path() -> Path:
    emb = Path(profile.current_embeddings_path(settings.obsidian_embeddings_path))
    p = emb.parent / "goals.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load() -> list[dict]:
    p = _path()
    if not p.is_file():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save(goals: list[dict]) -> None:
    _path().write_text(json.dumps(goals, ensure_ascii=False), encoding="utf-8")


def add(texto: str) -> dict:
    texto = (texto or "").strip()
    if not texto:
        return {"error": "meta vacía"}
    goals = load()
    gid = hashlib.sha1((texto + str(time.time())).encode("utf-8")).hexdigest()[:8]
    goal = {"id": gid, "texto": texto, "creada": datetime.now(timezone.utc).isoformat()}
    goals.append(goal)
    save(goals)
    return goal


def remove(gid: str) -> bool:
    goals = load()
    nuevos = [g for g in goals if g.get("id") != gid and g.get("texto") != gid]
    if len(nuevos) == len(goals):
        return False
    save(nuevos)
    return True


def list_goals() -> list[dict]:
    return load()
