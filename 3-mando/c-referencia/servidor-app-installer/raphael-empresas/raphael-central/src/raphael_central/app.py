"""Central de Raphael (lo maneja Damián): licencias de los clientes y panel de soporte.

- Cada cliente tiene una clave de licencia con plan y vencimiento. La primera instalación que la
  valida queda atada a ella (una clave no sirve en dos equipos).
- Cada instalación manda un latido cada 15 minutos con versiones, uso y avisos. Nunca datos de clientes.
- El panel (`/admin`) muestra qué instalaciones están vivas y cuáles necesitan atención.
"""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import string
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from . import __version__

SIN_LATIDO = timedelta(hours=1)
PLANES = ("basico", "pro", "privado", "premium")


class Validar(BaseModel):
    clave: str
    instalacion: str
    version: str = ""


class Latido(BaseModel):
    clave: str
    instalacion: str
    estado: dict


class NuevaLicencia(BaseModel):
    cliente: str
    plan: str = "basico"
    vence: str | None = None
    notas: str = ""


class Cambio(BaseModel):
    activa: bool | None = None
    plan: str | None = None
    vence: str | None = None
    liberar_instalacion: bool = False


def nueva_clave() -> str:
    abc = string.ascii_uppercase + string.digits
    return "RAPH-" + "-".join("".join(secrets.choice(abc) for _ in range(4)) for _ in range(3))


class Base:
    def __init__(self, ruta: str, reloj: Callable[[], datetime] = datetime.now) -> None:
        self._db = sqlite3.connect(ruta, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self.reloj = reloj
        self._db.executescript(
            "CREATE TABLE IF NOT EXISTS licencias (clave TEXT PRIMARY KEY, cliente TEXT, plan TEXT, vence TEXT, activa INTEGER,"
            " instalacion TEXT, creada TEXT, notas TEXT);"
            "CREATE TABLE IF NOT EXISTS latidos (instalacion TEXT PRIMARY KEY, clave TEXT, cuando TEXT, estado TEXT, version TEXT);")
        self._db.commit()

    def crear(self, cliente: str, plan: str, vence: str | None, notas: str = "") -> dict:
        if plan not in PLANES:
            raise ValueError(f"plan inválido: {plan}")
        clave = nueva_clave()
        with self._lock:
            self._db.execute("INSERT INTO licencias VALUES (?, ?, ?, ?, 1, NULL, ?, ?)",
                             (clave, cliente, plan, vence, self.reloj().isoformat(timespec="seconds"), notas))
            self._db.commit()
        return self.licencia(clave)

    def licencia(self, clave: str) -> dict | None:
        row = self._db.execute("SELECT * FROM licencias WHERE clave = ?", (clave,)).fetchone()
        return dict(row) if row else None

    def licencias(self) -> list[dict]:
        return [dict(r) for r in self._db.execute("SELECT * FROM licencias ORDER BY creada DESC")]

    def cambiar(self, clave: str, c: Cambio) -> dict:
        lic = self.licencia(clave)
        if not lic:
            raise KeyError(clave)
        if c.plan is not None and c.plan not in PLANES:
            raise ValueError(f"plan inválido: {c.plan}")
        nuevos = {"activa": int(c.activa) if c.activa is not None else lic["activa"], "plan": c.plan or lic["plan"],
                  "vence": c.vence if c.vence is not None else lic["vence"],
                  "instalacion": None if c.liberar_instalacion else lic["instalacion"]}
        with self._lock:
            self._db.execute("UPDATE licencias SET activa = ?, plan = ?, vence = ?, instalacion = ? WHERE clave = ?",
                             (nuevos["activa"], nuevos["plan"], nuevos["vence"], nuevos["instalacion"], clave))
            self._db.commit()
        return self.licencia(clave)

    def validar(self, clave: str, instalacion: str) -> dict:
        lic = self.licencia(clave)
        if not lic:
            return {"valida": False, "motivo": "clave inexistente"}
        if not lic["activa"]:
            return {"valida": False, "motivo": "licencia suspendida", "plan": lic["plan"]}
        if lic["vence"] and lic["vence"] < self.reloj().date().isoformat():
            return {"valida": False, "motivo": "licencia vencida", "plan": lic["plan"], "vence": lic["vence"]}
        if lic["instalacion"] and lic["instalacion"] != instalacion:
            return {"valida": False, "motivo": "la clave está en uso en otra instalación"}
        if not lic["instalacion"]:
            with self._lock:
                self._db.execute("UPDATE licencias SET instalacion = ? WHERE clave = ?", (instalacion, clave))
                self._db.commit()
        return {"valida": True, "plan": lic["plan"], "vence": lic["vence"], "cliente": lic["cliente"]}

    def latido(self, clave: str, instalacion: str, estado: dict) -> bool:
        lic = self.licencia(clave)
        if not lic or lic["instalacion"] != instalacion:
            return False
        with self._lock:
            self._db.execute("INSERT INTO latidos VALUES (?, ?, ?, ?, ?) ON CONFLICT(instalacion) DO UPDATE SET clave = excluded.clave,"
                             " cuando = excluded.cuando, estado = excluded.estado, version = excluded.version",
                             (instalacion, clave, self.reloj().isoformat(timespec="seconds"), json.dumps(estado),
                              str(estado.get("servidor", ""))))
            self._db.commit()
        return True

    def instalaciones(self) -> list[dict]:
        out = []
        ahora = self.reloj()
        for lic in self.licencias():
            lat = self._db.execute("SELECT * FROM latidos WHERE instalacion = ?", (lic["instalacion"],)).fetchone() if lic["instalacion"] else None
            estado = json.loads(lat["estado"]) if lat else {}
            alertas = []
            if not lic["instalacion"]:
                alertas.append("sin instalar")
            elif not lat or ahora - datetime.fromisoformat(lat["cuando"]) > SIN_LATIDO:
                alertas.append("sin latido hace más de 1 hora")
            if estado.get("envios_fallidos"):
                alertas.append(f"{estado['envios_fallidos']} envíos fallidos")
            if (estado.get("uso") or {}).get("excedido"):
                alertas.append("pasó el tope de mensajes del plan")
            alertas += [f"aviso: {a}" for a in estado.get("avisos", [])]
            if lic["vence"] and lic["vence"] < (ahora.date() + timedelta(days=7)).isoformat():
                alertas.append(f"vence el {lic['vence']}")
            out.append({"cliente": lic["cliente"], "clave": lic["clave"], "plan": lic["plan"], "activa": bool(lic["activa"]),
                        "vence": lic["vence"], "instalacion": lic["instalacion"], "ultimo_latido": lat["cuando"] if lat else None,
                        "version": lat["version"] if lat else None, "brigadas": estado.get("brigadas", {}),
                        "uso": estado.get("uso", {}), "pendientes": estado.get("pendientes"), "alertas": alertas})
        return out


def crear_app(base: Base | None = None, admin_token: str | None = None) -> FastAPI:
    base = base or Base(os.environ.get("CENTRAL_BASE", "central.sqlite"))
    token = admin_token if admin_token is not None else os.environ.get("CENTRAL_ADMIN_TOKEN", "")
    if len(token) < 16:
        raise RuntimeError("CENTRAL_ADMIN_TOKEN tiene que tener al menos 16 caracteres")
    app = FastAPI(title="Raphael central", version=__version__, docs_url=None, redoc_url=None)

    def admin(request: Request) -> None:
        if not secrets.compare_digest(request.headers.get("authorization", "").removeprefix("Bearer ").strip(), token):
            raise HTTPException(401, "no autorizado")

    @app.get("/salud")
    def salud():
        return {"ok": True, "version": __version__}

    @app.post("/api/licencias/validar")
    def validar(b: Validar):
        return base.validar(b.clave, b.instalacion)

    @app.post("/api/latido")
    def latido(b: Latido):
        if not base.latido(b.clave, b.instalacion, b.estado):
            raise HTTPException(403, "licencia o instalación desconocida")
        return {"ok": True}

    privado = [Depends(admin)]

    @app.get("/admin/licencias", dependencies=privado)
    def licencias():
        return base.licencias()

    @app.post("/admin/licencias", dependencies=privado)
    def crear(b: NuevaLicencia):
        try:
            if b.vence:
                date.fromisoformat(b.vence)
            return base.crear(b.cliente, b.plan, b.vence, b.notas)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e

    @app.post("/admin/licencias/{clave}", dependencies=privado)
    def cambiar(clave: str, b: Cambio):
        try:
            return base.cambiar(clave, b)
        except KeyError as e:
            raise HTTPException(404, "no existe esa licencia") from e
        except ValueError as e:
            raise HTTPException(400, str(e)) from e

    @app.get("/admin/instalaciones", dependencies=privado)
    def instalaciones():
        return base.instalaciones()

    @app.get("/admin", response_class=HTMLResponse)
    def panel():
        return (Path(__file__).with_name("panel.html")).read_text(encoding="utf-8")

    return app
