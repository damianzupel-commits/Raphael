"""Raphael Scout — producto #1 de la suite: investigación / intel continuo.

Módulo separado del monolito (2026-11-02). Reusa el núcleo compartido de
JarvisRemote (cliente LLM, tools, vault, navegador) y expone una superficie
chica y propia. Ver scout/README.md y docs/SPEC-PRODUCTO-INVESTIGACION.md.

Uso rápido:
    python -m scout "investigá el estado de los LLM locales en 2026"

Programático:
    from scout import run_scout
    texto, history = await run_scout("tu tema")
"""

from .engine import run_scout, scout_tool_schemas
from .identity import SCOUT_NAME, SCOUT_TOOL_NAMES

__all__ = ["run_scout", "scout_tool_schemas", "SCOUT_NAME", "SCOUT_TOOL_NAMES"]
