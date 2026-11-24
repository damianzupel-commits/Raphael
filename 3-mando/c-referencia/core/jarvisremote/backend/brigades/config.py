"""Config del modelo de los jefes de brigada.

Decisión 2026-11-03 (Damian): los jefes corren por ahora con **el modelo que
tengamos disponible** (hoy Groq free, `gpt-oss-120b`), y se pasan a **tier 3
(Sonnet)** cuando haya API. Esto es el ÚNICO punto de cambio: el día que esté la
key de Sonnet, se reemplaza el cuerpo de `load_chief_client_model` por
`model_registry.client_and_model_for_tier(3)` y todos los jefes quedan en Sonnet.

Variables (opcionales; si faltan, usa el modelo global del backend = hoy Groq):
  BRIGADE_LLM_BASE_URL / BRIGADE_LLM_API_KEY / BRIGADE_LLM_MODEL

MODELO INTERCAMBIABLE POR ROL (decisión de Damian 2026-11-16, P0.2 / DIV-08): orquestador, cada jefe y cada ayudante
tienen su PROPIO LLM y cada uno se cambia por configuración, sin tocar código. Un solo punto: `resolve_role_model`.
De más específico a más general:
  1. override del rol   ORQUESTADOR_VOZ_LLM_* (voz) · ORQUESTADOR_LLM_* · BRIGADE_<ID>_LLM_* (jefe de la brigada <ID>) ·
                        AYUDANTE_<ID>_LLM_* (ayudante <ID>) · el modelo declarado en el spec (`BrigadeSpec.client_model`,
                        `AyudanteSpec.client_model`, ej. el BYOM de Scout);
  2. default del tipo   orquestador -> ORQUESTADOR_LLM_* · jefes y ayudantes `shared` -> BRIGADE_LLM_* · `local` -> TIER1_*;
  3. default global     LMSTUDIO_* / LLM_API_KEY y, por último, nemotron en NVIDIA.
<ID> = el id en mayúsculas con los guiones como guion bajo (ej. `investigacion-forense` -> AYUDANTE_INVESTIGACION_FORENSE_LLM_MODEL).
Cada variable admite _BASE_URL, _MODEL y _API_KEY por separado (cambiar solo el modelo hereda endpoint y key).
La KEY de un proveedor NUNCA se usa para otro: una key solo se hereda si el endpoint es el mismo; si no, falta y se dice.
"""

from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlparse

from openai import AsyncOpenAI

from app.config import settings

DEFAULT_ORQUESTADOR_MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"  # ID oficial en el catálogo NIM (verificado 2026-11-11)
DEFAULT_ORQUESTADOR_BASE_URL = "https://integrate.api.nvidia.com/v1"


def load_chief_client_model() -> tuple[AsyncOpenAI, str]:
    """(cliente, modelo) para los jefes de brigada.

    PUNTO DE CAMBIO A SONNET: reemplazar el cuerpo por
        from app.harness.model_registry import client_and_model_for_tier
        return client_and_model_for_tier(3)
    cuando `TIER3_*` esté cableado con una key capaz de Sonnet.
    """
    # La key global (`LLM_API_KEY`) solo se hereda si BRIGADE_LLM_BASE_URL apunta al MISMO endpoint que el chat global:
    # mandarle la key de un proveedor a otro la filtraría (misma regla que el orquestador). Ver `resolve_role_model`.
    return _resolver([_capa_env("BRIGADE_LLM"), _capa_global()], rol="los jefes de brigada (BRIGADE_LLM_API_KEY)")


def load_local_client_model() -> tuple[AsyncOpenAI, str]:
    """(cliente, modelo) LOCAL para jefes que manejan datos personales (ej. Cerebro):
    corre en el Ollama local (tier 1, sin fallback a la nube) → las notas personales
    NUNCA salen de la PC. Esto ES una defensa (privacidad), no una optimización.

    `BRIGADE_LOCAL_MODEL` permite forzar otro modelo local (ej. `jarvis-text-lite`
    para CPU, más liviano que `jarvis-text-v2`)."""
    from app.harness.model_registry import client_and_model_for_tier

    client, model = client_and_model_for_tier(1)  # tier 1 = LOCAL (Ollama, privacidad)
    override = os.getenv("BRIGADE_LOCAL_MODEL", "").strip()
    return client, (override or model)


def load_orquestador_client_model() -> tuple[AsyncOpenAI, str]:
    """(cliente, modelo) del ORQUESTADOR (diseñador de brigadas + clasificador de ruteo).

    Decisión 2026-11-11 (Damian): API OFICIAL de NVIDIA (NIM), modelo nemotron-3.5-super-vl.
    Variables de `.env` (todas opcionales salvo la key):
      ORQUESTADOR_LLM_BASE_URL  (default https://integrate.api.nvidia.com/v1)
      ORQUESTADOR_LLM_MODEL     (default nvidia/nemotron-3.5-super-vl-120b-a12b)
      ORQUESTADOR_LLM_API_KEY   (OBLIGATORIA, solo del .env; nunca en el código ni en chat)

    La key NO cae al fallback global (`LLM_API_KEY` = otro proveedor, hoy OpenRouter): mandarle la key de un
    proveedor a otro la filtraría. Solo si ORQUESTADOR_LLM_BASE_URL se apunta al mismo endpoint que el chat global
    se reusa la key global (reversión a OpenRouter/otro sin duplicar la key).

    Privacidad: el ruteo manda mensajes (pueden tocar notas personales) a este endpoint; ver `routing.llm_classify`."""
    return resolve_role_model("orquestador")


# --- MODELO INTERCAMBIABLE POR ROL (P0.2 / DIV-08): un solo punto de resolución ------------------------------------------
ROLES = ("orquestador", "voz", "mando", "jefe", "ayudante")
_LOOPBACK = ("localhost", "127.0.0.1", "::1", "0.0.0.0")


@dataclass(frozen=True)
class _Capa:
    """Un nivel de la cadena de resolución. Cada campo puede faltar (None): lo completa el nivel siguiente."""

    nombre: str                # de dónde sale (se muestra en la UI: 'BRIGADE_CEREBRO_LLM_*', 'spec', 'global'…). Nunca una key.
    base: str | None = None
    model: str | None = None
    key: str | None = None

    @property
    def vacia(self) -> bool:
        return not (self.base or self.model or self.key)


def _env_slug(ident: str) -> str:
    """'investigacion-forense' -> 'INVESTIGACION_FORENSE' (para armar el nombre de la variable de entorno)."""
    return re.sub(r"[^A-Za-z0-9]+", "_", ident or "").strip("_").upper()


def _capa_env(prefijo: str) -> _Capa:
    def get(suf: str) -> str | None:
        return (os.getenv(f"{prefijo}_{suf}") or "").strip() or None

    return _Capa(f"{prefijo}_*", get("BASE_URL"), get("MODEL"), get("API_KEY"))


def _capa_global() -> _Capa:
    return _Capa("global (LMSTUDIO_* / LLM_API_KEY)", settings.lmstudio_base_url, settings.lmstudio_model, settings.llm_api_key or None)


def _capa_de(nombre: str, loader: Callable[[], tuple]) -> _Capa:
    """Capa a partir de un loader `() -> (cliente, modelo)` (el modelo declarado en un spec, el tier 1 local)."""
    client, model = loader()
    return _Capa(nombre, str(getattr(client, "base_url", "") or "") or None, model or None, getattr(client, "api_key", None) or None)


def _endpoint(base: str | None) -> tuple[str, int | None]:
    u = urlparse(str(base or ""))
    return (u.hostname or "").lower(), u.port


_CLIENTES: dict[tuple, AsyncOpenAI] = {}


def _cliente(base: str, key: str) -> AsyncOpenAI:
    """Cliente reutilizado por (endpoint, key) dentro del mismo event loop: no se arma uno por pedido ni por ayudante.
    max_retries=2: frente a una API en la nube, un 429/503 transitorio sí conviene reintentarlo con backoff."""
    try:
        loop = id(asyncio.get_running_loop())
    except RuntimeError:
        loop = 0
    k = (base, key, settings.llm_request_timeout_seconds, loop)
    if k not in _CLIENTES:
        if len(_CLIENTES) > 64:  # acotado: en la práctica hay un puñado de endpoints
            _CLIENTES.clear()
        _CLIENTES[k] = AsyncOpenAI(base_url=base, api_key=key, timeout=settings.llm_request_timeout_seconds, max_retries=2)
    return _CLIENTES[k]


def _resolver_capas(capas: list[_Capa], rol: str) -> tuple[str, str, str, str]:
    """(base, modelo, key, origen del modelo). El primer valor presente gana, de la capa más específica a la más general.
    La key solo se toma de una capa cuyo endpoint efectivo es el MISMO que el resuelto: nunca la de otro proveedor."""
    base = next((c.base for c in capas if c.base), None)
    model, origen = next(((c.model, c.nombre) for c in capas if c.model), (None, ""))
    if not base or not model:
        raise RuntimeError(f"No se pudo resolver el modelo de {rol}: falta el endpoint o el modelo en la configuración.")
    destino = _endpoint(base)
    key = None
    for i, c in enumerate(capas):
        if not c.key:
            continue
        propio = next((x.base for x in capas[i:] if x.base), None)  # el endpoint para el que esa key fue configurada
        if _endpoint(propio) == destino:
            key = c.key
            break
    if not key:
        if destino[0] in _LOOPBACK:
            key = "local"  # Ollama / LM Studio en esta PC no piden key
        else:
            raise RuntimeError(f"Falta la API key de {rol}: el endpoint {destino[0]} no tiene una key propia configurada en "
                               "backend/.env. No se reutiliza la key de otro proveedor.")
    return base, model, key, origen


def _resolver(capas: list[_Capa], rol: str) -> tuple[AsyncOpenAI, str]:
    base, model, key, _ = _resolver_capas(capas, rol)
    return _cliente(base, key), model


def _capas_de_rol(kind: str, brigade_id: str | None, helper_id: str | None, tipo: str,
                  declarado: Callable[[], tuple] | None) -> tuple[list[_Capa], str]:
    """Las capas (override del rol -> default del tipo -> default global) y el nombre del rol para los mensajes."""
    if kind not in ROLES:
        raise ValueError(f"rol desconocido: {kind!r} (roles: {ROLES})")
    orq = [_capa_env("ORQUESTADOR_LLM"), _Capa("default del orquestador", DEFAULT_ORQUESTADOR_BASE_URL, DEFAULT_ORQUESTADOR_MODEL),
           _capa_global()]
    if kind == "orquestador":
        return orq, "el orquestador (ORQUESTADOR_LLM_API_KEY)"
    if kind == "voz":
        return [_capa_env("ORQUESTADOR_VOZ_LLM"), *orq], "la voz del orquestador (ORQUESTADOR_VOZ_LLM_API_KEY / ORQUESTADOR_LLM_API_KEY)"
    if kind == "mando":  # reparte y concluye en el trabajo conjunto: el lugar para el modelo más capaz
        return [_capa_env("ORQUESTADOR_MANDO_LLM"), *orq], "el mando del orquestador (ORQUESTADOR_MANDO_LLM_API_KEY / ORQUESTADOR_LLM_API_KEY)"
    if kind == "jefe":
        capas = [_capa_env(f"BRIGADE_{_env_slug(brigade_id or '')}_LLM")]
        rol = f"el jefe de {brigade_id}"
    else:
        capas = [_capa_env(f"AYUDANTE_{_env_slug(helper_id or '')}_LLM")]
        rol = f"el ayudante {helper_id}"
    if declarado is not None:
        capas.append(_capa_de("spec (modelo declarado)", declarado))
    if tipo == "local":
        capas.append(_capa_de("TIER1_* (local)", load_local_client_model))
    else:
        capas.append(_capa_env("BRIGADE_LLM"))
    capas += [_capa_global(), _Capa("default (nemotron en NVIDIA)", DEFAULT_ORQUESTADOR_BASE_URL, DEFAULT_ORQUESTADOR_MODEL)]
    return capas, rol


def _override_de_rol(kind: str, brigade_id: str | None, helper_id: str | None) -> _Capa:
    prefijo = {"orquestador": "ORQUESTADOR_LLM", "voz": "ORQUESTADOR_VOZ_LLM", "mando": "ORQUESTADOR_MANDO_LLM", "jefe": f"BRIGADE_{_env_slug(brigade_id or '')}_LLM",
               "ayudante": f"AYUDANTE_{_env_slug(helper_id or '')}_LLM"}[kind]
    return _capa_env(prefijo)


# --- interruptor a LOCAL (O-11): llevar cualquier rol, o todos, a un modelo de esta PC sin tocar el resto de la config -------
def _capa_local_forzada(kind: str, brigade_id: str | None, helper_id: str | None) -> _Capa | None:
    """Si `ROLES_EN_LOCAL` nombra a este rol, la capa del modelo LOCAL (`MODELO_LOCAL_BASE_URL` / `MODELO_LOCAL_MODEL`), que
    gana sobre todo lo demás. Valores (separados por coma): `todos` · `orquestador` · `voz` · `jefes` · `ayudantes` ·
    `brigada:<id>` (su jefe y sus ayudantes) · `jefe:<id>` · `ayudante:<id>`. Vacío = nadie (default)."""
    pedidos = {x.strip().lower() for x in os.getenv("ROLES_EN_LOCAL", "").split(",") if x.strip()}
    if not pedidos:
        return None
    de_brigada = (brigade_id or "").lower() or (helper_id or "").lower().rsplit("-", 1)[0]
    mios = {"todos", kind, {"jefe": "jefes", "ayudante": "ayudantes", "mando": "orquestador"}.get(kind, kind),
            f"jefe:{(brigade_id or '').lower()}" if kind == "jefe" else "", f"ayudante:{(helper_id or '').lower()}" if kind == "ayudante" else "",
            f"brigada:{de_brigada}" if kind in ("jefe", "ayudante") and de_brigada else ""}
    if not (pedidos & (mios - {""})):
        return None
    base, model = (os.getenv("MODELO_LOCAL_BASE_URL") or "").strip(), (os.getenv("MODELO_LOCAL_MODEL") or "").strip()
    if not base or not model:
        raise RuntimeError("ROLES_EN_LOCAL está definido pero falta MODELO_LOCAL_BASE_URL o MODELO_LOCAL_MODEL en backend/.env.")
    if _endpoint(base)[0] not in _LOOPBACK:
        raise RuntimeError("MODELO_LOCAL_BASE_URL tiene que ser un endpoint de ESTA PC (localhost / 127.0.0.1): es el interruptor de privacidad.")
    return _Capa("ROLES_EN_LOCAL (modelo local)", base, model, (os.getenv("MODELO_LOCAL_API_KEY") or "").strip() or "local")


def fallback_role_model(kind: str) -> tuple[Any, str] | None:
    """(cliente, modelo) de RESPALDO de un rol (O-7), o None si no hay uno configurado. Se usa cuando el modelo del rol
    falla (429, caída, timeout) para no degradar de entrada: `ORQUESTADOR_FALLBACK_LLM_*` (orquestador y su voz) y
    `BRIGADE_FALLBACK_LLM_*` (jefes). Necesita _BASE_URL y _MODEL propios; la key, la suya (misma regla: nunca la de otro
    proveedor). Un rol forzado a local (`ROLES_EN_LOCAL`) no tiene respaldo en la nube."""
    capa = _capa_env("ORQUESTADOR_FALLBACK_LLM" if kind in ("orquestador", "voz", "mando") else "BRIGADE_FALLBACK_LLM")
    if not (capa.base and capa.model) or os.getenv("ROLES_EN_LOCAL", "").strip():
        return None
    try:
        return _resolver([capa], rol=f"el respaldo de {kind}")
    except RuntimeError:
        return None


def resolve_role_model(kind: str, brigade_id: str | None = None, helper_id: str | None = None, *, tipo: str = "shared",
                       declarado: Callable[[], tuple] | None = None) -> tuple[Any, str]:
    """(cliente, modelo) de UN rol: 'orquestador' | 'voz' | 'jefe' | 'ayudante'. El único punto donde se decide qué
    modelo corre cada rol (cadena: override del rol -> default del tipo -> default global; ver el docstring del módulo).

    `tipo`: 'shared' (modelo compartido de los jefes, `BRIGADE_LLM_*`) o 'local' (tier 1, `TIER1_*`).
    `declarado`: el loader que el spec declara para ese rol (ej. el BYOM de Scout). Si el rol no tiene un override por
    variable de entorno, se usa TAL CUAL (mismo cliente): cambiar el modelo no cambia el contrato."""
    if kind not in ROLES:
        raise ValueError(f"rol desconocido: {kind!r} (roles: {ROLES})")
    local = _capa_local_forzada(kind, brigade_id, helper_id)
    if local is not None:  # interruptor de privacidad: gana sobre cualquier otra configuración del rol
        return _resolver([local], rol=f"{kind} (forzado a local)")
    if kind in ("jefe", "ayudante") and declarado is not None and _override_de_rol(kind, brigade_id, helper_id).vacia:
        return declarado()
    capas, rol = _capas_de_rol(kind, brigade_id, helper_id, tipo, declarado)
    return _resolver(capas, rol)


def describe_role_model(kind: str, brigade_id: str | None = None, helper_id: str | None = None, *, tipo: str = "shared",
                        declarado: Callable[[], tuple] | None = None) -> dict:
    """Modelo EFECTIVO + proveedor de un rol y de qué nivel de la configuración salió (`origen`). Nunca toca ni
    devuelve claves. Si no se puede resolver, lo dice (no inventa): la UI no se rompe."""
    try:
        local = _capa_local_forzada(kind, brigade_id, helper_id) if kind in ROLES else None
        if local is not None:
            return {**describe_endpoint(local.base, local.model or ""), "origen": local.nombre, "ok": True}
        if kind in ("jefe", "ayudante") and declarado is not None and _override_de_rol(kind, brigade_id, helper_id).vacia:
            client, model = declarado()
            d = describe_endpoint(getattr(client, "base_url", ""), model)
            return {**d, "origen": "spec (modelo declarado)", "ok": True}
        capas, rol = _capas_de_rol(kind, brigade_id, helper_id, tipo, declarado)
        base, model, _key, origen = _resolver_capas(capas, rol)
        return {**describe_endpoint(base, model), "origen": origen, "ok": True}
    except Exception as exc:  # noqa: BLE001 — falta una key, etc.
        return {"model": "", "name": "", "provider": "?", "local": False, "origen": "", "ok": False,
                "label": f"modelo sin resolver ({type(exc).__name__}: {str(exc)[:120]})"}


# --- una llamada de chat de un rol: tope de tiempo, presupuesto de tokens y RAZONAMIENTO opcional (O-7) -------------------------
# Los modelos que "razonan" antes de responder (nemotron) gastan la mayor parte del tiempo y de los tokens en ese razonamiento.
# Medido el 2026-11-15 contra NVIDIA con datos de prueba: una respuesta de una oración tarda ~4-5 s razonando y ~1 s sin razonar
# (≈25 veces menos tokens de salida). Hay pasos donde razonar no aporta (clasificar en una palabra, redactar un mensaje desde
# un reporte ya armado y verificado por código) y pasos donde sí (sintetizar). Cada paso lo decide por config (`*_RAZONAMIENTO`).
# Cómo se le pide a cada PROVEEDOR que no razone (es conocimiento del proveedor, no del rol: por eso vive en esta tabla, junto
# a `_PROVEEDORES`). Un proveedor que no está acá simplemente no recibe ningún parámetro extra.
_SIN_RAZONAR: dict[str, dict] = {
    "NVIDIA": {"chat_template_kwargs": {"enable_thinking": False}},
}


def razonamiento(variable: str, default: bool) -> bool:
    """¿Este paso razona? `variable` = nombre de la variable de entorno (`on`/`off`); sin definir, `default`."""
    v = os.getenv(variable, "").strip().lower()
    if v in ("0", "off", "no", "false"):
        return False
    if v in ("1", "on", "si", "sí", "true", "yes"):
        return True
    return default


async def completar(client: Any, model: str, messages: list[dict], *, temperature: float, timeout: float,
                    max_tokens: int | None = None, razonar: bool = True) -> str:
    """Una llamada de chat SIN tools de un rol. `razonar=False` le pide al proveedor que no razone (si se sabe cómo); si el
    proveedor rechaza ese parámetro (400/422), se repite la llamada sin él: nunca falla por una optimización."""
    from .identidad import de_fabrica, personalizar

    if not de_fabrica():  # los prompts de SISTEMA son texto del código: van con el nombre del asistente y del usuario configurados
        messages = [{**m, "content": personalizar(m["content"])} if m.get("role") == "system" and isinstance(m.get("content"), str) else m
                    for m in messages]
    kw: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature}
    if max_tokens and max_tokens > 0:
        kw["max_tokens"] = max_tokens
    extra = None if razonar else _SIN_RAZONAR.get(describe_endpoint(getattr(client, "base_url", ""), model)["provider"])
    if extra:
        try:
            resp = await asyncio.wait_for(client.chat.completions.create(**kw, extra_body=extra), timeout=timeout)
            return resp.choices[0].message.content or ""
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            if getattr(exc, "status_code", None) not in (400, 404, 422):
                raise
    resp = await asyncio.wait_for(client.chat.completions.create(**kw), timeout=timeout)
    return resp.choices[0].message.content or ""


# --- etiqueta del modelo EFECTIVO (lo que ve Damian en la UI) ---------------------------------------------------------
_PROVEEDORES = (
    ("integrate.api.nvidia.com", "NVIDIA"), ("nvidia.com", "NVIDIA"), ("openrouter.ai", "OpenRouter"), ("api.groq.com", "Groq"),
    ("api.openai.com", "OpenAI"), ("api.anthropic.com", "Anthropic"), ("generativelanguage.googleapis.com", "Google AI"),
    ("api.deepseek.com", "DeepSeek"),
)


def describe_endpoint(base_url: object, model: str) -> dict:
    """Modelo REAL + proveedor a partir del endpoint y el id resuelto (nunca toca claves).
    `local` es True solo si el endpoint es de esta PC (Ollama :11434, LM Studio :1234, loopback)."""
    from urllib.parse import urlparse

    base = str(base_url or "")
    host = (urlparse(base).hostname or "").lower()
    port = urlparse(base).port
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        provider, local = {11434: "Ollama", 1234: "LM Studio"}.get(port or 0, "local"), True
    else:
        provider, local = next((n for h, n in _PROVEEDORES if host == h or host.endswith("." + h)), host or "?"), False
    name = model.split("/", 1)[1] if "/" in model else model  # 'nvidia/nemotron-…' -> 'nemotron-…'
    return {"model": model, "name": name, "provider": provider, "local": local, "label": f"{name} ({provider})"}


def effective_label(loader) -> str:
    """Etiqueta 'nemotron-… (NVIDIA)' de lo que `loader()` (-> (cliente, modelo)) resuelve HOY. Si no se puede resolver
    (falta una key, etc.) lo dice, no inventa."""
    try:
        client, model = loader()
        return describe_endpoint(getattr(client, "base_url", ""), model)["label"]
    except Exception as exc:  # noqa: BLE001
        return f"modelo sin resolver ({type(exc).__name__})"


def orquestador_info() -> dict:
    """Modelo efectivo del propio orquestador (ruteo + diseñador)."""
    try:
        client, model = load_orquestador_client_model()
        return describe_endpoint(client.base_url, model)
    except Exception as exc:  # noqa: BLE001 — sin key: se informa, la UI no se rompe
        return {"model": DEFAULT_ORQUESTADOR_MODEL, "name": DEFAULT_ORQUESTADOR_MODEL.split("/", 1)[-1], "provider": "NVIDIA",
                "local": False, "label": f"{DEFAULT_ORQUESTADOR_MODEL.split('/', 1)[-1]} (NVIDIA) — ⚠ {str(exc)[:80]}"}
