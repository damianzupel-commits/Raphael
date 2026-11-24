"""Servicios de fondo del servidor: licencia, latido al central, cola del relay y backups."""

from __future__ import annotations

import json
import logging
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

log = logging.getLogger("raphael.servicios")
GRACIA = timedelta(days=7)


def _post(url: str, cuerpo: dict, headers: dict | None = None) -> dict:
    import httpx

    r = httpx.post(url, json=cuerpo, headers=headers or {}, timeout=20)
    r.raise_for_status()
    return r.json()


def _get(url: str, headers: dict | None = None) -> dict:
    import httpx

    r = httpx.get(url, headers=headers or {}, timeout=40)
    r.raise_for_status()
    return r.json()


class Licencia:
    """Valida la clave contra el central. Si el central no responde, sigue andando 7 días con la última validación."""

    def __init__(self, central_url: str, clave: str, instalacion: str, archivo: Path, version: str,
                 post: Callable = _post, reloj: Callable[[], datetime] = datetime.now) -> None:
        self._url, self._clave, self._inst, self._archivo = central_url.rstrip("/"), clave, instalacion, archivo
        self._version, self._post, self._reloj = version, post, reloj
        self.estado = json.loads(archivo.read_text()) if archivo.exists() else {}

    def validar(self) -> dict:
        if not self._url:
            self.estado = {"valida": True, "motivo": "sin central configurado (desarrollo)", "plan": None}
            return self.estado
        try:
            r = self._post(f"{self._url}/api/licencias/validar",
                           {"clave": self._clave, "instalacion": self._inst, "version": self._version})
            self.estado = {**r, "validada": self._reloj().isoformat(timespec="seconds")}
            self._archivo.write_text(json.dumps(self.estado))
        except Exception as e:  # noqa: BLE001
            log.warning("no se pudo validar la licencia: %s", e)
            self.estado = {**self.estado, "ultimo_error": str(e)}
        return self.estado

    @property
    def activa(self) -> bool:
        e = self.estado
        if not self._url:
            return True
        if not e.get("valida") or not e.get("validada"):
            return False
        if e.get("vence") and e["vence"] < self._reloj().date().isoformat():
            return False
        return self._reloj() - datetime.fromisoformat(e["validada"]) <= GRACIA


def latido(central_url: str, clave: str, instalacion: str, estado: dict, post: Callable = _post) -> None:
    """Le cuenta al central que esta instalación está viva (versiones, uso, avisos). Sin datos de clientes."""
    if not central_url:
        return
    try:
        post(f"{central_url.rstrip('/')}/api/latido", {"clave": clave, "instalacion": instalacion, "estado": estado})
    except Exception as e:  # noqa: BLE001
        log.warning("latido fallido: %s", e)


class ColaRelay:
    """Trae del relay los mensajes de Meta de esta instalación (sin abrir puertos en el local)."""

    def __init__(self, url: str, token: str, get: Callable = _get, post: Callable = _post) -> None:
        self._url, self._token, self._get, self._post = url.rstrip("/"), token, get, post

    def traer(self) -> list[dict]:
        if not self._url:
            return []
        h = {"Authorization": f"Bearer {self._token}"}
        r = self._get(f"{self._url}/cola", h)
        items = r.get("items", [])
        if items:
            self._post(f"{self._url}/cola/ack", {"ids": [i["id"] for i in items]}, h)
        return [i["payload"] for i in items]


def hacer_backup(base: Path, carpeta: Path, clave_fernet: str = "", conservar: int = 30,
                 reloj: Callable[[], datetime] = datetime.now) -> Path:
    """Copia consistente de la base (API de backup de SQLite), cifrada si hay clave. Conserva las últimas N."""
    carpeta.mkdir(parents=True, exist_ok=True)
    sello = reloj().strftime("%Y%m%d-%H%M%S")
    tmp = carpeta / f"raphael-{sello}.sqlite"
    origen = sqlite3.connect(str(base))
    destino = sqlite3.connect(str(tmp))
    with destino:
        origen.backup(destino)
    destino.close()
    origen.close()
    final = tmp
    if clave_fernet:
        from cryptography.fernet import Fernet

        final = tmp.with_suffix(".sqlite.cifrado")
        final.write_bytes(Fernet(clave_fernet.encode()).encrypt(tmp.read_bytes()))
        tmp.unlink()
    copias = sorted(carpeta.glob("raphael-*"))
    for viejo in copias[:-conservar]:
        viejo.unlink()
    return final


def restaurar_backup(archivo: Path, base: Path, clave_fernet: str = "") -> None:
    datos = archivo.read_bytes()
    if archivo.suffix == ".cifrado":
        from cryptography.fernet import Fernet

        datos = Fernet(clave_fernet.encode()).decrypt(datos)
    if base.exists():
        shutil.copy2(base, base.with_suffix(".antes-de-restaurar"))
    base.write_bytes(datos)
