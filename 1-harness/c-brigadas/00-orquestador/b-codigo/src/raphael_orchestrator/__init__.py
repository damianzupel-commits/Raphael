"""Orquestador de Raphael (pieza 02): el único que habla con la persona y con las brigadas.

Se para encima de `raphael-core` (harness v2, contrato 2.1) y no importa ninguna brigada: todo lo que sabe de ellas sale
del catálogo del harness. Diseño: `docs/design/orchestrator.md`.

Tandas: O1 (config, voz, memoria, autoconocimiento) · O2 (ruteo, turno, watchdog) · O3 (mando y DAG) ·
O4 (confirmación y Secretaria) · O5 (modo master completo).
"""

__version__ = "0.1.0"

from .config import OrchestratorConfig, config_from, load_config  # noqa: E402
from .memory import Conversation, MemorySettings  # noqa: E402
from .self_report import system_report  # noqa: E402
from .voice import Message, Verification, VoiceSettings, chat, communicate, template_message, verify  # noqa: E402

__all__ = [
    "Conversation", "MemorySettings", "Message", "OrchestratorConfig", "Verification", "VoiceSettings", "__version__",
    "chat", "communicate", "config_from", "load_config", "system_report", "template_message", "verify",
]
