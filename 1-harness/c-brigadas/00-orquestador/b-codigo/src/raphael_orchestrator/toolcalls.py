"""Exporta el registro de tool calls del harness al formato JSONL que lee la introspección (brigada 13, `analyzer.py`).

Cada línea: {"timestamp", "conversation_id", "tool", "ok", "error"?, "arguments"?}. Se arma desde las entradas de auditoría
del harness: `tool` (corrió bien) y `tool_fallida` (falló). Solo convierte y escribe; no lee la auditoría por su cuenta
(quien lo llama le pasa las entradas) y NO ejecuta nada. Los argumentos ya vienen sin secretos: la auditoría los redacta.

LÍMITE (pendiente para el harness): hoy la auditoría no guarda los argumentos de la tool ni un id de conversación. Mientras
tanto `conversation_id` es la brigada y el día (así se agrupan las fallas repetidas), y `arguments` va vacío: el patrón
`error_repetido` anda; los de reescritura de archivos necesitan los argumentos y no se pueden detectar todavía.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

WHATS = ("tool", "tool_fallida")


def to_records(entries: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for e in entries:
        if e.get("what") not in WHATS:
            continue
        when = str(e.get("when") or "")
        rec: dict[str, Any] = {"timestamp": when, "conversation_id": f"{e.get('who', 'harness')}:{when[:10]}",
                               "tool": str(e.get("tool") or ""), "ok": e["what"] == "tool", "arguments": e.get("arguments") or {}}
        if e["what"] == "tool_fallida":
            rec["error"] = str(e.get("error") or "")
        if rec["tool"]:
            out.append(rec)
    return out


def export_jsonl(entries: Iterable[dict[str, Any]], path: str | Path) -> int:
    """Escribe el registro (pisa el archivo) y devuelve cuántas tool calls exportó."""
    recs = to_records(entries)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8")
    return len(recs)
