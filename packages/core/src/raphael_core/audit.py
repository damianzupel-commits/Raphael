"""Auditoría única: quién, qué, cuándo y por qué, para todo lo que pasa en la instalación.

Reemplaza al `_registrar` de Empresas y al `audit_log` de JarvisRemote. Es solo de agregar (no hay
borrar ni editar), vive en el espacio `_audit` del almacén y nunca guarda secretos: las claves con
nombre sensible y los valores con forma de token se tachan antes de escribir.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .store import Space

_SECRET_KEY = re.compile(r"(api[_-]?key|token|secret|password|passwd|clave|contrase|authorization|bearer)", re.I)
_SECRET_VALUE = re.compile(
    r"(sk-[A-Za-z0-9_-]{8,}|sk-ant-[A-Za-z0-9_-]{8,}|nvapi-[A-Za-z0-9_-]{8,}|gsk_[A-Za-z0-9]{8,}|ghp_[A-Za-z0-9]{8,}"
    r"|xox[abp]-[A-Za-z0-9-]{8,}|AKIA[0-9A-Z]{16}|EAA[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9._-]{8,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
REDACTED = "[tachado]"
_RESERVED = frozenset({"n", "what", "who", "when", "why"})


def redact(value: Any, _depth: int = 0) -> Any:
    """Copia de `value` sin secretos (recorre dicts y listas)."""
    if _depth > 6:
        return value
    if isinstance(value, dict):
        return {k: (REDACTED if _SECRET_KEY.search(str(k)) else redact(v, _depth + 1)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v, _depth + 1) for v in value]
    if isinstance(value, str):
        return _SECRET_VALUE.sub(REDACTED, value)
    return value


class AuditLog:
    COLLECTION = "entries"

    def __init__(self, space: Space, clock: Callable[[], datetime] | None = None) -> None:
        self._space = space
        self._clock = clock or datetime.now

    def record(self, what: str, *, who: str = "harness", why: str = "", **data: Any) -> dict:
        n = self._space.next(self.COLLECTION)
        head = {"n": n, "what": what, "who": who, "when": self._clock().isoformat(timespec="seconds"),
                **({"why": why} if why else {})}
        # un dato nunca pisa los campos del registro: si choca, se guarda como "data_<clave>"
        body = {(f"data_{k}" if k in _RESERVED else k): v for k, v in redact(data).items()}
        entry = {**head, **body}
        return self._space.put(self.COLLECTION, n, entry)

    def entries(self, what: str | None = None, who: str | None = None, last: int | None = None) -> list[dict]:
        out = self._space.list(self.COLLECTION)
        out = [e for e in out if (what is None or e["what"] == what) and (who is None or e["who"] == who)]
        return out[-last:] if last else out
