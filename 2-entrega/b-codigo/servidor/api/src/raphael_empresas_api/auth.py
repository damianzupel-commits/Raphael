"""Clave de la dueña y sesiones de la app.

- La clave se pone desde la consola del servidor (`python -m raphael_empresas_api clave`), nunca por la API: así nadie
  que llegue primero al servidor puede tomarlo. Se guarda solo su hash (PBKDF2-SHA256 con sal).
- `login` con la clave devuelve un token al azar; se guarda solo su hash. Vence a los 90 días sin uso.
- Cinco intentos fallidos en 5 minutos desde la misma dirección -> 15 minutos bloqueada.
Todo vive en el espacio `_api` de la base de la instalación (no lo ve ninguna brigada).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any

SPACE = "_api"
ITERATIONS = 200_000
TOKEN_TTL = timedelta(days=90)
MAX_FAILS, FAIL_WINDOW, LOCKOUT = 5, timedelta(minutes=5), timedelta(minutes=15)
MIN_KEY = 8


def _hash_key(key: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", key.encode("utf-8"), salt, ITERATIONS).hex()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class Auth:
    def __init__(self, store: Any, clock: Any) -> None:
        self.space = store.space(SPACE)
        self.clock = clock
        self._fails: dict[str, deque[datetime]] = defaultdict(deque)
        self._locked: dict[str, datetime] = {}

    # --- la clave
    def has_key(self) -> bool:
        return self.space.get("owner", "key") is not None

    def set_key(self, key: str) -> None:
        if len(key or "") < MIN_KEY:
            raise ValueError(f"la clave tiene que tener al menos {MIN_KEY} caracteres")
        salt = secrets.token_bytes(16)
        self.space.put("owner", "key", {"salt": salt.hex(), "hash": _hash_key(key, salt),
                                        "set": self.clock().isoformat(timespec="seconds")})
        for s in self.space.list("sessions"):           # cambiar la clave cierra todas las sesiones
            self.space.delete("sessions", s["id"])

    def _check_key(self, key: str) -> bool:
        rec = self.space.get("owner", "key")
        if rec is None:
            return False
        return hmac.compare_digest(_hash_key(key or "", bytes.fromhex(rec["salt"])), rec["hash"])

    # --- intentos
    def locked(self, who: str) -> bool:
        until = self._locked.get(who)
        if until and self.clock() < until:
            return True
        self._locked.pop(who, None)
        return False

    def _fail(self, who: str) -> None:
        now = self.clock()
        q = self._fails[who]
        q.append(now)
        while q and now - q[0] > FAIL_WINDOW:
            q.popleft()
        if len(q) >= MAX_FAILS:
            self._locked[who] = now + LOCKOUT
            q.clear()

    # --- sesiones
    def login(self, key: str, who: str, device: str = "") -> str | None:
        if self.locked(who):
            return None
        if not self._check_key(key):
            self._fail(who)
            return None
        self._fails.pop(who, None)
        token = secrets.token_urlsafe(32)
        h = _hash_token(token)
        now = self.clock().isoformat(timespec="seconds")
        self.space.put("sessions", h, {"id": h, "device": (device or "")[:80], "created": now, "last": now})
        return token

    def check(self, token: str | None) -> dict | None:
        if not token:
            return None
        h = _hash_token(token)
        s = self.space.get("sessions", h)
        if s is None:
            return None
        if self.clock() - datetime.fromisoformat(s["last"]) > TOKEN_TTL:
            self.space.delete("sessions", h)
            return None
        s["last"] = self.clock().isoformat(timespec="seconds")
        self.space.put("sessions", h, s)
        return s

    def logout(self, token: str) -> None:
        self.space.delete("sessions", _hash_token(token))
