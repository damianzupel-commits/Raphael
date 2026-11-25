"""Memoria episódica: qué pasó, cuándo y por qué. Capturar es total y barato; destilar es selectivo.

- El historial CRUDO de cada turno se guarda siempre (colección `crudo`): nada se tira.
- El EPISODIO (resumen con disparador, acciones, desenlace, lección, momentos salientes) se arma solo si el turno fue
  sustantivo. Lo trivial queda entero en el crudo.
- Sensibilidad `tecnico` | `personal`; ante la duda, `personal` (fail-safe hacia lo privado).
- Log de solo agregar con cadena de hashes (tamper-evident): cada episodio y cada olvido deja una entrada; borrar no
  reescribe el pasado, deja constancia de que se borró (no de qué decía). Lo único que borra es `olvidar`, a pedido.

Portado de `app/memory/*` de JarvisRemote. Diferencia: el log usa SHA-256 encadenado y no firma Ed25519 (no hay
`win32crypt` ni claves en la nube); detecta manipulación pero no autoría. Anotado en el log de la brigada.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

BEAT_MARKERS = [
    ("correccion", "no, así no"), ("correccion", "no es así"), ("correccion", "está mal"), ("correccion", "esta mal"),
    ("correccion", "mejor no"), ("correccion", "cambiá"), ("decision", "dale"), ("decision", "confirmo"),
    ("decision", "vamos con"), ("decision", "elijo"), ("decision", "prefiero"), ("preferencia", "me gusta más"),
    ("descubrimiento", "resultó que"), ("descubrimiento", "resulto que"), ("descubrimiento", "descubrí"),
    ("fallo", "falló"), ("fallo", "fallo"), ("fallo", "error"), ("fallo", "no funciona"), ("fallo", "no anduvo"),
]
_FALLO = ("error", "falló", "fallo", "no funciona", "no anduvo", "exception", "traceback")
_EXITO = ("listo", "funciona", "quedó", "quedo", "resuelto", "ok", "hecho", "perfecto")
_TECNICO = ("código", "codigo", "function", "función", "funcion", "clase", "bug", "commit", "vulnerab", "cve", "semgrep",
            "bandit", "pentest", "nmap", "exploit", "malware", "yara", "escaneo", "auditor", "backend", "endpoint", "api",
            "tool", "repo", "git", "test", "pytest", "trading", "backtest", "spec", "config", "raphael", "harness",
            "brigada", "docker", "servidor", "deploy", "refactor", "traceback", "logs")
_PERSONAL = ("me siento", "mi hija", "mi familia", "mi vieja", "mi viejo", "mi mamá", "mi papá", "psicolog", "psicólog",
             "terapia", "emocion", "angustia", "ansiedad", "miedo", "sueño", "relación", "relacion", "pareja", "personal",
             "íntimo", "intimo", "infancia", "recuerdo de", "me pasa que", "no sé qué hacer con mi")
_DOMINIOS_TECNICOS = {"auditoria", "security_audit", "pentesting", "malware_protection", "trading", "datos_externos",
                      "code_delegation", "web"}


def classify(text: str, *, dominio: str = "") -> str:
    """'tecnico' solo con señal clara y sin ninguna señal personal; todo lo demás, 'personal'."""
    low = (text or "").lower()
    if any(h in low for h in _PERSONAL):
        return "personal"
    if dominio in _DOMINIOS_TECNICOS or sum(1 for h in _TECNICO if h in low) >= 2:
        return "tecnico"
    return "personal"


@dataclass
class Beat:
    kind: str
    text: str
    timestamp: str = ""


@dataclass
class Episode:
    id: str
    conv_id: str = "default"
    level: str = "tarea"
    timestamp_inicio: str = ""
    timestamp_fin: str = ""
    trigger: str = ""
    dominio: str = ""
    acciones: list[str] = field(default_factory=list)
    decisiones: list[str] = field(default_factory=list)
    resultado: str = "sin_desenlace"        # exito | fallo | parcial | sin_desenlace
    porque: str = ""
    artefactos: list[str] = field(default_factory=list)
    pendientes: list[str] = field(default_factory=list)
    salience: float = 0.0
    sensibilidad: str = "personal"
    links: list[str] = field(default_factory=list)
    beats: list[Beat] = field(default_factory=list)
    distilled_by: str = "heuristica"
    corrects: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> Episode:
        d = dict(d)
        beats = [Beat(**b) for b in d.pop("beats", [])]
        ep = Episode(**d)
        ep.beats = beats
        return ep

    def summary_line(self) -> str:
        when = self.timestamp_inicio[:16].replace("T", " ")
        return (f"[{when}] ({self.dominio or 'general'}/{self.resultado}) {self.trigger[:120]}"
                + (f" — {self.porque[:120]}" if self.porque else ""))


# --- destilar ---------------------------------------------------------------------------------------------------------
def _text(m: dict) -> str:
    c = m.get("content")
    if isinstance(c, list):
        return " ".join(p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text")
    return c if isinstance(c, str) else ""


def current_turn(history: list[dict]) -> list[dict]:
    """El turno en curso: desde el último mensaje 'user' hasta el final."""
    last_user = max((i for i, m in enumerate(history) if m.get("role") == "user"), default=None)
    return [m for m in history if m.get("role") != "system"] if last_user is None else history[last_user:]


def is_substantive(turn: list[dict]) -> bool:
    return any(m.get("tool_calls") for m in turn) or len(" ".join(_text(m) for m in turn).strip()) >= 400


def _outcome(turn: list[dict]) -> str:
    last = next((_text(m) for m in reversed(turn) if m.get("role") == "assistant" and _text(m).strip()), "").lower()
    allt = " ".join(_text(m) for m in turn).lower()
    if any(h in last for h in _EXITO):
        return "exito"
    if any(h in allt for h in _FALLO):
        return "fallo" if any(h in last for h in _FALLO) else "parcial"
    return "sin_desenlace"


def _salience(ep: Episode) -> float:
    s = 0.15 + min(0.4, 0.1 * len(ep.beats)) + min(0.25, 0.05 * len(ep.acciones))
    if ep.resultado in ("fallo", "exito"):
        s += 0.2
    if ep.pendientes:
        s += 0.1
    return round(min(1.0, s), 3)


def distill(turn: list[dict], *, conv_id: str, dominio: str, sensibilidad: str, ts_inicio: str, ts_fin: str,
            ai=None) -> Episode:
    """Heurística siempre; con `ai` (modelo PRIVADO, local) mejora la lección. Si el modelo falla, queda la heurística."""
    beats = []
    for m in turn:
        if m.get("role") != "user":
            continue
        low = _text(m).lower()
        for kind, marker in BEAT_MARKERS:
            if marker in low:
                beats.append(Beat(kind, _text(m).strip()[:200], ts_fin))
                break
    tools: list[str] = []
    for m in turn:
        for tc in m.get("tool_calls") or []:
            fn = (tc.get("function") or {}).get("name")
            if fn and fn not in tools:
                tools.append(fn)
    ep = Episode(id=uuid.uuid4().hex[:16], conv_id=conv_id, timestamp_inicio=ts_inicio, timestamp_fin=ts_fin,
                 trigger=next((_text(m) for m in turn if m.get("role") == "user"), "").strip()[:400], dominio=dominio,
                 acciones=tools, beats=beats, sensibilidad=sensibilidad, resultado=_outcome(turn))
    ep.decisiones = [f"{b.kind}: {b.text}" for b in beats if b.kind in ("decision", "correccion", "preferencia")]
    ep.porque = next((_text(m) for m in reversed(turn) if m.get("role") == "assistant" and _text(m).strip()), "").strip()[:400]
    ep.salience = _salience(ep)
    if ai is not None:
        try:
            raw = ai([{"role": "system", "content": "Resumí en UNA oración, en español, la lección o el porqué de esta "
                                                    "tarea. Solo el texto, sin inventar datos que no estén."},
                      {"role": "user", "content": "\n".join(f"{m.get('role')}: {_text(m)[:600]}" for m in turn)[:3000]}])
            if raw and raw.strip():
                ep.porque, ep.distilled_by = raw.strip()[:400], "modelo-local"
        except Exception:  # noqa: BLE001 - un modelo caído nunca rompe la captura
            pass
    return ep


# --- guardar ---------------------------------------------------------------------------------------------------------
class EpisodeStore:
    """Episodios, crudo y log encadenado en el espacio de la brigada."""

    def __init__(self, space: Any, now, mirror=None) -> None:
        self.space = space
        self._now = now
        self._mirror = mirror        # función (Episode) -> None que espeja el episodio como nota (o None)

    # log encadenado
    def _log(self, op: str, payload: dict) -> dict:
        seq = self.space.next("registro_seq")
        prev = (self.space.get("registro", f"{seq - 1:08d}") or {}).get("hash", "") if seq > 1 else ""
        body = {"seq": seq, "op": op, "payload": payload, "at": self._now().isoformat(timespec="seconds"), "prev": prev}
        body["hash"] = hashlib.sha256((prev + json.dumps({k: body[k] for k in ("seq", "op", "payload", "at")},
                                                         sort_keys=True, ensure_ascii=False)).encode()).hexdigest()
        self.space.put("registro", f"{seq:08d}", body)
        return body

    def verify(self) -> dict:
        prev, n = "", 0
        for e in self.space.list("registro"):
            want = hashlib.sha256((prev + json.dumps({k: e[k] for k in ("seq", "op", "payload", "at")},
                                                     sort_keys=True, ensure_ascii=False)).encode()).hexdigest()
            if e.get("prev") != prev or e.get("hash") != want:
                return {"ok": False, "entries_checked": n, "broken_at_seq": e.get("seq"),
                        "reason": "la cadena de hashes no coincide"}
            prev, n = e["hash"], n + 1
        return {"ok": True, "entries_checked": n, "broken_at_seq": None, "reason": ""}

    # episodios
    def save_raw(self, conv_id: str, turn: list[dict]) -> str:
        key = f"{self._now().strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:6]}"
        stamp = self._now().isoformat(timespec="seconds")
        self.space.put("crudo", key, {"conv": conv_id, "mensajes": [
            {"role": m.get("role", "?"), "content": _text(m), "timestamp": stamp, "index": i} for i, m in enumerate(turn)]})
        return key

    def save(self, ep: Episode) -> None:
        self.space.put("episodios", ep.id, ep.to_dict())
        self._log("episodio", {"id": ep.id, "dominio": ep.dominio, "resultado": ep.resultado,
                               "sensibilidad": ep.sensibilidad, "inicio": ep.timestamp_inicio, "salience": ep.salience})
        if self._mirror:
            self._mirror(ep)

    def get(self, episode_id: str) -> Episode | None:
        d = self.space.get("episodios", episode_id)
        return Episode.from_dict(d) if d else None

    def list(self) -> list[Episode]:
        eps = [Episode.from_dict(d) for d in self.space.list("episodios")]
        eps.sort(key=lambda e: e.timestamp_inicio, reverse=True)
        return eps

    def forget(self, episode_id: str) -> bool:
        existed = self.space.delete("episodios", episode_id)
        self._log("olvidar", {"id": episode_id, "existia": existed})
        return existed

    # capturar al cierre de un turno
    def capture(self, conv_id: str, history: list[dict], *, dominio: str = "", ai=None) -> Episode | None:
        """Guarda el crudo SIEMPRE; arma el episodio solo si el turno fue sustantivo. Nunca levanta."""
        try:
            turn = current_turn(history)
            if not turn:
                return None
            t0 = self._now().isoformat(timespec="seconds")
            self.save_raw(conv_id, turn)
            if not is_substantive(turn):
                return None
            allt = " ".join(_text(m) for m in turn)
            ep = distill(turn, conv_id=conv_id, dominio=dominio, sensibilidad=classify(allt, dominio=dominio),
                         ts_inicio=t0, ts_fin=self._now().isoformat(timespec="seconds"), ai=ai)
            self.save(ep)
            return ep
        except Exception:  # noqa: BLE001 - la memoria NUNCA rompe un turno
            return None


# --- recordar ---------------------------------------------------------------------------------------------------------
def _within(ep: Episode, hours: int, now: datetime) -> bool:
    try:
        t = datetime.fromisoformat(ep.timestamp_inicio)
    except ValueError:
        return False
    t = t if t.tzinfo else t.replace(tzinfo=UTC)
    now = now if now.tzinfo else now.replace(tzinfo=UTC)
    return t >= now - timedelta(hours=hours)


def recall_auto(eps: list[Episode], now: datetime, *, hours: int = 24, max_items: int = 12,
                include_personal: bool = True) -> list[Episode]:
    """Últimas `hours` horas + los más salientes fuera de la ventana. Sin `include_personal`, los `personal` se filtran
    (para cualquier prompt que pueda salir de la PC)."""
    if not include_personal:
        eps = [e for e in eps if e.sensibilidad != "personal"]
    recent = [e for e in eps if _within(e, hours, now)]
    older = sorted((e for e in eps if not _within(e, hours, now)), key=lambda e: e.salience, reverse=True)
    return (recent + older[: max(0, max_items - len(recent))])[:max_items]


def recall_query(eps: list[Episode], tema: str, max_items: int = 8) -> list[Episode]:
    """Por tema (palabras en disparador, lección, dominio, acciones y momentos). Entra solo lo que nombra el tema: la
    saliencia ordena pero no alcanza para entrar (en JarvisRemote entraba todo lo que tuviera saliencia)."""
    q = (tema or "").lower().strip()
    if not q:
        return eps[:max_items]
    scored = []
    for e in eps:
        blob = " ".join([e.trigger, e.porque, e.dominio, " ".join(e.acciones), " ".join(b.text for b in e.beats)]).lower()
        hits = sum(blob.count(w) for w in q.split() if w)
        if hits:
            scored.append((hits + e.salience, e))
    scored.sort(key=lambda x: (x[0], x[1].timestamp_inicio), reverse=True)
    return [e for _, e in scored[:max_items]]


def render(eps: list[Episode]) -> str:
    return "\n".join(f"- {e.summary_line()} · id:{e.id}" for e in eps) if eps else "No hay recuerdos que traer."
