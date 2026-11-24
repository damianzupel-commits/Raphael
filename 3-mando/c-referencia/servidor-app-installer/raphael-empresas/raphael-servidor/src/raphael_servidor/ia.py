"""La IA del cliente: un solo proveedor (NVIDIA, Ollama, LM Studio u otro compatible con OpenAI) que atiende todos los roles.

Se guarda en `datos/ia.json`. La clave no sale nunca del equipo y la API jamás la devuelve (solo si hay una cargada).
Sin esta configuración, Raphael funciona igual con sus reglas.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

ROLES = ("intencion", "redaccion", "resumen", "secretaria")
PLANES = ("basico", "pro", "privado", "premium")

PRESETS = [
    {"id": "nvidia", "titulo": "NVIDIA (en la nube)", "base_url": "https://integrate.api.nvidia.com/v1", "model": "meta/llama-3.3-70b-instruct",
     "clave": True, "ayuda": "Sacá la clave gratis en build.nvidia.com (empieza con nvapi-)."},
    {"id": "ollama", "titulo": "Ollama (en esta PC)", "base_url": "http://localhost:11434/v1", "model": "llama3.1",
     "clave": False, "ayuda": "No necesita clave. Tené Ollama abierto y el modelo descargado (ollama pull llama3.1)."},
    {"id": "lmstudio", "titulo": "LM Studio (en esta PC)", "base_url": "http://localhost:1234/v1", "model": "",
     "clave": False, "ayuda": "No necesita clave. Cargá un modelo y activá el servidor local en LM Studio."},
    {"id": "otro", "titulo": "Otro (compatible con OpenAI)", "base_url": "", "model": "",
     "clave": True, "ayuda": "Cualquier servicio con la API de OpenAI: dirección, modelo y clave."},
]


def archivo(dir_: Path) -> Path:
    return dir_ / "ia.json"


def leer(dir_: Path) -> dict | None:
    try:
        d = json.loads(archivo(dir_).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and d.get("base_url") and d.get("model") is not None else None


def guardar(dir_: Path, d: dict) -> None:
    dir_.mkdir(parents=True, exist_ok=True)
    archivo(dir_).write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")


def quitar(dir_: Path) -> None:
    try:
        archivo(dir_).unlink()
    except OSError:
        pass


def publica(d: dict | None) -> dict:
    """Lo que se le muestra al panel: nunca la clave."""
    if not d:
        return {"configurada": False, "proveedor": "", "base_url": "", "model": "", "tiene_clave": False}
    return {"configurada": True, "proveedor": d.get("proveedor", "otro"), "base_url": d["base_url"], "model": d.get("model", ""),
            "tiene_clave": bool(d.get("api_key"))}


def config_modelos(base: dict, d: dict | None) -> dict | None:
    """El modelos.yaml del producto con TODOS los roles de TODOS los planes apuntando al proveedor del cliente. Sin IA cargada: None (queda lo de fábrica)."""
    if not d:
        return None
    nombre = d.get("proveedor") or "cliente"
    prov = {"base_url": d["base_url"], "model": d.get("model", ""), "api_key": d.get("api_key", ""), "api_key_env": "",
            "usd_por_millon_in": 0.0, "usd_por_millon_out": 0.0}
    cfg = dict(base)
    cfg["proveedores"] = {**(base.get("proveedores") or {}), nombre: prov}
    cfg["planes"] = {plan: {rol: nombre for rol in ROLES} for plan in PLANES}
    return cfg


def _http(url: str, cuerpo: dict, headers: dict) -> dict[str, Any]:
    import httpx
    r = httpx.post(url, json=cuerpo, headers=headers, timeout=25.0)
    r.raise_for_status()
    return r.json()


def probar(d: dict, transporte: Callable[[str, dict, dict], dict] | None = None) -> dict:
    """Le hace una pregunta mínima al modelo y devuelve {'ok': bool, 'respuesta'|'error': str}, con el error en criollo."""
    if not d.get("base_url"):
        return {"ok": False, "error": "Falta la dirección del servicio."}
    if not d.get("model"):
        return {"ok": False, "error": "Falta el nombre del modelo."}
    headers = {"Content-Type": "application/json"}
    if d.get("api_key"):
        headers["Authorization"] = f"Bearer {d['api_key']}"
    cuerpo = {"model": d["model"], "max_tokens": 40, "temperature": 0,
              "messages": [{"role": "user", "content": "Respondé solo con la palabra: listo"}]}
    try:
        data = (transporte or _http)(f"{d['base_url'].rstrip('/')}/chat/completions", cuerpo, headers)
        texto = (data["choices"][0]["message"]["content"] or "").strip()
        return {"ok": True, "respuesta": texto[:120] or "(sin texto)"}
    except Exception as e:  # noqa: BLE001 - se traduce a un mensaje entendible
        return {"ok": False, "error": _explicar(e, d)}


def _explicar(e: Exception, d: dict) -> str:
    estado = getattr(getattr(e, "response", None), "status_code", None)
    if estado in (401, 403):
        return "El servicio rechazó la clave. Revisá que esté bien copiada."
    if estado == 404:
        return "No encontré ese modelo o esa dirección. Revisá el nombre del modelo y que la dirección termine en /v1."
    if estado == 429:
        return "El servicio dice que hiciste demasiados pedidos o no tenés cupo. Probá en un rato."
    if estado:
        return f"El servicio contestó con error {estado}."
    txt = type(e).__name__
    if "Connect" in txt or "Timeout" in txt:
        local = "localhost" in d["base_url"] or "127.0.0.1" in d["base_url"]
        return ("No me pude conectar. ¿Está abierto " + ("Ollama / LM Studio en esta PC?" if local else "el servicio y tenés internet?"))
    return "No pude hablar con la IA: " + str(e)[:120]
