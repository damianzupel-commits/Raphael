"""Capa de modelos: elige la IA por rol y por plan, mide el consumo y nunca rompe la atención.

Si no hay modelo configurado, falla, o el cliente pasó su tope, `completar` devuelve None y la
brigada sigue con sus reglas. Habla con cualquier endpoint OpenAI-compatible (/chat/completions).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

import yaml

from .uso import Uso

CONFIG_POR_DEFECTO = Path(__file__).with_name("modelos.yaml")


def cargar_config(ruta: str | Path | None = None) -> dict:
    return yaml.safe_load(Path(ruta or CONFIG_POR_DEFECTO).read_text(encoding="utf-8")) or {}


class Modelos:
    def __init__(self, config: dict, plan: str, uso: Uso, *, env: dict[str, str] | None = None,
                 transporte: Callable[[str, dict, dict], dict] | None = None, timeout: float = 30.0) -> None:
        self._config = config
        self._plan = plan
        self._uso = uso
        self._env = env if env is not None else dict(os.environ)
        self._transporte = transporte or self._http
        self._timeout = timeout

    def proveedor(self, rol: str) -> dict | None:
        nombre = (self._config.get("planes", {}).get(self._plan) or {}).get(rol)
        p = self._config.get("proveedores", {}).get(nombre) if nombre else None
        if not p or not p.get("base_url") or not p.get("model"):
            return None
        if not p.get("api_key") and p.get("api_key_env") and not self._env.get(p["api_key_env"]):
            return None
        return {**p, "nombre": nombre}

    def disponible(self, rol: str) -> bool:
        return self.proveedor(rol) is not None and not self._uso.excedido()

    def completar(self, rol: str, mensajes: list[dict], *, max_tokens: int = 300, temperatura: float = 0.2) -> str | None:
        if self._uso.excedido():
            return None
        p = self.proveedor(rol)
        if p is None:
            return None
        headers = {"Content-Type": "application/json"}
        clave = p.get("api_key") or (self._env.get(p["api_key_env"]) if p.get("api_key_env") else None)
        if clave:
            headers["Authorization"] = f"Bearer {clave}"
        cuerpo = {"model": p["model"], "messages": mensajes, "max_tokens": max_tokens, "temperature": temperatura}
        try:
            data = self._transporte(f"{p['base_url'].rstrip('/')}/chat/completions", cuerpo, headers)
            texto = (data["choices"][0]["message"]["content"] or "").strip()
            u = data.get("usage") or {}
            tin, tout = int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0))
            costo = tin / 1e6 * float(p.get("usd_por_millon_in", 0)) + tout / 1e6 * float(p.get("usd_por_millon_out", 0))
            self._uso.registrar_ia(rol, p["model"], tin, tout, costo, True)
            return texto or None
        except Exception:  # noqa: BLE001 - cualquier falla de la IA cae a reglas
            self._uso.registrar_ia(rol, p["model"], 0, 0, 0.0, False)
            return None

    def _http(self, url: str, cuerpo: dict, headers: dict) -> dict[str, Any]:
        import httpx

        r = httpx.post(url, json=cuerpo, headers=headers, timeout=self._timeout)
        r.raise_for_status()
        return r.json()
