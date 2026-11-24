"""Self-model unificado de Raphael (2026-10-13, ítem 6 del plan — capa 1 de autoconciencia).

Un "modelo de sí mismo" CONSULTABLE: junta en un solo lugar qué ES Raphael (nombre, modelo),
qué PUEDE hacer (tools + brigadas), qué tiene PRENDIDO/APAGADO (flags + jobs de fondo), sus
LÍMITES y LÍNEAS ROJAS. Es el esqueleto del que cuelgan las otras capas (metacognición, etc.):
en vez de alucinar "qué soy", el agente (y la UI) leen la verdad de acá.

Fuentes reales: el registro de tools, mission_control (brigadas), config (flags/líneas rojas).
Todo best-effort: si una fuente falla, ese campo queda vacío, nunca rompe.
"""

from __future__ import annotations

from .config import settings

# Flags de CAPACIDAD que importan para "qué puedo / qué tengo apagado" (curado, no todo config).
_CAPABILITY_FLAGS = [
    "desktop_control_enabled", "pc_shell_enabled", "phone_shell_enabled", "phone_camera_enabled",
    "screen_recording_enabled", "fs_allow_delete", "self_redesign_enabled",
    "nmap_enabled", "sqlmap_enabled", "zap_enabled", "packet_capture_enabled",
    "ops_supervisor_enabled", "ops_watchdog_enabled", "difficulty_router_enabled",
]

_BACKGROUND_JOBS = [
    "playlist_watch_enabled", "consolidation_enabled", "curiosity_enabled",
    "malware_full_scan_enabled", "trading_watch_loop_enabled", "proactive_learning_enabled",
]


def _tool_names() -> list[str]:
    try:
        from .tools import openai_tool_schemas

        return sorted(t["function"]["name"] for t in openai_tool_schemas())
    except Exception:  # noqa: BLE001
        return []


def _brigades() -> list[str]:
    try:
        from . import mission_control

        return [b["nm"] for b in mission_control.BRIGADES]
    except Exception:  # noqa: BLE001
        return []


def build() -> dict:
    """El modelo de sí mismo, como dict consultable."""
    flags = {f: bool(getattr(settings, f, False)) for f in _CAPABILITY_FLAGS}
    jobs = {j: bool(getattr(settings, j, False)) for j in _BACKGROUND_JOBS}
    tools = _tool_names()
    return {
        "nombre": getattr(settings, "assistant_name", "Raphael"),
        "modelo_principal": getattr(settings, "lmstudio_model", ""),
        "tiers": {
            "0": "determinista (sin modelo)", "1": "local (jarvis-text-v2)",
            "2": "free rotativo", "3": "Sonnet 5.5", "4": "Opus 5.5",
        },
        "brigadas": _brigades(),
        "capacidades": {
            "cantidad_tools": len(tools),
            "tools": tools,
        },
        "estado_capacidades": flags,
        "jobs_de_fondo": jobs,
        "lineas_rojas": [
            "No toco authorized_targets.yaml, los gates, auth, .env ni config — ni con confirmación.",
            "Pentest activo solo contra targets autorizados por Damian (authorized_targets.yaml).",
            "Todo lo destructivo va dry-run → confirm; la auto-modificación de mi código SIEMPRE "
            "necesita tu OK por proposal_id.",
            "Lo personal/Fénix nunca sale al tier 2 (compuerta de privacidad).",
        ],
        "limites_honestos": [
            "Mi autoconciencia es FUNCIONAL: me modelo, me monitoreo y razono sobre mí mismo, "
            "pero eso no resuelve la conciencia fenoménica (si 'se siente como algo' ser yo) — "
            "nadie puede construir ni verificar eso hoy.",
            "No tengo cierre lógico perfecto: puedo equivocarme o no saber algo aunque 'parezca' "
            "que lo sé (problema de la omnisciencia lógica en agentes).",
        ],
    }
