"""Registro de modelo POR ESTACIÓN (capa A del console multi-agente).

Hoy todo el backend habla con UN modelo (`llm_client.client` + `settings.lmstudio_model`).
Esto permite que cada estación de la brigada tenga su PROPIO modelo/endpoint/API-key:
DeepSeek para el triage, GPT-OSS para la narrativa, etc. El harness resuelve, por
estación, qué cliente y modelo usar, con fallback al global.

Parte 1 (este módulo): el registro + la fábrica de clientes + serialización, todo
testeable en aislado. Parte 2 (enchufarlo en las 3 estaciones con LLM -- E3/E5/E6)
se hace y valida contra el backend en vivo.

Seguridad: la API key nunca se expone en la vista pública (`public()`), ni se escribe
al serializar salvo que se pida explícitamente (`include_secret=True`). El repo es
público: las keys van en env/almacén seguro, no commiteadas.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..config import settings

# Las estaciones que usan LLM (las únicas a las que tiene sentido asignarles modelo).
LLM_STATIONS = ("E3_triage", "E5_redaccion", "E6_catador")


@dataclass(frozen=True)
class StationModel:
    """Config de modelo de una estación. Compatible con cualquier endpoint estilo
    OpenAI (LM Studio, Ollama, OpenRouter, la nube que sea)."""

    model: str
    base_url: str
    api_key: str = "not-needed"
    timeout: float = 1800.0
    temperature: float | None = None

    def public(self) -> dict[str, Any]:
        """Vista para la UI: NUNCA expone la api_key, solo si está seteada."""
        return {
            "model": self.model,
            "base_url": self.base_url,
            "api_key_set": bool(self.api_key) and self.api_key != "not-needed",
            "timeout": self.timeout,
            "temperature": self.temperature,
        }

    def to_dict(self, include_secret: bool = False) -> dict[str, Any]:
        d: dict[str, Any] = {
            "model": self.model,
            "base_url": self.base_url,
            "timeout": self.timeout,
            "temperature": self.temperature,
        }
        if include_secret:
            d["api_key"] = self.api_key
        return d

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "StationModel":
        return StationModel(
            model=d["model"],
            base_url=d["base_url"],
            api_key=d.get("api_key", "not-needed"),
            timeout=float(d.get("timeout", 1800.0)),
            temperature=d.get("temperature"),
        )


def global_default() -> StationModel:
    """La config global de hoy (lo que usa `llm_client`), como default de todas las
    estaciones que no tengan uno propio asignado."""
    return StationModel(
        model=settings.lmstudio_model,
        base_url=settings.lmstudio_base_url,
        api_key=settings.llm_api_key,
        timeout=float(settings.llm_request_timeout_seconds),
    )


def _tier2_free_set() -> set[str]:
    """Los nombres de modelo declarados como tier-2 free (settings.tier2_free_models)."""
    return {m.strip() for m in str(settings.tier2_free_models).split(",") if m.strip()}


def endpoint_for_model(name: str, tier: int | None = None) -> StationModel:
    """Clasifica un nombre de modelo a su endpoint/key (2026-09-29). Los slugs de
    proveedor cloud (con "/": anthropic/..., deepseek/...) usan el endpoint/key
    GLOBAL del chat (hoy OpenRouter). Los nombres locales (jarvis-text-*, sin "/")
    usan el endpoint local de Ollama (`LOCAL_MODEL_BASE_URL`). Así el mismo mapa de
    tiers puede mezclar modelos cloud y locales sin que el caller sepa dónde vive
    cada uno.

    OmniRoute (2026-10-07, idea de Damian): si `TIER2_BASE_URL` está seteado y el
    modelo es uno de los tier-2 free, se enruta a ESE gateway (OmniRoute local en
    `http://localhost:20128/v1`) en vez de OpenRouter. OmniRoute es OpenAI-compatible,
    así que es solo otro base_url+key. Este chequeo va PRIMERO porque los slugs free
    tienen "/" y si no caerían a OpenRouter. La compuerta de privacidad sigue
    aplicando aguas arriba: lo personal nunca llega al tier 2.

    Override por tier (2026-10-11, pedido de Damian): si se pasa `tier` y ese tier tiene
    `TIER{n}_BASE_URL` y/o `TIER{n}_API_KEY` seteados en la config, se aplican ENCIMA del
    endpoint derivado (cada campo por separado: podés cambiar solo la key y dejar el
    endpoint derivado, o apuntar todo a otro proveedor). Vacío = sin cambios. Pensado para,
    por ej., mandar el tier 4 directo a la API de Anthropic con su propia key."""
    glob = global_default()
    tier2_url = str(settings.tier2_base_url).strip()
    if tier2_url and name in _tier2_free_set():  # tier-2 free vía gateway (OmniRoute)
        cfg = StationModel(
            model=name,
            base_url=tier2_url,
            api_key=str(settings.tier2_api_key) or "not-needed",
            timeout=glob.timeout,
        )
    elif "/" in name:  # slug cloud vía OpenRouter (o el proveedor global de turno)
        cfg = StationModel(model=name, base_url=glob.base_url, api_key=glob.api_key, timeout=glob.timeout)
    else:
        cfg = StationModel(
            model=name,
            base_url=settings.local_model_base_url,
            api_key=settings.local_model_api_key,
            timeout=glob.timeout,
        )
    if tier is not None:
        base = str(getattr(settings, f"tier{tier}_base_url", "") or "").strip()
        key = str(getattr(settings, f"tier{tier}_api_key", "") or "").strip()
        if key in ("not-needed", "lm-studio", "ollama"):  # placeholders, no es key real
            key = ""
        if base or key:
            cfg = StationModel(
                model=cfg.model,
                base_url=base or cfg.base_url,
                api_key=key or cfg.api_key,
                timeout=cfg.timeout,
                temperature=cfg.temperature,
            )
    return cfg


def build_client(cfg: StationModel, client_factory: Callable[..., Any] | None = None) -> Any:
    """Construye un cliente OpenAI-compatible para esta config (mismo mecanismo que
    `llm_client`: base_url + api_key + timeout, max_retries=0). `client_factory` es
    inyectable para testear sin construir el cliente real."""
    if client_factory is None:
        from openai import AsyncOpenAI

        client_factory = AsyncOpenAI
    return client_factory(
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        timeout=cfg.timeout,
        max_retries=0,
    )


def client_and_model_for_tier(tier: int, client_factory: Callable[..., Any] | None = None) -> tuple[Any, str]:
    """(cliente, modelo) para un TIER directo, sin pasar por una estación. Lo usan los
    jobs programados (ej. la consolidación/"sueño" -> tier 1 local). Resuelve el primer
    modelo del tier y le arma el endpoint correcto; si el tier no define modelo, cae al
    default global."""
    from . import routing

    name = routing.resolve_model(tier)
    # Tier efectivo (modo prueba puede bajar 3/4 -> 2): así el override de endpoint por tier
    # coincide con el modelo resuelto y en prueba NO se usa la API paga del tier 4.
    eff = routing.effective_tier(tier)
    cfg = endpoint_for_model(name, tier=eff) if name else global_default()
    return build_client(cfg, client_factory), cfg.model


class ModelRegistry:
    """Mapa estación -> StationModel, con fallback al default global. Cachea el
    cliente por (base_url, api_key, timeout) para no reconstruirlo en cada corrida."""

    def __init__(self, default: StationModel | None = None) -> None:
        self._default = default or global_default()
        self._by_station: dict[str, StationModel] = {}
        self._client_cache: dict[tuple[str, str, float], Any] = {}

    @property
    def default(self) -> StationModel:
        return self._default

    def set_default(self, cfg: StationModel) -> None:
        self._default = cfg
        self._client_cache.clear()
        self._autosave()

    def set(self, station: str, cfg: StationModel) -> None:
        self._by_station[station] = cfg
        self._client_cache.clear()
        self._autosave()

    def unset(self, station: str) -> None:
        """Vuelve la estación al default global."""
        self._by_station.pop(station, None)
        self._client_cache.clear()
        self._autosave()

    def for_station(self, station: str) -> StationModel:
        return self._by_station.get(station, self._default)

    def overrides(self) -> dict[str, StationModel]:
        return dict(self._by_station)

    def _build_cached(self, cfg: StationModel, client_factory: Callable[..., Any] | None = None) -> Any:
        key = (cfg.base_url, cfg.api_key, cfg.timeout)
        if key not in self._client_cache:
            self._client_cache[key] = build_client(cfg, client_factory)
        return self._client_cache[key]

    def client_for(
        self, station: str, client_factory: Callable[..., Any] | None = None
    ) -> tuple[Any, str]:
        """Devuelve (cliente, nombre_de_modelo) para la estación. Cacheado."""
        cfg = self.for_station(station)
        return self._build_cached(cfg, client_factory), cfg.model

    def candidates_for(
        self, station: str, tier: int, client_factory: Callable[..., Any] | None = None
    ) -> list[tuple[Any, str]]:
        """Lista ORDENADA de (cliente, modelo) a probar para esta estación, para el
        fallback en cascada (reconciliación registro-explícito + tier, 2026-09-29):
          1. el PRIMARIO — el override explícito de la estación, o el default global;
          2. los FALLBACKS del tier (routing.DEFAULT_TIER_MODELS), resueltos a su
             endpoint por `endpoint_for_model`.
        Deduplicado por (base_url, modelo). El caller prueba en orden: si el
        primero falla (proveedor caído, etc.), pasa al siguiente."""
        from . import routing

        seen: set[tuple[str, str]] = set()
        out: list[tuple[Any, str]] = []

        def _add(cfg: StationModel) -> None:
            k = (cfg.base_url, cfg.model)
            if k not in seen:
                seen.add(k)
                out.append((self._build_cached(cfg, client_factory), cfg.model))

        # 1. override EXPLÍCITO de la estación (si Damian la asignó a mano) = primario.
        if station in self._by_station:
            _add(self._by_station[station])
        # 2. modelos del TIER (primario del tier + fallbacks). Si NO hubo override,
        #    el primero del tier es el primario -> un tier-1 usa el barato, no el
        #    global caro. Si hubo override, estos son solo el fallback.
        for name in routing.DEFAULT_TIER_MODELS.get(tier, []):
            _add(endpoint_for_model(name))
        # 3. red de seguridad: si el tier no define modelos (o quedó vacío) y no hubo
        #    override, cae al default global (así una estación LLM nunca queda sin cliente).
        if not out:
            _add(self._default)
        return out

    def snapshot(self, include_secret: bool = False) -> dict[str, Any]:
        """Estado completo para la UI/persistencia. Sin secretos por default."""
        return {
            "default": self._default.to_dict(include_secret),
            "stations": {
                name: cfg.to_dict(include_secret) for name, cfg in self._by_station.items()
            },
            "llm_stations": list(LLM_STATIONS),
        }

    def load(self, data: dict[str, Any]) -> None:
        """Carga desde un snapshot (ej. persistido en disco o mandado por la UI).

        Backfill de api_key (2026-09-29): el snapshot en disco NO guarda keys (el
        repo es público). Al cargar, si una estación usa el MISMO base_url que el
        default global, hereda su api_key (mismo proveedor = misma key). Si usa
        otro endpoint sin key, queda 'not-needed' y fallará claro hasta que se
        re-setee desde la consola (a propósito: mejor fallar visible que en claro)."""
        glob = global_default()

        def _backfill(cfg: StationModel) -> StationModel:
            if (not cfg.api_key or cfg.api_key == "not-needed") and cfg.base_url == glob.base_url:
                return StationModel(model=cfg.model, base_url=cfg.base_url, api_key=glob.api_key,
                                    timeout=cfg.timeout, temperature=cfg.temperature)
            return cfg

        if data.get("default"):
            self._default = _backfill(StationModel.from_dict(data["default"]))
        for name, d in (data.get("stations") or {}).items():
            self._by_station[name] = _backfill(StationModel.from_dict(d))
        self._client_cache.clear()

    # --- persistencia a disco (2026-09-29) ---
    def _autosave(self) -> None:
        """Guarda el estado a disco SIN secretos. Best-effort: nunca rompe un set."""
        try:
            import json
            from pathlib import Path

            from ..config import settings
            p = Path(settings.model_registry_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(self.snapshot(include_secret=False), ensure_ascii=False, indent=2),
                         encoding="utf-8")
        except Exception:  # noqa: BLE001 -- persistencia best-effort
            pass

    def load_from_disk(self) -> bool:
        """Carga los overrides persistidos, si existen. Best-effort. Devuelve si cargó."""
        try:
            import json
            from pathlib import Path

            from ..config import settings
            p = Path(settings.model_registry_path)
            if not p.is_file():
                return False
            self.load(json.loads(p.read_text(encoding="utf-8")))
            return True
        except Exception:  # noqa: BLE001
            return False


# Singleton del proceso: la UI y el harness leen/escriben acá. Arranca con todas
# las estaciones en el modelo global; se reconfigura por estación en runtime.
registry = ModelRegistry()
# Recarga los overrides persistidos al importar el módulo (arranque del backend).
registry.load_from_disk()
