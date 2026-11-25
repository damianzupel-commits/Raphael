"""Los casos del forense: nodos, aristas, artefactos, propuestas y un registro encadenado, todo en el espacio de datos
de la brigada (el almacén del harness), no en archivos sueltos.

Reglas:
- Todo nodo se rastrea hasta un artefacto con hash (o es `manual`). Toda arista exige `artefacto_origen`.
- Nada se borra: retractar deja el dato y el motivo.
- Cada operación queda en un registro de solo agregar, encadenado por hash (y firmado con HMAC si hay clave
  `INVESTIGACION_LOG_KEY`). `verify_log` detecta cualquier cambio a una entrada vieja.
- El forense trabaja solo sobre artefactos que la persona entregó. Nunca sale a tocar sistemas ajenos.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import unicodedata
from pathlib import Path

from .env import Env
from .model import EdgeType, NodeType, Origin, make_edge, make_node

GENESIS = "0" * 64
MAX_ARTIFACT_BYTES = 25 * 1024 * 1024


class CaseError(ValueError):
    """Algo no se puede hacer con el caso (no existe, falta un dato, rompe una regla). El mensaje es para la persona."""


def slugify(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")[:48] or "caso"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Cases:
    """Todas las operaciones sobre los casos. Se arma con un `Env` y no guarda estado propio."""

    def __init__(self, env: Env) -> None:
        self.env = env
        self.s = env.space

    # --- casos ---------------------------------------------------------------------------------------------------------
    def create(self, title: str, description: str = "", by: str = "persona") -> dict:
        title = (title or "").strip()
        if not title:
            raise CaseError("el caso necesita un título")
        base, n, cid = slugify(title), 1, ""
        while True:
            cid = base if n == 1 else f"{base}-{n}"
            if self.s.get("cases", cid) is None:
                break
            n += 1
        case = {"id": cid, "title": title, "description": description, "created_at": self.env.iso(), "status": "abierto"}
        self.s.put("cases", cid, case)
        self.log(cid, "crear_caso", {"title": title}, by)
        self.env.event("caso.creado", {"case": cid, "title": title})
        return case

    def get(self, case: str) -> dict:
        found = self.s.get("cases", case)
        if found is None:
            raise CaseError(f"no existe el caso '{case}'")
        return found

    def list(self) -> list[dict]:
        return self.s.list("cases")

    # --- registro encadenado ---------------------------------------------------------------------------------------------
    def _key(self) -> bytes | None:
        raw = self.env.environ.get("INVESTIGACION_LOG_KEY", "")
        return raw.encode() if raw else None

    def log(self, case: str, op: str, payload: dict, who: str = "sistema") -> dict:
        entries = self.s.list("log", case=case)
        prev = entries[-1]["entry_hash"] if entries else GENESIS
        entry = {"case": case, "seq": len(entries) + 1, "at": self.env.iso(), "op": op, "who": who, "payload": payload,
                 "prev_hash": prev}
        entry["entry_hash"] = self._hash(entry)
        key = self._key()
        entry["signature"] = hmac.new(key, entry["entry_hash"].encode(), "sha256").hexdigest() if key else ""
        self.s.put("log", f"{case}:{entry['seq']:08d}", entry)
        return entry

    @staticmethod
    def _hash(entry: dict) -> str:
        body = {k: entry[k] for k in ("case", "seq", "at", "op", "who", "payload", "prev_hash")}
        return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def verify_log(self, case: str) -> dict:
        """{ok, entries, signed, problem}. Detecta una entrada cambiada, borrada o reordenada."""
        self.get(case)
        entries = self.s.list("log", case=case)
        key = self._key()
        prev = GENESIS
        signed = 0
        for i, e in enumerate(entries, 1):
            if e["seq"] != i or e["prev_hash"] != prev:
                return {"ok": False, "entries": len(entries), "signed": signed, "problem": f"la cadena se corta en la entrada {i}"}
            if self._hash(e) != e["entry_hash"]:
                return {"ok": False, "entries": len(entries), "signed": signed, "problem": f"la entrada {i} fue modificada"}
            if e.get("signature"):
                if key is None:
                    pass                      # firmada, pero esta instalación no tiene la clave: no se puede comprobar
                elif not hmac.compare_digest(e["signature"], hmac.new(key, e["entry_hash"].encode(), "sha256").hexdigest()):
                    return {"ok": False, "entries": len(entries), "signed": signed, "problem": f"firma inválida en la entrada {i}"}
                else:
                    signed += 1
            prev = e["entry_hash"]
        return {"ok": True, "entries": len(entries), "signed": signed, "problem": ""}

    # --- artefactos -------------------------------------------------------------------------------------------------------
    def add_artifact(self, case: str, name: str, data: bytes, mime: str = "application/octet-stream", *, text: str = "",
                     by: str = "persona") -> dict:
        """Registra un artefacto entregado: hash, tamaño, y (si hay carpeta configurada) una copia intacta."""
        self.get(case)
        if len(data) > MAX_ARTIFACT_BYTES:
            raise CaseError(f"'{name}' pesa más de {MAX_ARTIFACT_BYTES // 1024 // 1024} MB: no se ingesta")
        sha = sha256_bytes(data)
        node = make_node(NodeType.ARCHIVO, {"nombre": name, "sha256": sha, "tamano": len(data), "mime": mime})
        key = f"{case}:{sha}"
        existing = self.s.get("artifacts", key)
        if existing is not None:
            return {**existing, "already": True}
        copy_path = ""
        if self.env.config.artifacts_dir:
            folder = Path(self.env.config.artifacts_dir) / case
            folder.mkdir(parents=True, exist_ok=True)
            (folder / sha).write_bytes(data)
            copy_path = str(folder / sha)
        art = {"case": case, "sha256": sha, "name": name, "size": len(data), "mime": mime, "node": node["id"],
               "added_at": self.env.iso(), "copy": copy_path, "text": text[:200_000]}
        self.s.put("artifacts", key, art)
        self.add_node(case, node, by=by, log=False)
        self.log(case, "ingestar_artefacto", {"sha256": sha, "name": name, "size": len(data)}, by)
        return {**art, "already": False}

    def artifact(self, case: str, sha: str) -> dict:
        found = self.s.get("artifacts", f"{case}:{sha}")
        if found is None:
            raise CaseError(f"el caso '{case}' no tiene un artefacto {sha[:12]}…")
        return found

    def artifacts(self, case: str) -> list[dict]:
        return self.s.list("artifacts", case=case)

    def verify_artifact(self, case: str, sha: str) -> dict:
        """Recalcula el hash de la copia guardada. Sin copia no hay nada que verificar y lo dice."""
        art = self.artifact(case, sha)
        if not art["copy"]:
            return {"ok": None, "detail": "no hay copia guardada (falta `artifacts_dir`): solo se conoce el hash original"}
        path = Path(art["copy"])
        if not path.is_file():
            return {"ok": False, "detail": "la copia guardada ya no está"}
        ok = sha256_bytes(path.read_bytes()) == art["sha256"]
        return {"ok": ok, "detail": "el hash coincide" if ok else "la copia cambió: no coincide con el hash original"}

    # --- grafo ------------------------------------------------------------------------------------------------------------
    def add_node(self, case: str, node: dict, *, by: str = "parser", log: bool = True) -> tuple[dict, bool]:
        """Guarda un nodo (idempotente por id). Devuelve (nodo, creado)."""
        key = f"{case}:{node['id']}"
        prev = self.s.get("nodes", key)
        if prev is not None:
            return prev, False
        doc = {**node, "case": case, "created_at": self.env.iso()}
        self.s.put("nodes", key, doc)
        if log:
            self.log(case, "nodo", {"id": node["id"], "tipo": node["tipo"]}, by)
        return doc, True

    def add_edge(self, case: str, edge: dict, *, by: str = "parser", log: bool = True) -> tuple[dict, bool]:
        key = f"{case}:{edge['id']}"
        prev = self.s.get("edges", key)
        if prev is not None:
            return prev, False
        for end in (edge["src"], edge["dst"]):
            if self.s.get("nodes", f"{case}:{end}") is None:
                raise CaseError(f"la arista apunta a un nodo que no existe en el caso: {end}")
        doc = {**edge, "case": case, "created_at": self.env.iso()}
        self.s.put("edges", key, doc)
        if log:
            self.log(case, "arista", {"id": edge["id"], "tipo": edge["tipo"]}, by)
        return doc, True

    def node(self, case: str, node_id: str) -> dict:
        found = self.s.get("nodes", f"{case}:{node_id}")
        if found is None:
            raise CaseError(f"el caso '{case}' no tiene el nodo '{node_id}'")
        return found

    def nodes(self, case: str, *, tipo: str | None = None, retracted: bool = False) -> list[dict]:
        out = self.s.list("nodes", case=case)
        return [n for n in out if (tipo is None or n["tipo"] == tipo) and (retracted or not n["retracted"])]

    def edges(self, case: str, *, retracted: bool = False) -> list[dict]:
        return [e for e in self.s.list("edges", case=case) if retracted or not e["retracted"]]

    def retract(self, case: str, kind: str, item_id: str, reason: str, by: str = "persona") -> dict:
        """Marca un nodo o una arista como retractado. Nunca se borra: queda con su motivo y su fecha."""
        if kind not in ("nodo", "arista"):
            raise CaseError("se retracta un 'nodo' o una 'arista'")
        if not (reason or "").strip():
            raise CaseError("retractar necesita un motivo")
        coll = "nodes" if kind == "nodo" else "edges"
        doc = self.s.get(coll, f"{case}:{item_id}")
        if doc is None:
            raise CaseError(f"el caso '{case}' no tiene {kind} '{item_id}'")
        if doc["tipo"] == NodeType.ARCHIVO.value and kind == "nodo":
            raise CaseError("un artefacto no se retracta: es la prueba de la que cuelga todo lo demás")
        doc.update(retracted=True, retracted_reason=reason.strip(), retracted_at=self.env.iso())
        self.s.put(coll, f"{case}:{item_id}", doc)
        if kind == "nodo":     # las aristas que tocan un nodo retractado quedan retractadas con él
            for e in self.edges(case):
                if item_id in (e["src"], e["dst"]):
                    e.update(retracted=True, retracted_reason=f"el nodo {item_id} fue retractado", retracted_at=self.env.iso())
                    self.s.put("edges", f"{case}:{e['id']}", e)
        self.log(case, f"retractar_{kind}", {"id": item_id, "motivo": reason.strip()}, by)
        self.env.event("caso.actualizado", {"case": case, "op": f"retractar_{kind}", "id": item_id})
        return doc

    def link(self, case: str, tipo: EdgeType, src: str, dst: str, *, artifact: str, origen: Origin = Origin.PARSER,
             confianza: float = 1.0, detalle: str = "", by: str = "parser") -> dict:
        return self.add_edge(case, make_edge(tipo, src, dst, artefacto_origen=artifact, origen=origen, confianza=confianza,
                                             detalle=detalle), by=by, log=False)[0]

    def summary(self, case: str) -> dict:
        c = self.get(case)
        nodes = self.nodes(case)
        by_type: dict[str, int] = {}
        for n in nodes:
            by_type[n["tipo"]] = by_type.get(n["tipo"], 0) + 1
        pend = [p for p in self.s.list("proposals", case=case, status="pendiente")]
        fus = [f for f in self.s.list("fusions", case=case, status="pendiente")]
        return {"id": c["id"], "title": c["title"], "status": c["status"], "artifacts": len(self.artifacts(case)),
                "nodes": by_type, "edges": len(self.edges(case)), "pending_proposals": len(pend),
                "pending_fusions": len(fus), "log": self.verify_log(case)}
