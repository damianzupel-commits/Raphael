"""Almacén de datos: una base SQLite por instalación, con un ESPACIO por brigada.

Cada brigada guarda sus documentos (JSON) en su espacio y no ve los de las otras. No hay
esquemas compartidos: una brigada puede cambiar cómo guarda sus datos sin migrar nada ajeno.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from typing import Any, Callable


class Almacen:
    def __init__(self, ruta: str = ":memory:", reloj: Callable[[], datetime] | None = None) -> None:
        self._db = sqlite3.connect(ruta, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._reloj = reloj or datetime.now
        with self._lock:
            self._db.executescript(
                "CREATE TABLE IF NOT EXISTS docs (espacio TEXT, coleccion TEXT, clave TEXT, json TEXT, actualizado TEXT,"
                " PRIMARY KEY (espacio, coleccion, clave));"
                "CREATE TABLE IF NOT EXISTS contadores (espacio TEXT, coleccion TEXT, valor INTEGER,"
                " PRIMARY KEY (espacio, coleccion));")
            self._db.commit()

    def espacio(self, nombre: str) -> "Espacio":
        return Espacio(self, nombre)

    def cerrar(self) -> None:
        self._db.close()


class Espacio:
    """Los datos de UNA brigada."""

    def __init__(self, almacen: Almacen, nombre: str) -> None:
        self._a = almacen
        self.nombre = nombre

    def guardar(self, coleccion: str, clave: str | int, dato: dict) -> dict:
        with self._a._lock:
            self._a._db.execute(
                "INSERT INTO docs VALUES (?, ?, ?, ?, ?) ON CONFLICT(espacio, coleccion, clave) DO UPDATE SET"
                " json = excluded.json, actualizado = excluded.actualizado",
                (self.nombre, coleccion, str(clave), json.dumps(dato, ensure_ascii=False), self._a._reloj().isoformat()))
            self._a._db.commit()
        return dato

    def obtener(self, coleccion: str, clave: str | int) -> dict | None:
        row = self._a._db.execute("SELECT json FROM docs WHERE espacio = ? AND coleccion = ? AND clave = ?",
                                  (self.nombre, coleccion, str(clave))).fetchone()
        return json.loads(row["json"]) if row else None

    def actualizado(self, coleccion: str, clave: str | int) -> datetime | None:
        row = self._a._db.execute("SELECT actualizado FROM docs WHERE espacio = ? AND coleccion = ? AND clave = ?",
                                  (self.nombre, coleccion, str(clave))).fetchone()
        return datetime.fromisoformat(row["actualizado"]) if row else None

    def borrar(self, coleccion: str, clave: str | int) -> bool:
        with self._a._lock:
            n = self._a._db.execute("DELETE FROM docs WHERE espacio = ? AND coleccion = ? AND clave = ?",
                                    (self.nombre, coleccion, str(clave))).rowcount
            self._a._db.commit()
        return bool(n)

    def listar(self, coleccion: str, **filtros: Any) -> list[dict]:
        rows = self._a._db.execute("SELECT json FROM docs WHERE espacio = ? AND coleccion = ? ORDER BY rowid",
                                   (self.nombre, coleccion)).fetchall()
        out = [json.loads(r["json"]) for r in rows]
        return [d for d in out if all(d.get(k) == v for k, v in filtros.items())]

    def siguiente(self, coleccion: str) -> int:
        """Número correlativo (1, 2, 3…) para numerar encargos, turnos, pendientes."""
        with self._a._lock:
            self._a._db.execute(
                "INSERT INTO contadores VALUES (?, ?, 1) ON CONFLICT(espacio, coleccion) DO UPDATE SET valor = valor + 1",
                (self.nombre, coleccion))
            self._a._db.commit()
            row = self._a._db.execute("SELECT valor FROM contadores WHERE espacio = ? AND coleccion = ?",
                                      (self.nombre, coleccion)).fetchone()
        return int(row["valor"])
