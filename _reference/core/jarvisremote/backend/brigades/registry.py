"""Registro de los jefes de brigada. Agregar una brigada = declarar su `BrigadeSpec` y sumarla a `_SPECS`.

Cada jefe se instancia una vez (cacheado): su estado vive en disco, así que una
sola instancia alcanza. El modelo de los jefes sale de `brigades/config.py` (hoy Groq
free para los "shared"; mañana Sonnet — un solo punto de cambio).

Dos tipos de entrada:
  - `_SPECS`:     brigadas DECLARATIVAS (Cerebro, Investigación): un `BrigadeSpec` que ejecuta el
                  motor genérico (brigades/engine.py). Es el camino para toda brigada nueva.
  - `_BRIGADES`:  legacy. Hoy solo Scout, que nació antes del molde y sigue como `BrigadeChief` plano.
"""

from __future__ import annotations

import importlib

from .chief import BrigadeChief, ChiefConfig
from .config import load_chief_client_model
from .engine import GenericChief
from .spec import BrigadeSpec


def _scout_config() -> ChiefConfig:
    # Scout fue el primer jefe de facto; acá queda expresado como ChiefConfig.
    # persistent=True: TODOS los jefes son persistentes (decisión 2026-11-03, el
    # "representante de plaza"). Lo efímero/por-tarea son los AYUDANTES, no el jefe.
    from scout.config import load_scout_config
    from scout.identity import SCOUT_NAME, SCOUT_TOOL_NAMES, build_scout_system_prompt

    sc = load_scout_config()
    return ChiefConfig(
        id="scout",
        name=SCOUT_NAME,
        tool_names=SCOUT_TOOL_NAMES,
        system_prompt=build_scout_system_prompt(sc.capture_dir),
        vault_path=sc.vault_path,
        embeddings_path=sc.embeddings_path,
        persistent=True,
    )


# Legacy: id -> (factory de ChiefConfig, loader de (cliente, modelo)).
_BRIGADES: dict[str, tuple] = {
    "scout": (_scout_config, load_chief_client_model),
}

# Declarativas: id -> 'modulo:SPEC'. El import es perezoso (un spec importa sus tools recién al usarse).
_SPECS: dict[str, str] = {
    "cerebro": "brigades.cerebro:SPEC",
    "investigacion": "brigades.investigacion:SPEC",
    "seguridad": "brigades.seguridad:SPEC",
    "video": "brigades.video:SPEC",
}

_chiefs: dict[str, BrigadeChief] = {}
# Jefes de brigadas CREADAS (Etapa 2): id -> (hash aprobado, jefe). Se reverifica la aprobación en CADA uso.
_created_chiefs: dict[str, tuple[str, BrigadeChief]] = {}


def created_active_ids() -> list[str]:
    """Brigadas creadas por borrador que están ACTIVAS (aprobación firmada y vigente). Los borradores NUNCA aparecen acá."""
    from . import draft_store

    try:
        return [i for i in draft_store.active_ids() if i not in _BRIGADES and i not in _SPECS]
    except Exception:  # noqa: BLE001 — un almacén ilegible no tumba el registro: solo no hay brigadas creadas
        return []


def available() -> list[str]:
    return list(_BRIGADES) + list(_SPECS) + created_active_ids()


def get_spec(brigade_id: str) -> BrigadeSpec:
    """El spec declarativo de una brigada. KeyError si no existe, es legacy (Scout) o es un BORRADOR sin activar."""
    target = _SPECS.get(brigade_id)
    if target is None:
        from . import draft_store

        return draft_store.active_spec(brigade_id)  # KeyError si no está activa y verificada
    mod, _, name = target.partition(":")
    return getattr(importlib.import_module(mod), name)


def specs() -> dict[str, BrigadeSpec]:
    """Todas las brigadas declarativas ACTIVAS (id -> spec): las del sistema + las creadas y aprobadas."""
    out = {bid: get_spec(bid) for bid in _SPECS}
    for bid in created_active_ids():
        try:
            out[bid] = get_spec(bid)
        except KeyError:
            continue
    return out


def get_chief(brigade_id: str) -> BrigadeChief:
    """Jefe (cacheado) de una brigada. Lanza KeyError si no existe o si es un borrador sin activar."""
    if brigade_id in _SPECS or brigade_id in _BRIGADES:
        if brigade_id not in _chiefs:
            if brigade_id in _SPECS:
                spec = get_spec(brigade_id)
                spec.ensure_tool_modules()  # antes de armar el jefe: su allowlist se resuelve contra el registro
                client, model = spec.load_client_model()
                _chiefs[brigade_id] = GenericChief.from_spec(spec, client, model)
            else:
                config_factory, model_loader = _BRIGADES[brigade_id]
                client, model = model_loader()
                _chiefs[brigade_id] = BrigadeChief(config_factory(), client, model)
        return _chiefs[brigade_id]

    # Brigada creada: la aprobación se reverifica en cada uso (desactivar o editar la apaga al instante, también
    # si el cambio lo hizo OTRO proceso: el backend completo y el orquestador comparten el almacén en disco).
    from . import draft_store

    try:
        spec = draft_store.active_spec(brigade_id)
    except KeyError:
        _created_chiefs.pop(brigade_id, None)
        raise KeyError(f"brigada desconocida o sin activar: {brigade_id}") from None
    h = draft_store.get_record(brigade_id)["hash"]
    cached = _created_chiefs.get(brigade_id)
    if cached is None or cached[0] != h:
        spec.ensure_tool_modules()
        client, model = spec.load_client_model()
        _created_chiefs[brigade_id] = (h, GenericChief.from_spec(spec, client, model))
    return _created_chiefs[brigade_id][1]
