"""Registro de uso: mensajes recibidos y llamadas a la IA, por mes. Base del cobro y del tope por plan."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from .almacen import Espacio


class Uso:
    def __init__(self, espacio: Espacio, limite_mensajes: int, reloj: Callable[[], datetime]) -> None:
        self._e = espacio
        self._limite = limite_mensajes
        self._reloj = reloj

    def _mes(self) -> str:
        return self._reloj().strftime("%Y-%m")

    def _doc(self, mes: str | None = None) -> dict:
        mes = mes or self._mes()
        return self._e.obtener("meses", mes) or {"mes": mes, "mensajes": 0, "ia": {}, "tokens_in": 0, "tokens_out": 0,
                                                  "costo_usd": 0.0, "fallas_ia": 0}

    def registrar_mensaje(self) -> None:
        d = self._doc()
        d["mensajes"] += 1
        self._e.guardar("meses", d["mes"], d)

    def registrar_ia(self, rol: str, modelo: str, tokens_in: int, tokens_out: int, costo_usd: float, ok: bool) -> None:
        d = self._doc()
        clave = f"{rol}:{modelo}"
        d["ia"][clave] = d["ia"].get(clave, 0) + 1
        d["tokens_in"] += tokens_in
        d["tokens_out"] += tokens_out
        d["costo_usd"] = round(d["costo_usd"] + costo_usd, 6)
        if not ok:
            d["fallas_ia"] += 1
        self._e.guardar("meses", d["mes"], d)

    def excedido(self) -> bool:
        return self._doc()["mensajes"] > self._limite

    def resumen(self, mes: str | None = None) -> dict:
        d = self._doc(mes)
        return {**d, "limite_mensajes": self._limite, "excedido": d["mensajes"] > self._limite}
