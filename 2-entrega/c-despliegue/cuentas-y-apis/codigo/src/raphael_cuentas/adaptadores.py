"""Verificación de cuentas: un adaptador REAL (pedidos de solo lectura por HTTPS) y uno SIMULADO (sin red).

Los tests y el modo `--simulado` usan el simulado. El real nunca manda mensajes, cobra ni cambia nada: solo lee.
Ningún resultado incluye el valor de una clave (se censura aunque el proveedor la repita en un error).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol

from .catalogo import Cuenta
from .entorno import cargada, estado_de


@dataclass(frozen=True)
class Resultado:
    cuenta: str
    estado: str      # "ok", "falla", "omitida" (falta algo o no se puede probar sola) o "simulada"
    detalle: str


class Verificador(Protocol):
    def probar(self, cuenta: Cuenta, env: Mapping[str, str]) -> Resultado: ...


def censurar(texto: str, env: Mapping[str, str], cuenta: Cuenta) -> str:
    for v in cuenta.vars:
        val = (env.get(v.nombre) or "").strip()
        if v.secreta and len(val) >= 4:
            texto = texto.replace(val, "***")
    return texto


class AdaptadorSimulado:
    """No sale a la red. Responde según `respuestas` (id de cuenta → (estado, detalle)); por defecto, 'simulada' si la
    cuenta está completa y 'omitida' si falta algo."""

    def __init__(self, respuestas: Mapping[str, tuple[str, str]] | None = None) -> None:
        self.respuestas = dict(respuestas or {})
        self.llamadas: list[str] = []

    def probar(self, cuenta: Cuenta, env: Mapping[str, str]) -> Resultado:
        self.llamadas.append(cuenta.id)
        if cuenta.id in self.respuestas:
            est, det = self.respuestas[cuenta.id]
            return Resultado(cuenta.id, est, det)
        e = estado_de(cuenta, env)
        if e.faltan:
            return Resultado(cuenta.id, "omitida", f"falta {', '.join(e.faltan)}")
        return Resultado(cuenta.id, "simulada", "datos completos (prueba simulada, sin red)")


# id de verificador → (método, función que arma la URL, función que arma los headers). Todos GET de solo lectura.
def _bearer(var: str) -> Callable[[Mapping[str, str]], dict[str, str]]:
    return lambda env: {"Authorization": f"Bearer {env[var].strip()}"}


_VER = lambda env: (env.get("META_GRAPH_VERSION") or "v26.0").strip()  # noqa: E731

PEDIDOS: dict[str, tuple[Callable[[Mapping[str, str]], str], Callable[[Mapping[str, str]], dict[str, str]]]] = {
    "openrouter": (lambda env: "https://openrouter.ai/api/v1/auth/key", _bearer("OPENROUTER_API_KEY")),
    "nvidia": (lambda env: "https://integrate.api.nvidia.com/v1/models", _bearer("NVIDIA_API_KEY")),
    "meta_whatsapp": (lambda env: f"https://graph.facebook.com/{_VER(env)}/{env['META_WA_PHONE_ID'].strip()}"
                                  "?fields=display_phone_number", _bearer("META_WA_TOKEN")),
    "meta_instagram": (lambda env: f"https://{(env.get('META_IG_HOST') or 'graph.instagram.com').strip()}/{_VER(env)}/me"
                                   "?fields=username", _bearer("META_IG_TOKEN")),
    "mercado_pago": (lambda env: "https://api.mercadopago.com/users/me", _bearer("MP_ACCESS_TOKEN")),
    "hetzner": (lambda env: "https://api.hetzner.cloud/v1/servers?per_page=1", _bearer("HCLOUD_TOKEN")),
    "url_publica": (lambda env: env["RAPHAEL_PUBLIC_URL"].strip().rstrip("/") + "/api/v1/health", lambda env: {}),
}


def _local_url(env: Mapping[str, str]) -> str:
    base = (env.get("LOCAL_LLM_URL") or "http://127.0.0.1:11434").strip().rstrip("/")
    lmstudio = (env.get("LOCAL_LLM_KIND") or "ollama").strip().lower() == "lmstudio"
    return base + ("/v1/models" if lmstudio else "/api/tags")


PEDIDOS["local_llm"] = (_local_url, lambda env: {})


class AdaptadorReal:
    """Hace UN pedido GET de solo lectura por cuenta. `abrir` se puede reemplazar (los tests no usan red)."""

    def __init__(self, abrir: Callable[..., object] | None = None, timeout: float = 10.0) -> None:
        self.abrir = abrir or urllib.request.urlopen
        self.timeout = timeout

    def probar(self, cuenta: Cuenta, env: Mapping[str, str]) -> Resultado:
        e = estado_de(cuenta, env)
        if e.faltan:
            return Resultado(cuenta.id, "omitida", f"falta {', '.join(e.faltan)}")
        if e.problemas:
            return Resultado(cuenta.id, "falla", "; ".join(e.problemas))
        if cuenta.id == "transferencia":
            return Resultado(cuenta.id, "ok", "formato válido (no se puede confirmar con el banco)")
        pedido = PEDIDOS.get(cuenta.verificacion)
        if pedido is None:
            return Resultado(cuenta.id, "omitida", "no se prueba en vivo")
        url_fn, headers_fn = pedido
        if cuenta.id != "local_llm" and not url_fn(env).startswith("https://"):
            return Resultado(cuenta.id, "falla", "solo se prueba por https")
        try:
            req = urllib.request.Request(url_fn(env), headers={**headers_fn(env), "Accept": "application/json"}, method="GET")
            with self.abrir(req, timeout=self.timeout) as resp:  # type: ignore[operator]
                codigo = getattr(resp, "status", 200)
                cuerpo = resp.read(65536).decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            msg = {401: "clave rechazada (401)", 403: "sin permisos (403)", 404: "no encontrado (404)"}.get(
                exc.code, f"error HTTP {exc.code}")
            return Resultado(cuenta.id, "falla", censurar(msg, env, cuenta))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            motivo = "sin conexión" if cuenta.id != "local_llm" else "no está prendido o no responde"
            return Resultado(cuenta.id, "falla", censurar(f"{motivo}: {getattr(exc, 'reason', exc)}", env, cuenta))
        if not 200 <= codigo < 300:
            return Resultado(cuenta.id, "falla", f"respuesta {codigo}")
        return Resultado(cuenta.id, "ok", censurar(_resumen(cuenta.id, cuerpo), env, cuenta))


def _resumen(id_: str, cuerpo: str) -> str:
    try:
        d = json.loads(cuerpo)
    except ValueError:
        return "responde"
    if id_ == "local_llm":
        n = len(d.get("models") or d.get("data") or [])
        return f"responde, {n} modelo(s) bajado(s)" if n else "responde pero no hay modelos bajados"
    if id_ == "openrouter":
        data = d.get("data") or {}
        lim = data.get("limit_remaining")
        return "clave válida" + (f", saldo restante {lim}" if lim is not None else "")
    if id_ in {"nvidia", "hetzner"}:
        return "clave válida"
    return "responde"


def sin_clave_local(env: Mapping[str, str]) -> bool:
    return not cargada(env.get("LOCAL_LLM_URL"))
