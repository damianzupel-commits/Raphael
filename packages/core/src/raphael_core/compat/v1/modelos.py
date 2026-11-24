"""Configuración de modelos v1 (`planes` -> rol -> proveedor) traducida al formato v2 de escalones.

Cada proveedor v1 se vuelve un escalón propio ("v1:<nombre>") y cada rol del plan apunta a ese escalón.
Los nombres de rol de v1 (intencion, redaccion, resumen, secretaria) se usan tal cual: no se traducen.
"""

from __future__ import annotations

from ...models import ModelsConfig, models_from


def desde_v1(config: dict) -> ModelsConfig:
    if not config:
        return models_from({"aliases": {}})
    if "tiers" in config or "providers" in config:      # ya viene en formato v2
        return models_from(config)
    providers, tiers = {}, {}
    for nombre, p in (config.get("proveedores") or {}).items():
        providers[nombre] = {"base_url": p.get("base_url", ""), "model": p.get("model", ""),
                             "api_key_env": p.get("api_key_env", "") or "", "api_key": p.get("api_key", "") or "",
                             "usd_per_million_in": float(p.get("usd_por_millon_in", 0) or 0),
                             "usd_per_million_out": float(p.get("usd_por_millon_out", 0) or 0)}
        tiers[f"v1:{nombre}"] = [nombre]
    plans = {plan: {rol: [f"v1:{prov}"] for rol, prov in (roles or {}).items() if prov in providers}
             for plan, roles in (config.get("planes") or {}).items()}
    return models_from({"providers": providers, "tiers": tiers, "plans": plans, "aliases": {}, "paid_tiers": []})


def cargar_config(ruta: str | None = None) -> dict:
    """Como en v1: lee un YAML de modelos (formato v1 o v2) y lo devuelve como dict."""
    from pathlib import Path

    import yaml

    from ...models.config import DEFAULT_PATH

    return yaml.safe_load(Path(ruta or DEFAULT_PATH).read_text(encoding="utf-8")) or {}
