"""Almacén v1 (`Almacen`, `Espacio` con métodos en castellano) sobre el `Store` del v2."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from ...store import Space, Store


class Espacio:
    def __init__(self, space: Space) -> None:
        self._s = space
        self.nombre = space.name

    def guardar(self, coleccion: str, clave: str | int, dato: dict) -> dict:
        return self._s.put(coleccion, clave, dato)

    def obtener(self, coleccion: str, clave: str | int) -> dict | None:
        return self._s.get(coleccion, clave)

    def actualizado(self, coleccion: str, clave: str | int) -> datetime | None:
        return self._s.updated(coleccion, clave)

    def borrar(self, coleccion: str, clave: str | int) -> bool:
        return self._s.delete(coleccion, clave)

    def listar(self, coleccion: str, **filtros: Any) -> list[dict]:
        return self._s.list(coleccion, **filtros)

    def siguiente(self, coleccion: str) -> int:
        return self._s.next(coleccion)


class Almacen:
    def __init__(self, ruta: str = ":memory:", reloj: Callable[[], datetime] | None = None) -> None:
        self.store = Store(ruta, clock=reloj)

    def espacio(self, nombre: str) -> Espacio:
        return Espacio(self.store.space(nombre))

    def cerrar(self) -> None:
        self.store.close()
