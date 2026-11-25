"""Ingesta de artefactos: chats (WhatsApp .txt, Telegram .json), CSV, logs de servidor (Apache/Nginx y auth.log de SSH),
documentos (txt, md, pdf, docx) e imágenes (EXIF).

Todo determinístico: ningún modelo en el medio. Cada artefacto se registra con su sha256 y todo lo que sale de él cuelga
de ese hash. Reingestar el mismo archivo no duplica nada. Lo que no se entiende se rechaza o se anota; no se inventa.
Los textos de terceros son DATO: se guardan, no se obedecen.
"""

from __future__ import annotations

import csv
import io
import json
import mimetypes
import re
from pathlib import Path
from typing import Any

from .casefile import CaseError, Cases, sha256_bytes
from .model import EdgeType, NodeType, make_edge, make_node
from .timeline import normalize_timestamp

MAX_DESC = 2000
MAX_MESSAGES = 20000
MAX_ROWS = 20000


# --- detección --------------------------------------------------------------------------------------------------------------
_WA = (
    re.compile(r"^\[(?P<f>\d{1,2}/\d{1,2}/\d{2,4}),\s*(?P<h>\d{1,2}:\d{2}(?::\d{2})?)\]\s*(?P<s>[^:]+):\s(?P<t>.*)$"),
    re.compile(r"^(?P<f>\d{1,2}/\d{1,2}/\d{2,4}),\s*(?P<h>\d{1,2}:\d{2}(?::\d{2})?)\s*[-–]\s*(?P<s>[^:]+):\s(?P<t>.*)$"),
)
_APACHE = re.compile(r'^(?P<ip>\S+) \S+ \S+ \[(?P<f>[^\]]+)\] "(?P<m>\S+) (?P<p>\S+)(?: \S+)?" (?P<st>\d{3}) (?P<sz>\S+)')
_SSH = re.compile(r"^(?P<f>\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+\S+\s+sshd\[\d+\]:\s+"
                  r"(?P<r>Failed password|Accepted password|Invalid user)\s+(?:for\s+)?(?:invalid user\s+)?(?P<u>\S+)\s+"
                  r"from\s+(?P<ip>\S+)\s+port\s+(?P<port>\d+)")


def _ratio(lines: list[str], pats: tuple[re.Pattern, ...]) -> float:
    rows = [ln for ln in lines if ln.strip()][:200]
    return sum(1 for ln in rows if any(p.match(ln) for p in pats)) / len(rows) if rows else 0.0


def detect_kind(name: str, data: bytes) -> str:
    ext = Path(name).suffix.lower()
    if ext in (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".heic"):
        return "imagen"
    if ext == ".pdf":
        return "pdf"
    if ext == ".docx":
        return "docx"
    text = data[:200_000].decode("utf-8", errors="replace")
    if ext == ".json":
        try:
            doc = json.loads(data.decode("utf-8", errors="replace"))
        except ValueError as exc:
            raise CaseError(f"'{name}' no es un JSON válido: {exc}") from None
        if isinstance(doc, dict) and isinstance(doc.get("messages"), list):
            return "telegram"
        raise CaseError(f"'{name}': JSON que no es un export de Telegram (no tiene 'messages'); no adivino su estructura")
    lines = text.splitlines()
    if _ratio(lines, _WA) >= 0.5:
        return "whatsapp"
    if _ratio(lines, (_APACHE,)) >= 0.5:
        return "log-web"
    if _ratio(lines, (_SSH,)) >= 0.5:
        return "log-ssh"
    if ext in (".csv", ".tsv"):
        return "csv"
    if ext in (".txt", ".md", ".log", ""):
        return "texto"
    raise CaseError(f"no sé qué es '{name}' (extensión {ext or 'ninguna'}): ingestá chats, CSV, logs, documentos o imágenes")


# --- el flujo común -----------------------------------------------------------------------------------------------------------
class Ingestor:
    def __init__(self, cases: Cases) -> None:
        self.c = cases

    def ingest_path(self, case: str, path: str, *, kind: str | None = None, mapping: dict | None = None,
                    by: str = "persona") -> dict:
        p = Path(path)
        if not p.is_file():
            raise CaseError(f"no encuentro el archivo: {path}")
        return self.ingest_bytes(case, p.name, p.read_bytes(), kind=kind, mapping=mapping, by=by)

    def ingest_bytes(self, case: str, name: str, data: bytes, *, kind: str | None = None, mapping: dict | None = None,
                     by: str = "persona") -> dict:
        self.c.get(case)
        kind = kind or detect_kind(name, data)
        text = ""
        if kind in ("pdf", "docx"):
            text = _extract_document(kind, data, name)         # antes de registrar: si falta la librería, no queda a medias
        elif kind != "imagen":
            text = data.decode("utf-8", errors="replace")
        art = self.c.add_artifact(case, name, data, mimetypes.guess_type(name)[0] or "application/octet-stream", text=text, by=by)
        out: dict[str, Any] = {"sha256": art["sha256"], "name": name, "kind": kind, "nodes_new": 0, "edges_new": 0,
                               "warnings": [], "already": art["already"]}
        if art["already"]:
            out["warnings"].append("este artefacto ya estaba en el caso: no se duplicó nada")
            return out
        handler = {"whatsapp": self._whatsapp, "telegram": self._telegram, "csv": self._csv, "log-web": self._weblog,
                   "log-ssh": self._sshlog, "texto": self._doc, "pdf": self._doc, "docx": self._doc,
                   "imagen": self._image}.get(kind)
        if handler is None:
            raise CaseError(f"tipo de artefacto desconocido: {kind}")
        handler(case, art, data, text, mapping, out)
        self.c.log(case, "ingesta_completa", {"sha256": art["sha256"], "kind": kind, "nodes": out["nodes_new"],
                                               "edges": out["edges_new"]}, by)
        self.c.env.event("caso.actualizado", {"case": case, "op": "ingesta", "sha256": art["sha256"], "kind": kind})
        return out

    # --- helpers
    def _node(self, case: str, out: dict, node: dict) -> dict:
        doc, created = self.c.add_node(case, node, log=False)
        out["nodes_new"] += int(created)
        return doc

    def _edge(self, case: str, out: dict, tipo: EdgeType, src: str, dst: str, art: dict, detalle: str = "") -> None:
        _, created = self.c.add_edge(case, make_edge(tipo, src, dst, artefacto_origen=art["sha256"], detalle=detalle), log=False)
        out["edges_new"] += int(created)

    def _event(self, case: str, out: dict, art: dict, key: str, raw_ts: str, desc: str,
               extra: dict | None = None) -> dict | None:
        ts, notes = normalize_timestamp(raw_ts)
        if ts is None:
            out["warnings"].append(f"evento sin fecha usable ({notes[0]}): se omitió")
            return None
        campos = {"timestamp_utc": ts, "descripcion": desc[:MAX_DESC], "fuente": art["sha256"], "notas_fecha": notes,
                  **(extra or {})}
        ev = self._node(case, out, make_node(NodeType.EVENTO, campos, key=f"{art['sha256']}:{key}"))
        self._edge(case, out, EdgeType.APARECE_EN, ev["id"], art["node"], art)
        return ev

    # --- chats
    def _messages(self, case: str, art: dict, msgs: list[dict], scope: str, out: dict) -> None:
        if len(msgs) > MAX_MESSAGES:
            out["warnings"].append(f"el chat tiene {len(msgs)} mensajes: se ingestaron los primeros {MAX_MESSAGES}")
            msgs = msgs[:MAX_MESSAGES]
        for i, m in enumerate(msgs):
            if m["sender_id"]:
                who = self._node(case, out, make_node(NodeType.CUENTA, {"plataforma": m["platform"],
                                                                       "handle": str(m["sender_id"]),
                                                                       "nombre_visible": m["sender"]}))
            else:
                who = self._node(case, out, make_node(NodeType.PERSONA, {"etiqueta": m["sender"], "alias": [m["sender"]],
                                                                        "confianza": 0.5}, key=f"{scope}:{m['sender']}"))
            digest = sha256_bytes(f"{i}|{m['ts']}|{m['sender']}|{m['text']}".encode())[:10]
            ev = self._event(case, out, art, f"{scope}:{digest}", m["ts"], f"{m['sender']}: {m['text']}",
                             {"canal": m["platform"]})
            if ev:
                self._edge(case, out, EdgeType.APARECE_EN, who["id"], ev["id"], art)

    def _whatsapp(self, case, art, data, text, mapping, out) -> None:
        msgs: list[dict] = []
        for line in text.splitlines():
            hit = _WA[0].match(line) or _WA[1].match(line)
            if hit:
                msgs.append({"ts": f"{hit['f']} {hit['h']}", "sender": hit["s"].strip(), "sender_id": None,
                             "text": hit["t"], "platform": "whatsapp"})
            elif msgs:
                msgs[-1]["text"] += "\n" + line    # continuación de un mensaje multilínea
        if not msgs:
            raise CaseError("no encontré mensajes de WhatsApp en el archivo")
        out["warnings"].append("WhatsApp no trae id de conversación: re-exportar el mismo chat con mensajes nuevos "
                               "duplica los viejos")
        self._messages(case, art, msgs, art["sha256"], out)

    def _telegram(self, case, art, data, text, mapping, out) -> None:
        doc = json.loads(text)
        msgs = []
        for m in doc.get("messages") or []:
            if not isinstance(m, dict) or m.get("type") != "message" or not (m.get("from") or m.get("actor")):
                continue
            body = m.get("text")
            if isinstance(body, list):
                body = "".join(x if isinstance(x, str) else str(x.get("text", "")) for x in body)
            msgs.append({"ts": str(m.get("date") or ""), "sender": m.get("from") or m.get("actor"),
                         "sender_id": m.get("from_id") or m.get("actor_id"), "text": body or "", "platform": "telegram"})
        if not msgs:
            raise CaseError("el export de Telegram no tiene mensajes")
        self._messages(case, art, msgs, f"tg{doc.get('id', art['sha256'][:12])}", out)

    # --- CSV
    _SYN = {
        "timestamp": ("timestamp", "fecha", "fecha_hora", "date", "datetime", "hora", "momento"),
        "descripcion": ("descripcion", "detalle", "mensaje", "description", "evento", "concepto", "texto"),
        "monto": ("monto", "importe", "amount", "valor"),
        "contraparte": ("contraparte", "destinatario", "beneficiario", "counterparty", "destino"),
        "tipo": ("tipo", "tipo_transaccion", "type"),
        "host": ("ip", "ip_origen", "dominio", "host", "ip_o_dominio"),
        "persona": ("nombre", "persona", "name", "titular"),
        "handle": ("handle", "usuario", "user", "cuenta"),
        "plataforma": ("plataforma", "platform", "red"),
    }

    @staticmethod
    def _norm(h: str) -> str:
        plain = h.strip().lower().translate(str.maketrans("áéíóúñ", "aeioun"))
        return re.sub(r"[^a-z0-9_]+", "_", plain).strip("_")

    def _csv(self, case, art, data, text, mapping, out) -> None:
        head = text[:4096]
        delim = max(",;\t", key=head.count)
        rows = list(csv.DictReader(io.StringIO(text), delimiter=delim))
        if not rows:
            raise CaseError("el CSV no tiene filas")
        cols = {self._norm(h): h for h in rows[0] if h}
        pick = {k: next((cols[s] for s in syn if s in cols), None) for k, syn in self._SYN.items()}
        for k, v in ((mapping or {}).get("columns") or {}).items():
            if v not in rows[0]:
                raise CaseError(f"el mapeo pide la columna '{v}', que no existe. Columnas: {list(rows[0])}")
            pick[k] = v
        tipo = (mapping or {}).get("tipo") or (
            "Transacción" if pick["monto"] and pick["contraparte"] else
            "Evento" if pick["timestamp"] and pick["descripcion"] else
            "Cuenta" if pick["handle"] and pick["plataforma"] else
            "Host" if pick["host"] else "Persona" if pick["persona"] else None)
        if tipo is None:
            raise CaseError(f"no reconozco las columnas {list(rows[0])}: pasá un mapeo (tipo y columnas) en vez de que lo adivine")
        if len(rows) > MAX_ROWS:
            out["warnings"].append(f"el CSV tiene {len(rows)} filas: se ingestaron las primeras {MAX_ROWS}")
            rows = rows[:MAX_ROWS]
        for i, r in enumerate(rows):
            def g(k: str, r: dict = r) -> str:
                return (r.get(pick[k] or "") or "").strip()
            key = f"{art['sha256']}:{i}"
            if tipo == "Evento":
                self._event(case, out, art, f"fila{i}", g("timestamp"), g("descripcion"))
                continue
            if tipo == "Transacción":
                ts, _ = normalize_timestamp(g("timestamp"))
                raw = g("monto")
                try:
                    monto = float(raw.replace(".", "").replace(",", ".")) if "," in raw else float(raw)
                except ValueError:
                    out["warnings"].append(f"fila {i + 2}: monto no numérico {raw!r}, se omitió")
                    continue
                node = make_node(NodeType.TRANSACCION, {"tipo_transaccion": g("tipo") or "transferencia", "monto": monto,
                                                         "timestamp": ts or "", "contraparte": g("contraparte")}, key=key)
            elif tipo == "Cuenta":
                node = make_node(NodeType.CUENTA, {"plataforma": g("plataforma"), "handle": g("handle")})
            elif tipo == "Host":
                node = make_node(NodeType.HOST, {"ip_o_dominio": g("host")})
            else:
                node = make_node(NodeType.PERSONA, {"etiqueta": g("persona"), "alias": [g("persona")], "confianza": 0.5},
                                 key=key)
            n = self._node(case, out, node)
            self._edge(case, out, EdgeType.APARECE_EN, n["id"], art["node"], art, f"fila {i + 2}")

    # --- logs de servidor
    def _weblog(self, case, art, data, text, mapping, out) -> None:
        for i, line in enumerate(text.splitlines()):
            m = _APACHE.match(line)
            if not m:
                continue
            host = self._node(case, out, make_node(NodeType.HOST, {"ip_o_dominio": m["ip"]}))
            ev = self._event(case, out, art, f"l{i}", m["f"], f"{m['ip']} {m['m']} {m['p']} -> {m['st']}",
                             {"http_status": int(m["st"]), "metodo": m["m"], "ruta": m["p"][:300]})
            self._edge(case, out, EdgeType.APARECE_EN, host["id"], art["node"], art)
            if ev:
                self._edge(case, out, EdgeType.APARECE_EN, host["id"], ev["id"], art)

    def _sshlog(self, case, art, data, text, mapping, out) -> None:
        out["warnings"].append("auth.log no trae año: se asumió el año actual")
        for i, line in enumerate(text.splitlines()):
            m = _SSH.match(line)
            if not m:
                continue
            host = self._node(case, out, make_node(NodeType.HOST, {"ip_o_dominio": m["ip"]}))
            acct = self._node(case, out, make_node(NodeType.CUENTA, {"plataforma": "ssh", "handle": f"{m['ip']}:{m['u']}"}))
            ev = self._event(case, out, art, f"l{i}", m["f"], f"ssh {m['r']} usuario {m['u']} desde {m['ip']}:{m['port']}",
                             {"resultado": m["r"]})
            self._edge(case, out, EdgeType.USA, acct["id"], host["id"], art)
            if ev:
                self._edge(case, out, EdgeType.APARECE_EN, host["id"], ev["id"], art)

    # --- documentos e imágenes
    def _doc(self, case, art, data, text, mapping, out) -> None:
        if not text.strip():
            out["warnings"].append("el documento no tiene texto extraíble (¿es un escaneo?): no se hace OCR")
        out["chars"] = len(text)

    def _image(self, case, art, data, text, mapping, out) -> None:
        info = read_exif(data)
        out["exif"] = info
        if not info:
            out["warnings"].append("la imagen no trae EXIF (o falta instalar Pillow)")
            return
        if info.get("fecha"):
            extra: dict[str, Any] = {k: v for k, v in info.items() if k in ("gps", "marca", "modelo")}
            self._event(case, out, art, "exif", info["fecha"], f"foto tomada ({art['name']})", extra)
        if info.get("marca") or info.get("modelo"):
            ident = " ".join(x for x in (info.get("marca"), info.get("modelo")) if x)
            dev = self._node(case, out, make_node(NodeType.DISPOSITIVO,
                                                  {"tipo_dispositivo": "camara", "identificadores": [ident]},
                                                  key=f"{ident}:{art['sha256']}"))
            self._edge(case, out, EdgeType.APARECE_EN, dev["id"], art["node"], art)


def _extract_document(kind: str, data: bytes, name: str) -> str:
    if kind == "pdf":
        try:
            import pypdf
        except ImportError:
            raise CaseError("para leer PDFs falta instalar `pypdf` (pip install pypdf)") from None
        try:
            return "\n".join((pg.extract_text() or "") for pg in pypdf.PdfReader(io.BytesIO(data)).pages)
        except Exception as exc:  # noqa: BLE001 - un PDF roto es un archivo malo, no una caída
            raise CaseError(f"'{name}' no se pudo leer como PDF ({type(exc).__name__})") from None
    try:
        import docx
    except ImportError:
        raise CaseError("para leer .docx falta instalar `python-docx` (pip install python-docx)") from None
    try:
        return "\n".join(p.text for p in docx.Document(io.BytesIO(data)).paragraphs)
    except Exception as exc:  # noqa: BLE001
        raise CaseError(f"'{name}' no se pudo leer como .docx ({type(exc).__name__})") from None


def read_exif(data: bytes) -> dict:
    """Marca, modelo, fecha y GPS del EXIF. Sin Pillow o sin EXIF devuelve {} (y el ingestor lo avisa)."""
    try:
        from PIL import Image
        from PIL.ExifTags import GPSTAGS, IFD, TAGS
    except ImportError:
        return {}
    try:
        exif = Image.open(io.BytesIO(data)).getexif()
    except Exception:  # noqa: BLE001 - imagen corrupta: sin EXIF
        return {}
    tags = {TAGS.get(k, k): v for k, v in exif.items()}
    tags.update({TAGS.get(k, k): v for k, v in exif.get_ifd(IFD.Exif).items()})
    out: dict[str, Any] = {}
    if tags.get("Make"):
        out["marca"] = str(tags["Make"]).strip("\x00 ")
    if tags.get("Model"):
        out["modelo"] = str(tags["Model"]).strip("\x00 ")
    raw = tags.get("DateTimeOriginal") or tags.get("DateTime")
    if raw:
        out["fecha"] = str(raw).replace(":", "-", 2)      # 2026:08:12 14:30:00 -> 2026-08-12 14:30:00
    gps = {GPSTAGS.get(k, k): v for k, v in exif.get_ifd(IFD.GPSInfo).items()}
    if gps.get("GPSLatitude") and gps.get("GPSLongitude"):
        def deg(v: Any, ref: Any) -> float:
            d = float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
            return -d if str(ref) in ("S", "W") else d
        out["gps"] = {"lat": round(deg(gps["GPSLatitude"], gps.get("GPSLatitudeRef")), 6),
                      "lon": round(deg(gps["GPSLongitude"], gps.get("GPSLongitudeRef")), 6)}
    return out
