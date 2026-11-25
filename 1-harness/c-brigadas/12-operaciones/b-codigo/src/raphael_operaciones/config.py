"""Configuración de Operaciones: lo que dice `installation.yaml` (config de la brigada) y, en su defecto, el entorno.

Orden: la config de la brigada manda; si la clave no está, se mira la variable de entorno `OPERACIONES_<CLAVE>`; si
tampoco, el valor por defecto (siempre el más seguro). Nada de esto son claves: son interruptores y carpetas. Las
contraseñas de sitios web van en variables propias (ver `adapters/credentials.py`) y nunca por la config ni por un chat.

Las listas del entorno se separan con `;` (así sirven igual en Windows, con rutas con `:`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from .modes import OperationMode, parse_mode

ENV_PREFIX = "OPERACIONES_"
TRUE = {"1", "true", "si", "sí", "yes", "y", "on", "verdadero"}
FALSE = {"0", "false", "no", "n", "off", "falso", ""}
ADAPTER_MODES = ("real", "simulado")

DEFAULT_SANDBOX = Path.home() / ".raphael" / "operaciones" / "carpeta-segura"
DEFAULT_CACHE = Path.home() / ".raphael" / "operaciones" / "cache-web"


class ConfigError(ValueError):
    """La config de Operaciones está mal. El mensaje dice qué clave y qué se esperaba."""


@dataclass(frozen=True)
class OpsConfig:
    adapters: str = "simulado"                  # "real" toca la PC y el celular de verdad; "simulado" no toca nada
    mode: OperationMode = OperationMode.AUTONOMOUS
    sandbox_dir: Path = DEFAULT_SANDBOX         # la carpeta segura: única raíz de archivos si nadie configura otra
    fs_roots: tuple[str, ...] = ()              # raíces extra, valen en los dos modos
    fs_supervised_roots: tuple[str, ...] = ()   # raíces extra, solo en modo supervisado
    fs_denied: tuple[str, ...] = ()             # carpetas prohibidas aunque caigan dentro de una raíz
    fs_allow_delete: bool = False
    pc_shell: bool = False                      # permitir comandos de shell reales en la PC
    desktop: bool = False                       # permitir control real del escritorio (mouse, teclado, ventanas)
    phone_shell: bool = False                   # permitir comandos reales en el celular (Termux)
    phone_camera: bool = False                  # permitir fotos y video con la cámara del celular
    phone_timeout: float = 30.0
    browser_headless: bool = True
    browser_channel: str = ""                   # "msedge" para usar el Edge del sistema (ver LIENZO)
    web_deny_domains: tuple[str, ...] = ()
    web_login_allow: tuple[str, ...] = ()       # sitios donde Raphael puede iniciar sesión con credenciales cargadas
    web_proxies: tuple[str, ...] = ()
    web_local_net: bool = False                 # permitir que web_get traiga páginas de la red local (por defecto no)
    web_cache_dir: Path = DEFAULT_CACHE
    web_cache_versions: int = 5
    web_cache_days: int = 7
    supervisor: bool = False                    # revisión de llamados por un modelo local (falla abierta)
    notes: tuple[str, ...] = field(default_factory=tuple)   # avisos de cómo se leyó la config (para la salud)

    @property
    def real(self) -> bool:
        return self.adapters == "real"


def _get(config: Mapping, env: Mapping[str, str], key: str):
    if key in config and config[key] is not None:
        return config[key]
    raw = env.get(ENV_PREFIX + key.upper())
    return raw if raw not in (None, "") else None


def _bool(value, key: str, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in TRUE:
        return True
    if text in FALSE:
        return False
    raise ConfigError(f"{key}: se esperaba sí o no, llegó {value!r}")


def _number(value, key: str, default: float, minimum: float, maximum: float) -> float:
    if value is None:
        return default
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ConfigError(f"{key}: se esperaba un número, llegó {value!r}") from None
    if not minimum <= n <= maximum:
        raise ConfigError(f"{key}: tiene que estar entre {minimum:g} y {maximum:g}, llegó {n:g}")
    return n


def _list(value, key: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        items = [p.strip() for p in value.replace("\n", ";").split(";")]
    elif isinstance(value, (list, tuple)):
        items = [str(p).strip() for p in value]
    else:
        raise ConfigError(f"{key}: se esperaba una lista, llegó {value!r}")
    return tuple(p for p in items if p)


def load_config(config: Mapping | None = None, env: Mapping[str, str] | None = None) -> OpsConfig:
    """Arma la config. Un valor inválido da `ConfigError` (la salud de la brigada lo dice; no se monta a ciegas)."""
    config = dict(config or {})
    env = env or {}
    notes: list[str] = []

    adapters = str(_get(config, env, "adaptadores") or "simulado").strip().lower()
    if adapters not in ADAPTER_MODES:
        raise ConfigError(f"adaptadores: tiene que ser 'real' o 'simulado', llegó {adapters!r}")

    mode, warn = parse_mode(_get(config, env, "modo"))
    if warn:
        notes.append(warn)

    sandbox = _get(config, env, "carpeta_segura")
    cache = _get(config, env, "web_cache_carpeta")
    cfg = OpsConfig(
        adapters=adapters,
        mode=mode,
        sandbox_dir=Path(str(sandbox)).expanduser() if sandbox else DEFAULT_SANDBOX,
        fs_roots=_list(_get(config, env, "fs_raices"), "fs_raices"),
        fs_supervised_roots=_list(_get(config, env, "fs_supervisado"), "fs_supervisado"),
        fs_denied=_list(_get(config, env, "fs_prohibidas"), "fs_prohibidas"),
        fs_allow_delete=_bool(_get(config, env, "fs_permitir_borrar"), "fs_permitir_borrar", False),
        pc_shell=_bool(_get(config, env, "pc_shell"), "pc_shell", False),
        desktop=_bool(_get(config, env, "escritorio"), "escritorio", False),
        phone_shell=_bool(_get(config, env, "celular_shell"), "celular_shell", False),
        phone_camera=_bool(_get(config, env, "celular_camara"), "celular_camara", False),
        phone_timeout=_number(_get(config, env, "celular_timeout"), "celular_timeout", 30.0, 1, 300),
        browser_headless=_bool(_get(config, env, "navegador_headless"), "navegador_headless", True),
        browser_channel=str(_get(config, env, "navegador_canal") or "").strip(),
        web_deny_domains=_list(_get(config, env, "web_vetados"), "web_vetados"),
        web_login_allow=_list(_get(config, env, "web_login_permitidos"), "web_login_permitidos"),
        web_proxies=_list(_get(config, env, "web_proxies"), "web_proxies"),
        web_local_net=_bool(_get(config, env, "web_red_local"), "web_red_local", False),
        web_cache_dir=Path(str(cache)).expanduser() if cache else DEFAULT_CACHE,
        web_cache_versions=int(_number(_get(config, env, "web_cache_versiones"), "web_cache_versiones", 5, 1, 50)),
        web_cache_days=int(_number(_get(config, env, "web_cache_dias"), "web_cache_dias", 7, 1, 365)),
        supervisor=_bool(_get(config, env, "supervisor"), "supervisor", False),
        notes=tuple(notes),
    )
    return cfg
