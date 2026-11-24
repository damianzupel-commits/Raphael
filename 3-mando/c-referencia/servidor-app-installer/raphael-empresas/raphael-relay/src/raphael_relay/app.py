"""Relay de Raphael: recibe los webhooks de Meta en la nube y los guarda en una cola por instalación.

El equipo del cliente (detrás del router del local, sin IP pública) los retira con `GET /cola` y
confirma con `POST /cola/ack`. Los mensajes se guardan solo hasta que se retiran (y como mucho 7 días).
Las respuestas NO pasan por acá: el equipo las manda directo a la API de Meta.

instalaciones.yaml:
    - instalacion: "a1b2c3"            # id de la instalación (servidor.json del cliente)
      token: "secreto-largo"           # el mismo RAPHAEL_RELAY_TOKEN del equipo
      whatsapp_phone_ids: ["1234567"]  # metadata.phone_number_id de su número
      instagram_ids: ["1784..."]       # id de su cuenta de Instagram
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from . import __version__

log = logging.getLogger("raphael.relay")
RETENCION = timedelta(days=7)


class Ack(BaseModel):
    ids: list[int]


class Cola:
    def __init__(self, ruta: str) -> None:
        self._db = sqlite3.connect(ruta, check_same_thread=False)
        self._lock = threading.Lock()
        self._db.execute("CREATE TABLE IF NOT EXISTS cola (id INTEGER PRIMARY KEY AUTOINCREMENT, instalacion TEXT,"
                         " payload TEXT, llegado TEXT)")
        self._db.commit()

    def poner(self, instalacion: str, payload: dict) -> None:
        with self._lock:
            self._db.execute("INSERT INTO cola (instalacion, payload, llegado) VALUES (?, ?, ?)",
                             (instalacion, json.dumps(payload), datetime.now().isoformat(timespec="seconds")))
            self._db.commit()

    def sacar(self, instalacion: str, limite: int = 50) -> list[dict]:
        with self._lock:
            limite_viejo = (datetime.now() - RETENCION).isoformat(timespec="seconds")
            self._db.execute("DELETE FROM cola WHERE llegado < ?", (limite_viejo,))
            self._db.commit()
            rows = self._db.execute("SELECT id, payload FROM cola WHERE instalacion = ? ORDER BY id LIMIT ?",
                                    (instalacion, limite)).fetchall()
        return [{"id": i, "payload": json.loads(p)} for i, p in rows]

    def confirmar(self, instalacion: str, ids: list[int]) -> int:
        if not ids:
            return 0
        with self._lock:
            n = self._db.execute(f"DELETE FROM cola WHERE instalacion = ? AND id IN ({','.join('?' * len(ids))})",
                                 (instalacion, *ids)).rowcount
            self._db.commit()
        return n

    def pendientes(self) -> dict[str, int]:
        return dict(self._db.execute("SELECT instalacion, COUNT(*) FROM cola GROUP BY instalacion").fetchall())


class Rutas:
    def __init__(self, instalaciones: list[dict]) -> None:
        self.por_token = {i["token"]: i["instalacion"] for i in instalaciones}
        self.por_wa = {str(p): i["instalacion"] for i in instalaciones for p in i.get("whatsapp_phone_ids", [])}
        self.por_ig = {str(p): i["instalacion"] for i in instalaciones for p in i.get("instagram_ids", [])}
        if len(self.por_token) != len(instalaciones):
            raise ValueError("cada instalación necesita un token propio")

    @classmethod
    def desde_archivo(cls, ruta: str | Path) -> "Rutas":
        return cls(yaml.safe_load(Path(ruta).read_text(encoding="utf-8")) or [])

    def repartir(self, payload: dict) -> list[tuple[str, dict]]:
        """Separa un webhook de Meta por instalación (un webhook puede traer varias entradas)."""
        out: dict[str, list] = {}
        objeto = payload.get("object")
        for entry in payload.get("entry", []) or []:
            destino = None
            if objeto == "whatsapp_business_account":
                for ch in entry.get("changes", []) or []:
                    pid = str(((ch.get("value") or {}).get("metadata") or {}).get("phone_number_id", ""))
                    destino = self.por_wa.get(pid) or destino
            elif objeto == "instagram":
                destino = self.por_ig.get(str(entry.get("id", "")))
            if destino:
                out.setdefault(destino, []).append(entry)
            else:
                log.warning("webhook sin instalación conocida (%s)", objeto)
        return [(inst, {"object": objeto, "entry": entries}) for inst, entries in out.items()]


def firma_ok(secreto: str, cuerpo: bytes, cabecera: str | None) -> bool:
    if not secreto or not cabecera or not cabecera.startswith("sha256="):
        return False
    return hmac.compare_digest(cabecera[7:], hmac.new(secreto.encode(), cuerpo, hashlib.sha256).hexdigest())


def crear_app(rutas: Rutas | None = None, cola: Cola | None = None, app_secret: str | None = None,
              verify_token: str | None = None) -> FastAPI:
    rutas = rutas or Rutas.desde_archivo(os.environ.get("RELAY_INSTALACIONES", "instalaciones.yaml"))
    cola = cola or Cola(os.environ.get("RELAY_BASE", "relay.sqlite"))
    secreto = app_secret if app_secret is not None else os.environ.get("META_APP_SECRET", "")
    verificar = verify_token if verify_token is not None else os.environ.get("META_VERIFY_TOKEN", "")
    app = FastAPI(title="Raphael relay", version=__version__, docs_url=None, redoc_url=None)

    def instalacion(request: Request) -> str:
        tok = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        inst = rutas.por_token.get(tok)
        if not inst:
            raise HTTPException(401, "token inválido")
        return inst

    @app.get("/salud")
    def salud():
        return {"ok": True, "version": __version__, "en_cola": sum(cola.pendientes().values())}

    @app.get("/webhook/meta", response_class=PlainTextResponse)
    def verificar_webhook(request: Request):
        q = request.query_params
        if q.get("hub.mode") == "subscribe" and verificar and q.get("hub.verify_token") == verificar:
            return q.get("hub.challenge", "")
        raise HTTPException(403, "token de verificación inválido")

    @app.post("/webhook/meta")
    async def webhook(request: Request):
        cuerpo = await request.body()
        if not firma_ok(secreto, cuerpo, request.headers.get("x-hub-signature-256")):
            raise HTTPException(403, "firma inválida")
        partes = rutas.repartir(json.loads(cuerpo))
        for inst, sub in partes:
            cola.poner(inst, sub)
        return {"encolados": len(partes)}

    @app.get("/cola")
    def sacar(request: Request):
        return {"items": cola.sacar(instalacion(request))}

    @app.post("/cola/ack")
    def ack(b: Ack, request: Request):
        return {"borrados": cola.confirmar(instalacion(request), b.ids)}

    return app
