"""Almacén: una base SQLite por instalación, con un ESPACIO por brigada (y subespacios por cocinero).

Cada espacio guarda documentos JSON por colección y clave, y no ve los de los otros. No hay esquemas
compartidos: una brigada cambia cómo guarda sus datos sin migrar nada ajeno. Al desmontar una brigada
su espacio se exporta y se purga. Los espacios que empiezan con "_" son del harness.

Portado de `raphael_harness.almacen` (Empresas 0.4) con exportar, purgar y todas las lecturas bajo lock.
"""

from __future__ import annotations

import json
import re
import sqlite3
import threading
from collections.abc import Callable
from datetime import datetime
from typing import Any

_SPACE = re.compile(r"^_?[a-z][a-z0-9-]{0,39}(/[a-z][a-z0-9-]{0,39})?$")
_COLLECTION = re.compile(r"^[a-z_][a-z0-9_-]{0,59}$")


class LegacyDatabaseError(RuntimeError):
    """La base es de raphael-harness 0.4 (columnas en castellano). No se abre ni se migra sola."""


class Store:
    def __init__(self, path: str = ":memory:", clock: Callable[[], datetime] | None = None) -> None:
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._clock = clock or datetime.now
        cols = {r[1] for r in self._db.execute("PRAGMA table_info(docs)").fetchall()}
        if "espacio" in cols:
            self._db.close()
            raise LegacyDatabaseError(
                f"{path} es una base de Raphael Empresas 0.4 (columnas espacio/coleccion/clave). El v2 no la abre ni "
                "la migra solo: migrarla no tiene vuelta atrás y tiene que aprobarla una persona (fase 3).")
        with self._lock:
            if path != ":memory:":
                self._db.execute("PRAGMA journal_mode=WAL")
            self._db.executescript(
                "CREATE TABLE IF NOT EXISTS docs (space TEXT, collection TEXT, key TEXT, json TEXT, updated TEXT,"
                " PRIMARY KEY (space, collection, key));"
                "CREATE TABLE IF NOT EXISTS counters (space TEXT, collection TEXT, value INTEGER,"
                " PRIMARY KEY (space, collection));")
            self._db.commit()

    def space(self, name: str) -> Space:
        if not _SPACE.match(name):
            raise ValueError(f"nombre de espacio inválido: {name!r}")
        return Space(self, name)

    def spaces(self) -> list[str]:
        with self._lock:
            rows = self._db.execute("SELECT DISTINCT space FROM docs UNION SELECT DISTINCT space FROM counters").fetchall()
        return sorted(r[0] for r in rows)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # --- uso interno de Space
    def _query(self, sql: str, args: tuple) -> list[sqlite3.Row]:
        with self._lock:
            return self._db.execute(sql, args).fetchall()

    def _write(self, sql: str, args: tuple) -> int:
        with self._lock:
            n = self._db.execute(sql, args).rowcount
            self._db.commit()
            return n


def _check_collection(name: str) -> str:
    if not _COLLECTION.match(name):
        raise ValueError(f"nombre de colección inválido: {name!r}")
    return name


class Space:
    """Los datos de UNA brigada (o de un cocinero, con nombre 'brigada/cocinero')."""

    def __init__(self, store: Store, name: str) -> None:
        self._s = store
        self.name = name

    def _prefix_clause(self) -> tuple[str, tuple]:
        """Este espacio y sus subespacios (para exportar y purgar una brigada entera)."""
        # "_" es comodín en LIKE: se escapa para que "_harness" no matchee "xharness/…"
        return "(space = ? OR space LIKE ? ESCAPE '\\')", (self.name, self.name.replace("_", "\\_") + "/%")

    def put(self, collection: str, key: str | int, doc: dict) -> dict:
        self._s._write(
            "INSERT INTO docs VALUES (?, ?, ?, ?, ?) ON CONFLICT(space, collection, key) DO UPDATE SET"
            " json = excluded.json, updated = excluded.updated",
            (self.name, _check_collection(collection), str(key), json.dumps(doc, ensure_ascii=False),
             self._s._clock().isoformat()))
        return doc

    def get(self, collection: str, key: str | int) -> dict | None:
        rows = self._s._query("SELECT json FROM docs WHERE space = ? AND collection = ? AND key = ?",
                              (self.name, collection, str(key)))
        return json.loads(rows[0]["json"]) if rows else None

    def updated(self, collection: str, key: str | int) -> datetime | None:
        rows = self._s._query("SELECT updated FROM docs WHERE space = ? AND collection = ? AND key = ?",
                              (self.name, collection, str(key)))
        return datetime.fromisoformat(rows[0]["updated"]) if rows else None

    def delete(self, collection: str, key: str | int) -> bool:
        return bool(self._s._write("DELETE FROM docs WHERE space = ? AND collection = ? AND key = ?",
                                   (self.name, collection, str(key))))

    def list(self, collection: str, **filters: Any) -> list[dict]:
        rows = self._s._query("SELECT json FROM docs WHERE space = ? AND collection = ? ORDER BY rowid",
                              (self.name, collection))
        out = [json.loads(r["json"]) for r in rows]
        return [d for d in out if all(d.get(k) == v for k, v in filters.items())]

    def next(self, collection: str) -> int:
        """Número correlativo (1, 2, 3…) para numerar encargos, turnos, pendientes."""
        with self._s._lock:
            self._s._db.execute(
                "INSERT INTO counters VALUES (?, ?, 1) ON CONFLICT(space, collection) DO UPDATE SET value = value + 1",
                (self.name, _check_collection(collection)))
            self._s._db.commit()
            row = self._s._db.execute("SELECT value FROM counters WHERE space = ? AND collection = ?",
                                      (self.name, collection)).fetchone()
        return int(row["value"])

    def collections(self) -> list[str]:
        rows = self._s._query("SELECT DISTINCT collection FROM docs WHERE space = ? ORDER BY collection", (self.name,))
        return [r[0] for r in rows]

    # --- desmontaje
    def export(self, collections: tuple[str, ...] | list[str] | None = None) -> dict:
        """{espacio: {colección: {clave: doc}}}, con subespacios. None = todas las colecciones."""
        where, args = self._prefix_clause()
        rows = self._s._query(f"SELECT space, collection, key, json FROM docs WHERE {where} ORDER BY rowid", args)
        out: dict[str, dict[str, dict]] = {}
        for r in rows:
            if collections is not None and r["collection"] not in collections:
                continue
            out.setdefault(r["space"], {}).setdefault(r["collection"], {})[r["key"]] = json.loads(r["json"])
        return out

    def purge(self, collections: tuple[str, ...] | list[str] | None = None) -> int:
        """Borra colecciones (o todo, con subespacios y contadores). Devuelve cuántos documentos borró."""
        where, args = self._prefix_clause()
        if collections is None or "*" in collections:
            n = self._s._write(f"DELETE FROM docs WHERE {where}", args)
            self._s._write(f"DELETE FROM counters WHERE {where}", args)
            return n
        n = 0
        for c in collections:
            n += self._s._write(f"DELETE FROM docs WHERE {where} AND collection = ?", (*args, c))
            self._s._write(f"DELETE FROM counters WHERE {where} AND collection = ?", (*args, c))
        return n
