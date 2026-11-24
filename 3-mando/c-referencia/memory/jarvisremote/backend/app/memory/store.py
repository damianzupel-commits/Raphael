"""Store de la memoria episódica (§8/§10 del spec).

Tres cosas por episodio:
1. **JSON** del episodio en `data/episodic_memory/episodes/<id>.json`.
2. **Log append-only firmado** (Ed25519 + hash-chain): se REUSA el módulo ya
   probado `investigation/log.py` con un log propio de la memoria y la MISMA
   clave (`investigation_keys_dir`). Cada episodio deja una entrada firmada →
   la autobiografía de Raphael queda tamper-evident. Ningún borrado reescribe
   el pasado: `memoria_olvidar` borra el JSON pero deja en el log que se borró.
3. **Espejo en el grafo**: una nota Markdown en el vault (Vault-Fenix), para que
   el episodio se conecte con el resto del conocimiento (mismo grafo, Decisión C).

La capa CRUDA (B): el historial completo del turno se guarda aparte en
`data/episodic_memory/raw/<conv>/<ts>.jsonl` con timestamp por mensaje. Nada se
tira (Decisión 7): el único borrado es el explícito de Damian.

Todo defensivo: si falta win32crypt (no-Windows) o el vault, se degrada con un
aviso, nunca rompe.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import settings
from .schema import Episode, RawMessage

logger = logging.getLogger("jarvis.memory")


def _base() -> Path:
    return Path(settings.episodic_memory_dir)


def _episodes_dir() -> Path:
    return _base() / "episodes"


def _raw_dir() -> Path:
    return _base() / "raw"


def _log_path() -> Path:
    return _base() / "memory_log.jsonl"


def _mirror_dir() -> Path | None:
    """Carpeta del espejo en el grafo (vault). None si no hay vault configurado."""
    vault = getattr(settings, "obsidian_vault_path", "") or ""
    if not vault:
        return None
    return Path(vault) / "12-Memoria-Raphael"


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------


def _sign_log(op: str, payload: dict) -> None:
    """Entrada firmada en el log de memoria (reusa investigation/log.py + la
    misma clave). Best-effort: si falta win32crypt, no rompe la captura."""
    try:
        from ..investigation import log as inv_log
        inv_log.append_entry(_log_path(), settings.investigation_keys_dir, op, payload)
    except Exception as exc:  # noqa: BLE001
        logger.warning("no pude firmar la entrada de memoria (%s): %r", op, exc)


def _mirror_markdown(ep: Episode) -> None:
    mdir = _mirror_dir()
    if mdir is None:
        return
    try:
        mdir.mkdir(parents=True, exist_ok=True)
        links = "".join(f"\n- [[{l}]]" for l in ep.links)
        beats = "".join(f"\n- **{b.kind}**: {b.text}" for b in ep.beats)
        body = (
            f"---\n"
            f"id: {ep.id}\n"
            f"tipo: episodio\n"
            f"nivel: {ep.level}\n"
            f"dominio: {ep.dominio}\n"
            f"resultado: {ep.resultado}\n"
            f"sensibilidad: {ep.sensibilidad}\n"
            f"salience: {ep.salience}\n"
            f"inicio: {ep.timestamp_inicio}\n"
            f"fin: {ep.timestamp_fin}\n"
            f"---\n\n"
            f"# Episodio {ep.id}\n\n"
            f"**Disparador:** {ep.trigger}\n\n"
            f"**Acciones:** {', '.join(ep.acciones) or '—'}\n\n"
            f"**Resultado:** {ep.resultado}\n\n"
            f"**Por qué / lección:** {ep.porque or '—'}\n\n"
            f"**Momentos:**{beats or ' —'}\n\n"
            f"**Pendientes:** {', '.join(ep.pendientes) or '—'}\n\n"
            f"**Relacionado:**{links or ' —'}\n"
        )
        (mdir / f"{ep.id}.md").write_text(body, encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        logger.warning("no pude espejar el episodio %s al grafo: %r", ep.id, exc)


def save_episode(ep: Episode) -> None:
    """Persiste el episodio (JSON + log firmado + espejo). Defensivo."""
    _episodes_dir().mkdir(parents=True, exist_ok=True)
    try:
        (_episodes_dir() / f"{ep.id}.json").write_text(
            json.dumps(ep.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("no pude guardar el episodio %s: %r", ep.id, exc)
        return
    _sign_log("episode", {"id": ep.id, "level": ep.level, "dominio": ep.dominio,
                          "resultado": ep.resultado, "sensibilidad": ep.sensibilidad,
                          "inicio": ep.timestamp_inicio, "salience": ep.salience})
    _mirror_markdown(ep)


def save_raw(conv_id: str, messages: list[RawMessage]) -> str | None:
    """Guarda el historial crudo del turno (capa B). Devuelve la ruta o None."""
    if not messages:
        return None
    folder = _raw_dir() / conv_id
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    path = folder / f"{stamp}.jsonl"
    try:
        with path.open("w", encoding="utf-8") as f:
            for m in messages:
                f.write(json.dumps(m.to_dict(), ensure_ascii=False) + "\n")
        return str(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("no pude guardar el crudo de %s: %r", conv_id, exc)
        return None


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------


def get_episode(episode_id: str) -> Episode | None:
    p = _episodes_dir() / f"{episode_id}.json"
    if not p.is_file():
        return None
    try:
        return Episode.from_dict(json.loads(p.read_text(encoding="utf-8")))
    except Exception:  # noqa: BLE001
        return None


def list_episodes() -> list[Episode]:
    """Todos los episodios, más nuevo primero."""
    d = _episodes_dir()
    if not d.is_dir():
        return []
    eps: list[Episode] = []
    for p in d.glob("*.json"):
        try:
            eps.append(Episode.from_dict(json.loads(p.read_text(encoding="utf-8"))))
        except Exception:  # noqa: BLE001
            continue
    eps.sort(key=lambda e: e.timestamp_inicio, reverse=True)
    return eps


# ---------------------------------------------------------------------------
# Borrado (el ÚNICO borrado real — explícito de Damian, Decisión 7/§9)
# ---------------------------------------------------------------------------


def forget_episode(episode_id: str) -> bool:
    """Borra el JSON del episodio y su espejo. Deja en el log FIRMADO que se
    borró (no qué decía). El sistema jamás borra solo; esto solo lo llama la
    tool `memoria_olvidar` a pedido de Damian."""
    p = _episodes_dir() / f"{episode_id}.json"
    existed = p.is_file()
    try:
        p.unlink(missing_ok=True)
        mdir = _mirror_dir()
        if mdir is not None:
            (mdir / f"{episode_id}.md").unlink(missing_ok=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("no pude borrar el episodio %s: %r", episode_id, exc)
        return False
    _sign_log("olvidar", {"id": episode_id, "existia": existed})
    return existed


def verify_integrity() -> dict:
    """Verifica el log firmado de la memoria (tamper-evidence)."""
    try:
        from ..investigation import log as inv_log
        res = inv_log.verify_chain(_log_path(), settings.investigation_keys_dir)
        return {"ok": res.ok, "entries_checked": res.entries_checked,
                "broken_at_seq": res.broken_at_seq, "reason": res.reason}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": f"no pude verificar: {exc!r}"}
