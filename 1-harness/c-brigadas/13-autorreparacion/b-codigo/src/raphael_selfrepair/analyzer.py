"""Introspección: detecta patrones de falla conocidos en el comportamiento del agente (portado de `introspection/`).

Mira el registro de tool calls (no el código) y NUNCA toca nada: su salida son hallazgos con evidencia, hipótesis y una
corrección sugerida, para que una persona decida. Convertir un hallazgo en arreglo pasa por `proponer` y `aplicar`.

Formato de cada entrada del registro (JSONL, una por línea):
  {"timestamp": "...", "conversation_id": "...", "tool": "fs_write_file", "ok": true|false, "error": "...",
   "arguments": {"path": "...", "content_sha256": "..."}}
Las entradas sin `conversation_id` no se pueden agrupar y se ignoran.

Patrones:
- reescritura_identica_repetida: N escrituras exitosas seguidas al mismo archivo con el mismo contenido.
- archivo_bloqueado_abandonado: una escritura bloqueada de la que nunca hay una exitosa posterior al mismo archivo.
- error_repetido: la misma tool falla N veces seguidas con el mismo error.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

WRITE_TOOLS = ("fs_write_file",)
MAX_LOG_BYTES = 20_000_000


def finding_id(pattern: str, conversation: str, path: str) -> str:
    return "hz-" + hashlib.sha256(f"{pattern}|{conversation}|{path}".encode()).hexdigest()[:8]


def read_log(path: str | Path) -> list[dict]:
    """Lee un JSONL de a una línea; las que no se pueden leer se saltean. Solo las últimas MAX_LOG_BYTES."""
    p = Path(path)
    if not p.is_file():
        return []
    size = p.stat().st_size
    with p.open("rb") as f:
        if size > MAX_LOG_BYTES:
            f.seek(size - MAX_LOG_BYTES)
            f.readline()                      # la primera línea puede venir cortada
        raw = f.read().decode("utf-8", errors="replace")
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict):
            out.append(d)
    return out


def _group(entries: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = {}
    for e in entries:
        cid = e.get("conversation_id")
        if cid:
            groups.setdefault(str(cid), []).append(e)
    return groups


def _args(e: dict) -> dict:
    a = e.get("arguments")
    return a if isinstance(a, dict) else {}


def _finding(pattern: str, conv: str, tool: str, path: str, summary: str, hypothesis: str, fix: str,
             evidence: list[dict]) -> dict:
    return {"id": finding_id(pattern, conv, path), "pattern": pattern, "conversation_id": conv, "tool": tool, "path": path,
            "summary": summary, "hypothesis": hypothesis, "suggested_fix": fix, "evidence": evidence}


def _repeated_writes(conv: str, entries: list[dict], min_repeats: int) -> list[dict]:
    out: list[dict] = []
    run: list[dict] = []
    prev: tuple | None = None

    def flush() -> None:
        if len(run) < min_repeats:
            return
        path = _args(run[0]).get("path", "?")
        out.append(_finding(
            "reescritura_identica_repetida", conv, run[0].get("tool", ""), str(path),
            f"Reescribió '{path}' con contenido idéntico {len(run)} veces seguidas, sin escribir nada nuevo en el medio.",
            "El modelo entró en un loop: repite la misma tool call porque no percibe que ya tuvo éxito o perdió de vista "
            "qué le falta después de esa escritura.",
            "Un guardarraíl duro en el loop de tool calls: si las últimas N escrituras fueron al mismo archivo con el mismo "
            "`content_sha256`, bloquear la siguiente con un mensaje explícito en vez de ejecutarla de nuevo.",
            [{"timestamp": e.get("timestamp"), "path": path, "content_sha256": _args(e).get("content_sha256")} for e in run]))

    for e in entries:
        if e.get("tool") not in WRITE_TOOLS:
            continue
        if not e.get("ok"):
            flush()
            run, prev = [], None
            continue
        a = _args(e)
        key = (a.get("path"), a.get("content_sha256"))
        if key == prev and key[0] is not None:
            run.append(e)
        else:
            flush()
            run, prev = [e], key
    flush()
    return out


def _abandoned_blocks(conv: str, entries: list[dict]) -> list[dict]:
    writes = [e for e in entries if e.get("tool") in WRITE_TOOLS]
    out: list[dict] = []
    seen: set[str] = set()
    for i, e in enumerate(writes):
        path = _args(e).get("path")
        if e.get("ok") or not path or path in seen:
            continue
        if any(later.get("ok") is True and _args(later).get("path") == path for later in writes[i + 1:]):
            continue
        seen.add(str(path))
        err = str(e.get("error", ""))[:200]
        out.append(_finding(
            "archivo_bloqueado_abandonado", conv, e.get("tool", ""), str(path),
            f"'{path}' fue bloqueado ({err}) y nunca se volvió a escribir con éxito en el resto de la sesión.",
            "El modelo se distrajo con otros archivos después del bloqueo y perdió de vista que este quedó pendiente.",
            "Que el loop lleve un conjunto de archivos pendientes (no uno solo) y no cierre la sesión mientras quede alguno.",
            [{"timestamp": e.get("timestamp"), "path": path, "error": err}]))
    return out


def _repeated_errors(conv: str, entries: list[dict], min_repeats: int) -> list[dict]:
    out: list[dict] = []
    run: list[dict] = []

    def flush() -> None:
        if len(run) < min_repeats:
            return
        tool = str(run[0].get("tool", "?"))
        err = str(run[0].get("error", ""))[:200]
        out.append(_finding(
            "error_repetido", conv, tool, tool,
            f"La tool '{tool}' falló {len(run)} veces seguidas con el mismo error: {err}",
            "El agente insiste con la misma llamada sin cambiar nada: no lee el error o no tiene otra salida.",
            "Cortar el reintento tras N fallas idénticas y avisar a la persona qué se probó.",
            [{"timestamp": e.get("timestamp"), "error": err} for e in run]))

    prev: tuple | None = None
    for e in entries:
        if e.get("ok") or not e.get("tool"):
            flush()
            run, prev = [], None
            continue
        key = (e.get("tool"), str(e.get("error", "")))
        if key == prev:
            run.append(e)
        else:
            flush()
            run, prev = [e], key
    flush()
    return out


def analyze(entries: list[dict], min_repeats: int = 3) -> list[dict]:
    """Todos los hallazgos de todas las conversaciones (un id estable por patrón + conversación + archivo)."""
    findings: list[dict] = []
    for conv, es in _group(entries).items():
        findings += _repeated_writes(conv, es, min_repeats)
        findings += _abandoned_blocks(conv, es)
        findings += _repeated_errors(conv, es, min_repeats)
    return findings
