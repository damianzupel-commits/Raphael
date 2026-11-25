"""Las acciones con efecto de la brigada, en un solo lugar. Cada cocinero que pide una acción la ejecuta con esto; los
niveles de autonomía los decide el manifiesto (`manifest.yaml`), no este archivo.

El contenido que viene de terceros (otras brigadas, mensajes, páginas) es DATO: se guarda como nota, nunca se interpreta
como orden. Las notas que escribe Raphael van siempre a `jarvis/`; `human/` solo con una orden de la persona dueña.
"""

from __future__ import annotations

import re
from pathlib import Path

from raphael_core import Action, ActionError, Origin

from .brain import Brain, embedding_text

MAX_TITLE, MAX_CONTENT = 200, 50_000
NOTE_ID = re.compile(r"^[A-Za-z0-9ÁÉÍÓÚÜÑáéíóúüñ_./ -]{1,200}$")


def _text(d: dict, key: str, limit: int, *, required: bool = True) -> str:
    v = d.get(key)
    if v is None or not isinstance(v, str) or not v.strip():
        if required:
            raise ActionError(f"falta '{key}'")
        return ""
    if len(v) > limit:
        raise ActionError(f"'{key}' es demasiado largo (tope {limit} caracteres)")
    return v.strip()


def _tags(d: dict) -> list[str]:
    tags = d.get("tags") or []
    if not isinstance(tags, list):
        raise ActionError("'tags' tiene que ser una lista")
    return [re.sub(r"[^\w-]", "", str(t))[:40] for t in tags[:20] if str(t).strip()]


def run(brain: Brain, action: Action) -> dict:
    """Ejecuta la acción y devuelve su resultado (un dict chico y serializable)."""
    d = action.data
    t = action.type
    if t == "guardar_nota":
        title, content = _text(d, "title", MAX_TITLE), _text(d, "content", MAX_CONTENT)
        if d.get("brigade"):
            note = brain.remember(str(d["brigade"]), title, content, tags=_tags(d), source=d.get("source"))
        else:
            author = "human" if d.get("author") == "human" and action.origin is Origin.OWNER else "jarvis"
            note = brain.save_note(title, content, author=author, tags=_tags(d), category=str(d.get("category") or "")[:60])
        return {"nota": note.id, "titulo": note.title, "con_vector": note.id in brain.index.load()}
    if t == "reindexar":
        if d.get("ruta"):                                   # una sola nota (la que acaba de ingerir Ingesta)
            try:
                rel = Path(str(d["ruta"])).resolve().relative_to(brain.vault.root.resolve()).with_suffix("").as_posix()
                note = brain.vault.read(rel)
            except (ValueError, FileNotFoundError, OSError):
                raise ActionError("la ruta no es una nota de este vault") from None
            return {"nota": note.id, "con_vector": brain.index.update(note.id, embedding_text(note))}
        return brain.reindex()
    if t == "consolidar":
        return brain.consolidate(dry_run=bool(d.get("dry_run", False)), max_clusters=d.get("max_clusters"))
    if t == "registrar_episodio":
        history = d.get("history")
        if not isinstance(history, list) or not history:
            raise ActionError("falta 'history' (la lista de mensajes del turno)")
        ep = brain.episodes.capture(str(d.get("conv_id") or "default")[:80], history, dominio=str(d.get("dominio") or "")[:40],
                                    ai=brain.ai if brain.has_model() else None)
        return {"episodio": ep.id if ep else None, "sensibilidad": ep.sensibilidad if ep else None,
                "nota": "turno guardado en el crudo" + ("" if ep else " (trivial: sin episodio)")}
    if t == "olvidar":
        kind, target = d.get("kind"), _text(d, "id", 200)
        if kind == "episodio":
            return {"olvidado": brain.forget_episode(target), "kind": kind, "id": target}
        if kind == "nota":
            if not NOTE_ID.match(target):
                raise ActionError("id de nota inválido")
            try:
                brain.delete_note(target)
            except FileNotFoundError as exc:
                raise ActionError(str(exc)) from None
            return {"olvidado": True, "kind": kind, "id": target}
        raise ActionError("'kind' tiene que ser 'episodio' o 'nota'")
    if t == "dar_feedback":
        ids = d.get("ids")
        if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids):
            raise ActionError("falta 'ids' (lista de ids de notas usadas)")
        res = brain.learning.outcome(ids[:50], d.get("signals") or {}, str(d.get("situacion") or "recall"))
        if d.get("paso"):
            res["transiciones"] = brain.learning.step(ids[:50])
        return res
    if t == "exportar_vault":
        dest = _text(d, "destino", 500)
        return {"exportado": str(brain.vault.export_zip(dest))}
    raise ActionError(f"memoria no ejecuta '{t}'")


def request(ctx, action_type: str, data: dict, summary: str, origin: Origin = Origin.OWNER) -> dict:
    """Pide una acción por el harness (que aplica el nivel del manifiesto) y devuelve estado + resultado."""
    res = ctx.request(Action(action_type, data, summary, origin=origin))
    out = {"estado": res.get("state")}
    if res.get("state") == "executed":
        out["resultado"] = ctx.shared.get("resultados", action_type)
    elif res.get("state") == "error":
        out["error"] = res.get("error")
    else:
        out.update({k: v for k, v in res.items() if k != "state"})
    return out


def execute(ctx, action: Action) -> str | None:
    """`Cook.execute` de todos los cocineros: corre la acción, guarda su resultado y la anota en el feed de actividad."""
    brain = Brain.from_ctx(ctx)
    result = run(brain, action)
    ctx.shared.put("resultados", action.type, result)
    log_activity(ctx, action.type, action.summary or action.type, result)
    return action.summary or action.type


def log_activity(ctx, kind: str, detail: str, meta: dict | None = None, cap: int = 200) -> None:
    """El feed «lo que hizo solo»: lo más nuevo primero, con tope."""
    items = (ctx.shared.get("estado", "actividad") or {}).get("items", [])
    items.insert(0, {"accion": kind, "detalle": detail[:400], "meta": meta or {}, "at": ctx.now().isoformat(timespec="seconds")})
    ctx.shared.put("estado", "actividad", {"items": items[:cap]})
