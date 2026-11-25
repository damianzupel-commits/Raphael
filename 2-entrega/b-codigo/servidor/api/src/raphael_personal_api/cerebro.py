"""Cerebro mixto: modelos por rol configurables, estado del modelo local y avisos si se apaga.

Regla de Damián (25 nov 2026): lo sensible corre en local (Ollama o LM Studio en la PC); el resto, en la nube (NVIDIA). Si
el modelo local no está prendido, se avisa y lo sensible NO se manda a la nube. Esa garantía la da la pasarela del harness
(`ModelGateway`: un pedido privado solo admite proveedores de localhost); acá se arma la config, se mira si el local
responde y se avisa cuando cambia. Los avisos nunca llevan texto de pedidos, solo nombres de brigadas.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from pathlib import Path
from urllib.parse import urlparse

import yaml
from raphael_core.models import ModelsConfig, models_from
from raphael_core.models.config import LOOPBACK

DEFAULT_YAML = Path(__file__).resolve().parents[5] / "c-despliegue" / "personal" / "modelos.personal.yaml"
ROLES = ("mando", "voz", "jefe", "ruteo", "cocinero", "efimero")
LOCAL_ENV = {"ollama": ("OLLAMA_URL", "OLLAMA_MODEL"), "lmstudio": ("LMSTUDIO_URL", "LMSTUDIO_MODEL")}
_ID = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")

Fetch = Callable[[str], dict]   # GET json con timeout corto


def load(path: str | Path | None = None, environ: Mapping[str, str] | None = None) -> ModelsConfig:
    """`modelos.personal.yaml` más lo que pida el entorno (modelos locales, roles, brigadas privadas)."""
    env = environ or {}
    data = yaml.safe_load(Path(path or DEFAULT_YAML).read_text(encoding="utf-8")) or {}
    for name, (url_var, model_var) in LOCAL_ENV.items():
        spec = data.get("providers", {}).get(name)
        if spec is None:
            continue
        if env.get(url_var):
            spec["base_url"] = env[url_var]
        if env.get(model_var):
            spec["model"] = env[model_var]
    if env.get("LOCAL_LLM_URL"):        # el nombre que usa la pieza de Cuentas y APIs: una sola dirección y de qué programa es
        kind = (env.get("LOCAL_LLM_KIND") or "ollama").lower()
        spec = data.get("providers", {}).get(kind if kind in LOCAL_ENV else "ollama")
        url_var = LOCAL_ENV.get(kind, LOCAL_ENV["ollama"])[0]
        if spec is not None and not env.get(url_var):
            base = env["LOCAL_LLM_URL"].rstrip("/")
            spec["base_url"] = base if base.endswith("/v1") else base + "/v1"
    tiers = data.get("tiers", {})
    for role in ROLES:
        raw = env.get(f"RAPHAEL_ROL_{role.upper()}", "")
        if raw.strip():
            chain = [t.strip() for t in raw.split(",") if t.strip()]
            bad = [t for t in chain if t not in tiers]
            if bad:
                raise ValueError(f"RAPHAEL_ROL_{role.upper()}: escalón inexistente {bad} (hay: {sorted(tiers)})")
            data.setdefault("roles", {})[role] = chain
    extra = [b.strip() for b in env.get("RAPHAEL_PRIVADAS", "").split(",") if b.strip()]
    if any(not _ID.match(b) for b in extra):
        raise ValueError("RAPHAEL_PRIVADAS: ids de brigada en minúsculas, separados por comas")
    data["private"] = sorted({*data.get("private", []), *extra})
    if env.get("RAPHAEL_TOPE_PAGO_USD", "").strip():      # gastar es decisión de Damián: sin esto el tope queda en 0
        data["paid_cap_usd_month"] = parse_cap(env["RAPHAEL_TOPE_PAGO_USD"])
    cfg = models_from(data)
    for name in ("ollama", "lmstudio"):   # lo privado depende de que "local" sea de verdad local
        spec = cfg.providers.get(name)
        if spec is not None and (urlparse(spec.base_url).hostname or "") not in LOOPBACK:
            raise ValueError(f"{name}: el modelo local tiene que estar en localhost (no en {urlparse(spec.base_url).hostname})")
    return cfg


def parse_cap(value: str) -> float:
    try:
        cap = float(value.strip().replace(",", "."))
    except ValueError:
        cap = -1.0
    if not 0 <= cap <= 1000:
        raise ValueError("el tope de gasto es un número de dólares por mes, de 0 a 1000")
    return cap


def check_field(name: str, value: str) -> str:
    """Validación de los campos de Configuración propios del cerebro (ValueError en español)."""
    if name == "LOCAL_LLM_KIND" and value.lower() not in LOCAL_ENV:
        raise ValueError("es ollama o lmstudio")
    if name in {*(u for u, _ in LOCAL_ENV.values()), "LOCAL_LLM_URL"}:
        p = urlparse(value)
        if p.scheme not in ("http", "https") or (p.hostname or "") not in LOOPBACK:
            raise ValueError("la dirección del modelo local es de esta PC: http://localhost:<puerto>/v1")
        return value
    if name == "RAPHAEL_TOPE_PAGO_USD":
        return f"{parse_cap(value):g}"
    if name.startswith("RAPHAEL_ROL_"):
        chain = [t.strip() for t in value.split(",") if t.strip()]
        if not chain or any(t not in ("local", "gratis", "pago") for t in chain):
            raise ValueError("escalones separados por coma: local, gratis, pago (en el orden que quieras)")
        return ",".join(chain)
    if name == "RAPHAEL_PRIVADAS":
        ids = [b.strip() for b in value.split(",") if b.strip()]
        if not ids or any(not _ID.match(b) for b in ids):
            raise ValueError("ids de brigada en minúsculas separados por comas, ej. trading,legales")
        return ",".join(ids)
    return value


def http_get(url: str) -> dict:
    import httpx

    r = httpx.get(url, timeout=2.0)
    r.raise_for_status()
    return r.json()


def model_present(provider: str, model: str, ids: list[str]) -> bool:
    """¿Está el modelo pedido? En Ollama el nombre sin etiqueta (`llama3.1`) vale por `llama3.1:latest`. En LM Studio los
    identificadores los pone el programa: con cualquier modelo cargado se atiende (se usa el que esté cargado)."""
    if model in ids:
        return True
    if provider == "lmstudio":
        return bool(ids)
    return ":" not in model and f"{model}:latest" in ids


def probe_local(cfg: ModelsConfig, fetch: Fetch = http_get) -> list[dict]:
    """Qué modelos locales responden. Ollama y LM Studio hablan `GET <base>/models` (formato OpenAI)."""
    out = []
    for name in cfg.tiers.get("local", []):
        spec = cfg.providers[name]
        row = {"provider": name, "url": spec.base_url, "model": spec.model, "up": False, "model_ready": False,
               "available": []}
        try:
            body = fetch(spec.base_url.rstrip("/") + "/models")
            ids = [m.get("id", "") for m in (body.get("data") or [])] or [m.get("name", "") for m in (body.get("models") or [])]
            row["up"] = True
            row["available"] = [i for i in ids if i][:20]
            row["model_ready"] = model_present(name, spec.model, ids)
        except Exception as exc:  # noqa: BLE001 - apagado, sin red, respuesta rara: es "no responde", no un error
            row["error"] = type(exc).__name__
        out.append(row)
    return out


def local_ready(probe: list[dict]) -> bool:
    return any(p["up"] and p["model_ready"] for p in probe)


def live_label(gateway, role: str, probe: list[dict]) -> str:
    """Qué modelo atendería ahora ese rol de verdad: un proveedor local que no responde (o sin su modelo) no cuenta.
    Sin ninguno disponible dice «sin modelo (reglas)»; nunca muestra un modelo que no está prendido."""
    if gateway is None:
        return ""
    up = {p["provider"] for p in probe if p["up"] and p["model_ready"]}
    for c in gateway.candidates(role):
        if c.spec.is_local and c.name not in up:
            continue
        return f"{c.name}: {c.spec.model}"
    return "sin modelo (reglas)"


def status(cfg: ModelsConfig, probe: list[dict], gateway=None) -> dict:
    """Lo que ve el cliente: qué usa cada rol, qué brigadas son privadas y qué pasa con ellas ahora."""
    ready = local_ready(probe)
    roles = {}
    for role in ROLES:
        chain = cfg.roles.get(role, [])
        roles[role] = {"tiers": chain, "now": live_label(gateway, role, probe)}
    hints = []
    for p in probe:
        if not p["up"]:
            hints.append(f"{p['provider']} no responde en {p['url']}: abrilo (Ollama o LM Studio).")
        elif not p["model_ready"]:
            how = f"bajalo con `ollama pull {p['model']}`." if p["provider"] == "ollama" else "cargalo en LM Studio."
            hints.append(f"{p['provider']} está prendido pero no tiene el modelo «{p['model']}»: {how}")
    return {"local": {"ready": ready, "providers": probe, "hints": [] if ready else hints},
            "private": list(cfg.private), "private_mode": "local" if ready else "reglas",
            "roles": roles,
            "paid_cap_usd_month": cfg.paid_cap_usd_month}


def private_warning(cfg: ModelsConfig) -> str:
    return ("El modelo local no está prendido. " + ", ".join(cfg.private[:4]).capitalize() + " y las demás privadas siguen por "
            "reglas y no mando nada sensible a la nube. Abrí Ollama o LM Studio y sigo.")


class LocalWatch:
    """Avisa (una vez por cambio) cuando el modelo local se apaga o vuelve. `notify(texto, **datos)` es `rt.notify`."""

    def __init__(self, notify: Callable[..., object], cfg: ModelsConfig, fetch: Fetch = http_get) -> None:
        self.notify, self.cfg, self.fetch = notify, cfg, fetch
        self.last: bool | None = None

    def check(self) -> dict:
        probe = probe_local(self.cfg, self.fetch)
        ready = local_ready(probe)
        if ready != self.last:
            if not ready:
                self.notify(private_warning(self.cfg), kind="modelo_local_apagado")
            elif self.last is False:
                self.notify("El modelo local volvió: las brigadas privadas vuelven a usarlo.", kind="modelo_local_ok")
            self.last = ready
        return {"ready": ready, "probe": probe}
