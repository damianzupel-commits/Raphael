"""Canal de Meta: WhatsApp Cloud API e Instagram (mensajes directos). Entrada por webhook, salida por la Graph API.

Fuente revisada el 23 nov 2026 (developers.facebook.com):
  - Versión vigente de la Graph API: v26.0 (29 jul 2026). Configurable con META_GRAPH_VERSION.
  - WhatsApp: POST https://graph.facebook.com/<versión>/<PHONE_NUMBER_ID>/messages
    {"messaging_product": "whatsapp", "recipient_type": "individual", "to": ..., "type": "text", "text": {"body": ...}}
    cuerpo de hasta 4096 caracteres. Texto libre solo dentro de la ventana de atención (24 h desde el último mensaje del
    cliente); afuera hacen falta plantillas aprobadas -> no se manda y se le avisa a la dueña.
  - Instagram API with Instagram Login (cuenta profesional sin página de Facebook): POST
    https://graph.instagram.com/<versión>/me/messages {"recipient": {"id": IGSID}, "message": {"text": ...}} con el token de
    usuario de Instagram; texto de hasta 1000 bytes. Con META_IG_HOST=graph.facebook.com se usa la variante con página.
  - Webhooks: verificación GET con hub.mode=subscribe, hub.verify_token y hub.challenge; POST firmado con
    X-Hub-Signature-256 = sha256=HMAC(app secret, cuerpo crudo).
No se probó contra la API real (no hay cuentas todavía): está probado con respuestas falsas. Pendiente para 04: las cuentas.

Modo `mock` (por defecto): no sale nada a internet; lo que se mandaría queda en `sent` (para probar). Modo `real`: sale.
Los tokens se leen de variables de entorno (el archivo `meta.env` del servidor); nunca se escriben en logs.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import queue
import threading
from collections import OrderedDict, deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

log = logging.getLogger("raphael.meta")

GRAPH_VERSION = "v26.0"
WA_MAX = 4096
IG_MAX_BYTES = 1000
WINDOW = timedelta(hours=24)

#: (url, cuerpo json, headers) -> respuesta json; lo cambian los tests
Transport = Callable[[str, dict, dict], dict]


@dataclass(frozen=True)
class MetaSettings:
    mode: str = "mock"                 # mock | real
    verify_token: str = ""
    app_secret: str = ""
    wa_token: str = ""
    wa_phone_id: str = ""
    ig_token: str = ""
    ig_host: str = "graph.instagram.com"
    graph_version: str = GRAPH_VERSION

    @property
    def real(self) -> bool:
        return self.mode == "real"

    def problems(self) -> list[str]:
        """Lo que falta para el modo real (sin mostrar ningún valor)."""
        out = []
        if self.real:
            if not self.app_secret:
                out.append("falta META_APP_SECRET (sin él no se puede verificar la firma de los webhooks)")
            if not self.verify_token:
                out.append("falta META_VERIFY_TOKEN")
            if not (self.wa_token and self.wa_phone_id) and not self.ig_token:
                out.append("no hay ningún canal: faltan META_WA_TOKEN + META_WA_PHONE_ID o META_IG_TOKEN")
        return out


def settings_from_env(env: Mapping[str, str]) -> MetaSettings:
    mode = (env.get("META_MODE") or "mock").strip().lower()
    return MetaSettings(mode="real" if mode == "real" else "mock", verify_token=env.get("META_VERIFY_TOKEN", ""),
                        app_secret=env.get("META_APP_SECRET", ""), wa_token=env.get("META_WA_TOKEN", ""),
                        wa_phone_id=env.get("META_WA_PHONE_ID", ""), ig_token=env.get("META_IG_TOKEN", ""),
                        ig_host=env.get("META_IG_HOST", "graph.instagram.com") or "graph.instagram.com",
                        graph_version=env.get("META_GRAPH_VERSION", GRAPH_VERSION) or GRAPH_VERSION)


def verify_signature(secret: str, body: bytes, header: str | None) -> bool:
    if not secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header[7:], expected)


@dataclass(frozen=True)
class Incoming:
    channel: str
    sender: str
    text: str
    name: str = ""
    attachment: bool = False
    mid: str = ""


def parse_webhook(payload: dict) -> list[Incoming]:
    """Webhook de Meta -> mensajes entrantes. Ignora estados de entrega, ecos propios y lo que no tiene remitente."""
    out: list[Incoming] = []
    obj = payload.get("object")
    for entry in payload.get("entry") or []:
        if obj == "whatsapp_business_account":
            for ch in entry.get("changes") or []:
                v = ch.get("value") or {}
                names = {c.get("wa_id"): (c.get("profile") or {}).get("name", "") for c in v.get("contacts") or []}
                for m in v.get("messages") or []:
                    kind = m.get("type")
                    if kind == "text":
                        text = (m.get("text") or {}).get("body", "")
                    elif kind == "interactive":
                        it = m.get("interactive") or {}
                        text = ((it.get("button_reply") or it.get("list_reply") or {}).get("title")) or "[respuesta]"
                    elif kind == "button":
                        text = (m.get("button") or {}).get("text", "") or "[botón]"
                    else:
                        text = (m.get(kind) or {}).get("caption", "") or f"[{kind}]"
                    out.append(Incoming("whatsapp", str(m.get("from", "")), text, names.get(m.get("from"), ""),
                                        kind not in ("text", "interactive", "button"), str(m.get("id", ""))))
        elif obj == "instagram":
            for ev in entry.get("messaging") or []:
                m = ev.get("message") or {}
                if not m or m.get("is_echo") or m.get("is_deleted"):
                    continue
                att = bool(m.get("attachments"))
                out.append(Incoming("instagram", str((ev.get("sender") or {}).get("id", "")),
                                    m.get("text") or ("[adjunto]" if att else ""), "", att, str(m.get("mid", ""))))
    return [x for x in out if x.sender and (x.text or x.attachment)]


def split_text(text: str, max_chars: int = WA_MAX, max_bytes: int | None = None) -> list[str]:
    """Parte un mensaje largo en pedazos (por párrafo, después por palabra) sin pasarse del límite del canal."""
    def fits(s: str) -> bool:
        return len(s) <= max_chars and (max_bytes is None or len(s.encode("utf-8")) <= max_bytes)

    if fits(text):
        return [text]
    parts, cur = [], ""
    for word in text.replace("\n", "\n ").split(" "):
        cand = (cur + " " + word) if cur else word
        if fits(cand):
            cur = cand
            continue
        if cur:
            parts.append(cur.replace("\n ", "\n").strip())
        while not fits(word):                    # una "palabra" gigante (un link larguísimo): se corta a lo bruto
            cut = max_chars
            while max_bytes is not None and len(word[:cut].encode("utf-8")) > max_bytes:
                cut -= 1
            parts.append(word[:cut])
            word = word[cut:]
        cur = word
    if cur.strip():
        parts.append(cur.replace("\n ", "\n").strip())
    return [p for p in parts if p]


def http_post(url: str, body: dict, headers: dict) -> dict:
    import httpx

    r = httpx.post(url, json=body, headers=headers, timeout=20)
    if r.status_code >= 400:
        try:
            err = (r.json().get("error") or {}).get("message", "")
        except ValueError:
            err = ""
        raise RuntimeError(f"Meta respondió {r.status_code}{': ' + err[:160] if err else ''}")
    return r.json()


@dataclass
class Failure:
    contact: str
    text: str
    reason: str
    when: str


class Outbox:
    """Los envíos salen en un hilo aparte: una Graph API lenta o caída no frena el harness. Los que fallan quedan en
    `failures` para avisarle a la dueña (los vacía la API en su tick)."""

    def __init__(self, transport: Transport | None = None, *, threaded: bool = True) -> None:
        self.transport = transport or http_post
        self.failures: deque[Failure] = deque(maxlen=200)
        self.sent: deque[tuple[str, dict]] = deque(maxlen=200)      # lo que salió (en mock: lo que habría salido)
        self._q: queue.Queue | None = queue.Queue() if threaded else None
        if self._q is not None:
            threading.Thread(target=self._work, name="meta-outbox", daemon=True).start()

    def put(self, contact: str, url: str, body: dict, headers: dict, text: str) -> None:
        job = (contact, url, body, headers, text)
        if self._q is None:
            self._do(*job)
        else:
            self._q.put(job)

    def fail(self, contact: str, text: str, reason: str) -> None:
        self.failures.append(Failure(contact, text, reason, datetime.now().isoformat(timespec="seconds")))

    def _do(self, contact: str, url: str, body: dict, headers: dict, text: str) -> None:
        try:
            self.transport(url, body, headers)
            self.sent.append((contact, body))
        except Exception as exc:  # noqa: BLE001 - un envío fallido no tumba el servidor
            log.warning("no se pudo mandar a %s: %s", contact, type(exc).__name__)
            self.fail(contact, text, str(exc)[:200] or type(exc).__name__)

    def _work(self) -> None:
        assert self._q is not None
        while True:
            self._do(*self._q.get())
            self._q.task_done()

    def wait(self) -> None:
        if self._q is not None:
            self._q.join()


@dataclass
class MetaChannel:
    """Los dos conectores (`whatsapp`, `instagram`) para el `Runtime`, más el estado compartido del canal."""

    settings: MetaSettings
    outbox: Outbox
    last_inbound: Callable[[str], datetime | None] = field(default=lambda contact: None)
    clock: Callable[[], datetime] = datetime.now
    _seen: OrderedDict = field(default_factory=OrderedDict)
    _fixed_transport: bool = False

    @classmethod
    def build(cls, settings: MetaSettings, transport: Transport | None = None, *, threaded: bool = True) -> MetaChannel:
        mock = (lambda url, body, headers: {"mock": True}) if not settings.real else None
        ch = cls(settings, Outbox(transport or mock, threaded=threaded))
        ch._fixed_transport = transport is not None
        return ch

    def reconfigure(self, settings: MetaSettings, runtime: Any) -> None:
        """Cambio en caliente (pantalla de Configuración): modo mock/real, tokens y qué canales existen."""
        self.settings = settings
        if not self._fixed_transport:
            self.outbox.transport = http_post if settings.real else (lambda url, body, headers: {"mock": True})
        runtime.connectors.clear()
        runtime.connectors.update(self.connectors())

    def bind(self, runtime: Any) -> None:
        """Después de armar el runtime: la ventana de 24 h sale de cuándo escribió el cliente por última vez."""
        def last(contact: str) -> datetime | None:
            for c in runtime.contacts():
                if c["contact"] == contact and c.get("last"):
                    return datetime.fromisoformat(c["last"])
            return None
        self.last_inbound = last
        self.clock = runtime.clock

    def connectors(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        s = self.settings
        if s.wa_phone_id or not s.real:
            out["whatsapp"] = _WhatsApp(self)
        if s.ig_token or not s.real:
            out["instagram"] = _Instagram(self)
        return out

    def first_time(self, mid: str) -> bool:
        """Meta reintenta webhooks: el mismo mensaje no se procesa dos veces."""
        if not mid:
            return True
        if mid in self._seen:
            return False
        self._seen[mid] = True
        while len(self._seen) > 5000:
            self._seen.popitem(last=False)
        return True


class _WhatsApp:
    def __init__(self, ch: MetaChannel) -> None:
        self.ch = ch

    def send(self, recipient: str, text: str) -> None:
        s, contact = self.ch.settings, f"whatsapp:{recipient}"
        last = self.ch.last_inbound(contact)
        if last is not None and self.ch.clock() - last > WINDOW:
            self.ch.outbox.fail(contact, text, "pasaron más de 24 h desde el último mensaje del cliente: WhatsApp solo deja "
                                               "mandar plantillas aprobadas")
            return
        url = f"https://graph.facebook.com/{s.graph_version}/{s.wa_phone_id or 'mock'}/messages"
        for part in split_text(text, WA_MAX):
            body = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": recipient, "type": "text",
                    "text": {"preview_url": False, "body": part}}
            self.ch.outbox.put(contact, url, body, {"Authorization": f"Bearer {s.wa_token}"}, part)


class _Instagram:
    def __init__(self, ch: MetaChannel) -> None:
        self.ch = ch

    def send(self, recipient: str, text: str) -> None:
        s, contact = self.ch.settings, f"instagram:{recipient}"
        last = self.ch.last_inbound(contact)
        if last is not None and self.ch.clock() - last > WINDOW:
            self.ch.outbox.fail(contact, text, "pasaron más de 24 h desde el último mensaje del cliente: Instagram no deja "
                                               "escribirle sin que él escriba primero")
            return
        url = f"https://{s.ig_host}/{s.graph_version}/me/messages"
        for part in split_text(text, WA_MAX, IG_MAX_BYTES):
            body = {"recipient": {"id": recipient}, "message": {"text": part}}
            self.ch.outbox.put(contact, url, body, {"Authorization": f"Bearer {s.ig_token}"}, part)
