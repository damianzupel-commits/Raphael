"""Registro versionado de documentos y consentimientos (colecciones del espacio compartido de la brigada).

- `documents`: clave `doc_id` (ej. `politica_privacidad-3`). Cada versión es un registro propio; un borrador se puede
  reemplazar con otra versión, uno EMITIDO es inmutable (se anula con una versión nueva, nunca se pisa).
- `consents`: un registro por contacto y finalidad; la baja no borra: marca `revoked_at` (queda la prueba de que hubo).
- `norm_checks`: la última verificación de cada norma (ver `sources.py`).
"""

from __future__ import annotations

import hashlib
from typing import Any

DOC_STATES = ("borrador", "emitido")


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def next_version(space, kind: str) -> int:
    return 1 + max([d["version"] for d in space.list("documents") if d["kind"] == kind] or [0])


def doc_key(kind: str, version: int) -> str:
    return f"{kind}-{version}"


def save_draft(space, doc: dict[str, Any]) -> dict:
    doc = {**doc, "hash": content_hash(doc["text"])}
    space.put("documents", doc["id"], doc)
    return doc


def get_doc(space, doc_id: str) -> dict | None:
    return space.get("documents", doc_id)


def issue(space, doc_id: str, *, by: str, at: str) -> dict:
    d = get_doc(space, doc_id)
    if d is None:
        raise KeyError(doc_id)
    if d["state"] == "emitido":
        return d
    d = {**d, "state": "emitido", "issued_by": by, "issued_at": at}
    space.put("documents", doc_id, d)
    return d


def issued(space, kind: str) -> dict | None:
    docs = [d for d in space.list("documents") if d["kind"] == kind and d["state"] == "emitido"]
    return max(docs, key=lambda d: d["version"]) if docs else None


def consent_key(contact: str, purpose: str) -> str:
    return f"{contact}|{purpose}"


def record_consent(space, *, contact: str, purpose: str, channel: str, evidence: str, at: str) -> dict:
    rec = {"contact": contact, "purpose": purpose, "channel": channel, "evidence": evidence[:500], "at": at,
           "revoked_at": None}
    space.put("consents", consent_key(contact, purpose), rec)
    return rec


def revoke_consent(space, *, contact: str, purpose: str | None, at: str) -> int:
    n = 0
    for c in space.list("consents"):
        if c["contact"] == contact and (purpose is None or c["purpose"] == purpose) and not c["revoked_at"]:
            space.put("consents", consent_key(c["contact"], c["purpose"]), {**c, "revoked_at": at})
            n += 1
    return n


def has_consent(space, contact: str, purpose: str) -> bool:
    c = space.get("consents", consent_key(contact, purpose))
    return bool(c and not c["revoked_at"])


def active_consents(space) -> list[dict]:
    return [c for c in space.list("consents") if not c["revoked_at"]]
