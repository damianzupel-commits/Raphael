"""Carga LIVIANA del registro de tools para el Orquestador standalone.

`app/tools/__init__.py` define el registro (`register_tool`, `call_tool`, ...) y AL FINAL
importa los ~30 módulos de tools del Raphael completo (pentest, malware, desktop/pywinauto,
phone, playwright, yara...), que es lo que hace pesado el arranque. Los jefes de brigada
(`brigades/chief.py`) solo necesitan `call_tool` + `openai_tool_schemas` y las tools de sus
allowlists: filesystem, obsidian, research e investigation.

En vez de tocar el monolito, este módulo carga el MISMO `app/tools/__init__.py` pero saltea
los imports de los módulos que no hacen falta. Es el mismo código y el mismo registro: lo que
cambia es cuántos módulos se registran. Tiene que correr ANTES de importar `brigades`.

Si el formato del final de `app/tools/__init__.py` cambia y ya no matchea, falla fuerte en
vez de cargar todo en silencio (para que el arranque liviano no se degrade sin que nadie lo vea).
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

# Módulos de tools que usan los jefes de hoy: Cerebro (obsidian), Investigación
# (Scout = research + obsidian + fs; Forense = investigation). Sumar una brigada que use
# otras tools = sumar su módulo acá.
KEEP = frozenset({"filesystem", "obsidian", "research", "investigation", "video_edit"})

_IMPORT_LINE = re.compile(r"^from \. import (\w+)\s+# noqa")


def install() -> None:
    """Deja `app.tools` en sys.modules con solo los módulos de KEEP registrados."""
    if "app.tools" in sys.modules:
        raise RuntimeError("app.tools ya está cargado: instalá la versión liviana antes de importar brigades/app.tools")
    import app  # paquete vacío (sin side effects)

    tools_dir = Path(app.__file__).resolve().parent / "tools"
    init = tools_dir / "__init__.py"
    kept: list[str] = []
    dropped = 0
    for line in init.read_text(encoding="utf-8").splitlines():
        m = _IMPORT_LINE.match(line)
        if m and m.group(1) not in KEEP:
            dropped += 1
            continue
        kept.append(line)
    if not dropped:
        raise RuntimeError(
            "slim_tools: no encontré los imports de módulos al final de app/tools/__init__.py "
            "(¿cambió el formato?). No cargo el registro completo en silencio."
        )

    spec = importlib.util.spec_from_file_location("app.tools", init, submodule_search_locations=[str(tools_dir)])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["app.tools"] = mod
    app.tools = mod  # type: ignore[attr-defined]
    exec(compile("\n".join(kept), str(init), "exec"), mod.__dict__)  # noqa: S102 — mismo código del repo, filtrado


def stub_agent_persona() -> None:
    """Cerebro arma su prompt con `from app.agent import RAPHAEL_PERSONA`; importar app.agent
    es importar el monolito entero. Se deja un módulo `app.agent` mínimo con SOLO la persona,
    leída del propio agent.py por AST (sin ejecutarlo), así la identidad de Raphael sigue siendo
    la misma fuente de verdad."""
    import ast
    import types

    import app

    persona = ""
    try:
        src = (Path(app.__file__).resolve().parent / "agent.py").read_text(encoding="utf-8")
        for node in ast.parse(src).body:
            if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "RAPHAEL_PERSONA" for t in node.targets):
                persona = ast.literal_eval(node.value)
                break
    except Exception:  # noqa: BLE001 — sin persona el jefe igual funciona con su prompt de rol
        persona = ""
    if not persona:
        persona = "Sos Raphael, la Gran Sabia: el orquestador de Damian. Sabio, preciso y sereno."
    stub = types.ModuleType("app.agent")
    stub.RAPHAEL_PERSONA = persona  # type: ignore[attr-defined]
    sys.modules["app.agent"] = stub
    app.agent = stub  # type: ignore[attr-defined]
