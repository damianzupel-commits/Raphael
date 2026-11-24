"""Acceso de la dueña al panel: clave hasheada (scrypt) y sesiones firmadas. Nada de esto sale del equipo."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from pathlib import Path

DURACION_SESION = 30 * 24 * 3600


class Secretos:
    def __init__(self, archivo: Path) -> None:
        self._archivo = archivo
        if archivo.exists():
            self._d = json.loads(archivo.read_text(encoding="utf-8"))
        else:
            self._d = {"instalacion": uuid.uuid4().hex, "firma": secrets.token_hex(32), "clave": None}
            self._guardar()
        self._intentos: dict[str, list[float]] = {}

    def _guardar(self) -> None:
        self._archivo.parent.mkdir(parents=True, exist_ok=True)
        self._archivo.write_text(json.dumps(self._d, indent=2), encoding="utf-8")

    @property
    def instalacion(self) -> str:
        return self._d["instalacion"]

    @property
    def tiene_clave(self) -> bool:
        return bool(self._d.get("clave"))

    def poner_clave(self, clave: str) -> None:
        if len(clave) < 8:
            raise ValueError("la clave tiene que tener al menos 8 caracteres")
        sal = secrets.token_bytes(16)
        h = hashlib.scrypt(clave.encode(), salt=sal, n=2**14, r=8, p=1)
        self._d["clave"] = base64.b64encode(sal + h).decode()
        self._guardar()

    def verificar_clave(self, clave: str, origen: str = "-") -> bool:
        ahora = time.time()
        intentos = [t for t in self._intentos.get(origen, []) if ahora - t < 600]
        if len(intentos) >= 5:
            return False                                  # 5 intentos fallidos en 10 minutos: esperar
        raw = base64.b64decode(self._d.get("clave") or "")
        ok = False
        if raw:
            sal, h = raw[:16], raw[16:]
            ok = hmac.compare_digest(h, hashlib.scrypt(clave.encode(), salt=sal, n=2**14, r=8, p=1))
        if not ok:
            self._intentos[origen] = [*intentos, ahora]
        return ok

    def sesion(self) -> str:
        vence = int(time.time()) + DURACION_SESION
        carga = f"duena.{vence}"
        firma = hmac.new(self._d["firma"].encode(), carga.encode(), hashlib.sha256).hexdigest()
        return f"{carga}.{firma}"

    def sesion_valida(self, token: str) -> bool:
        try:
            quien, vence, firma = token.split(".")
        except ValueError:
            return False
        esperada = hmac.new(self._d["firma"].encode(), f"{quien}.{vence}".encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(firma, esperada) and int(vence) > time.time()
