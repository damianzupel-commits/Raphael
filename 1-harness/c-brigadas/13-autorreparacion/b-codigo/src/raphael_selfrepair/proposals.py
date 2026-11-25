"""Propuestas de arreglo: se guardan en el espacio de la brigada (las ven el que propone y el que aplica)."""

from __future__ import annotations

import hashlib
import re
import secrets

COLLECTION = "proposals"
ID_RE = re.compile(r"^sf-[0-9a-f]{8}$")

PROPOSED, APPLIED, REVERTED, DISCARDED, REJECTED, FAILED_CHECK = (
    "propuesta", "aplicada", "revertida", "descartada", "rechazada", "revertida_por_verificacion")


def new_id() -> str:
    return f"sf-{secrets.token_hex(4)}"


def digest(file: str, old: str, new: str) -> str:
    """Huella de lo que se va a cambiar. La aprobación queda atada a ella: si la propuesta cambia, no aplica."""
    h = hashlib.sha256()
    for part in (file, old, new):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()


def load(shared, proposal_id: str) -> dict | None:
    return shared.get(COLLECTION, proposal_id) if ID_RE.match(str(proposal_id or "")) else None


def save(shared, proposal: dict) -> dict:
    return shared.put(COLLECTION, proposal["id"], proposal)


def brief(p: dict) -> dict:
    """La propuesta sin los snippets (para listas)."""
    return {k: p.get(k) for k in ("id", "file", "status", "rationale", "created_at", "applied_at", "commit", "finding_id")}
