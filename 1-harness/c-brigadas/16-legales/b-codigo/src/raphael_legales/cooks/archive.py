"""Archivo: registro versionado de documentos emitidos y de consentimientos recibidos.

Emitir un documento (`emitir_documento`, aprobación, irreversible) crea una versión EMITIDA nueva e inmutable; el borrador
queda. Quien aprueba puede mandar `changes: {"text": ...}` con el texto final. Nunca firma ni envía: emitir es dejar
constancia de que una persona lo dio por bueno. Un consentimiento recibido se registra solo (automático); una baja
también y se respeta al instante (marca, no borra). Borrar un registro pide aprobación.
"""

from __future__ import annotations

from raphael_core import Action, ActionError, Cook

from .. import archive
from ..disclaimer import DISCLAIMER


def _strip_header(text: str) -> str:
    """Saca el encabezado de borrador (hasta el primer renglón vacío) si el texto lo trae."""
    if text.startswith("*** BORRADOR"):
        return text.split("\n\n", 1)[1] if "\n\n" in text else ""
    return text


class Archive(Cook):
    name = "archivo"
    version = "2.0.0"
    description = "Guarda las versiones de los documentos emitidos y los consentimientos (y bajas) de los contactos."
    commands = {
        "documentos": "Documentos del archivo {'kind': ..., 'state': 'borrador'|'emitido'} (sin el texto)",
        "ver": "Un documento completo {'doc_id': ...}",
        "emitir": "Emite un documento {'doc_id': ..., 'text': 'texto final opcional'} (pide aprobación)",
        "consentimientos": "Consentimientos {'all': true} para incluir las bajas",
        "consentimiento": "Registra un consentimiento {'contact': ..., 'purpose': ..., 'channel': ..., 'evidence': ...}",
        "baja": "Registra una baja {'contact': ..., 'purpose': opcional}",
        "borrar": "Borra un registro {'collection': 'documents'|'consents', 'key': ...} (pide aprobación)",
    }

    def _do(self, ctx, typ: str, data: dict, summary: str) -> dict:
        res = ctx.request(Action(typ, data, summary))
        if res.get("state") == "error":
            raise ActionError(res["error"])
        return res

    def command(self, name, data, ctx):
        if name == "documentos":
            return [{k: v for k, v in d.items() if k != "text"} for d in ctx.shared.list("documents")
                    if (not data.get("kind") or d["kind"] == data["kind"]) and (not data.get("state") or d["state"] == data["state"])]
        if name == "ver":
            d = archive.get_doc(ctx.shared, str(data.get("doc_id") or ""))
            if d is None:
                raise ActionError("no existe ese documento")
            return d
        if name == "consentimientos":
            return ctx.shared.list("consents") if data.get("all") else archive.active_consents(ctx.shared)
        if name == "emitir":
            doc_id = str(data.get("doc_id") or "")
            d = archive.get_doc(ctx.shared, doc_id)
            if d is None:
                raise ActionError("no existe ese documento")
            payload = {"doc_id": doc_id, **({"text": str(data["text"])} if data.get("text") else {})}
            return self._do(ctx, "emitir_documento", payload, f"Emitir «{d['title']}» (versión {d['version']})")
        if name == "consentimiento":
            for k in ("contact", "purpose", "channel"):
                if not data.get(k):
                    raise ActionError(f"falta '{k}'")
            return self._do(ctx, "registrar_consentimiento", dict(data), f"Consentimiento de {data['contact']}")
        if name == "baja":
            if not data.get("contact"):
                raise ActionError("falta 'contact'")
            return self._do(ctx, "registrar_baja", dict(data), f"Baja de {data['contact']}")
        if name == "borrar":
            if data.get("collection") not in ("documents", "consents") or not data.get("key"):
                raise ActionError("hace falta 'collection' (documents|consents) y 'key'")
            return self._do(ctx, "borrar_registro", dict(data), f"Borrar {data['collection']}/{data['key']}")
        return super().command(name, data, ctx)

    def on_event(self, event, data, ctx):
        if event == "consentimiento.recibido" and data.get("contact") and data.get("purpose"):
            ctx.request(Action("registrar_consentimiento", {"channel": "", "evidence": "", **data},
                               f"Consentimiento de {data['contact']}"))
        elif event == "baja.solicitada" and data.get("contact"):
            ctx.request(Action("registrar_baja", dict(data), f"Baja de {data['contact']}"))

    def execute(self, action, ctx):
        d, now = action.data, ctx.now().isoformat(timespec="seconds")
        if action.type == "emitir_documento":
            base = archive.get_doc(ctx.shared, d["doc_id"])
            if base is None:
                raise ActionError("no existe ese documento")
            if base["state"] == "emitido" and not d.get("text"):
                return f"{base['id']} ya estaba emitido"
            body = _strip_header(d.get("text") or base["text"])
            if "[COMPLETAR" in body or "[VERIFICAR" in body:
                raise ActionError("el texto todavía tiene [COMPLETAR] o [VERIFICAR]: completalo (o pasá 'text' final) antes de emitir")
            version = archive.next_version(ctx.shared, base["kind"])
            text = f"*** DOCUMENTO EMITIDO · {base['title']} · versión {version} ***\n{DISCLAIMER}\n\n{body}"
            rec = archive.save_draft(ctx.shared, {**base, "id": archive.doc_key(base["kind"], version), "version": version,
                                                  "state": "emitido", "text": text, "missing": [], "from": base["id"],
                                                  "issued_at": now, "issued_by": "persona (aprobación)"})
            ctx.publish("documento.emitido", {"id": rec["id"], "kind": rec["kind"], "version": version})
            return f"{rec['id']} emitido"
        if action.type == "registrar_consentimiento":
            archive.record_consent(ctx.shared, contact=d["contact"], purpose=d["purpose"], channel=d.get("channel", ""),
                                   evidence=d.get("evidence", ""), at=now)
            ctx.publish("consentimiento.registrado", {"contact": d["contact"], "purpose": d["purpose"]})
            return None
        if action.type == "registrar_baja":
            n = archive.revoke_consent(ctx.shared, contact=d["contact"], purpose=d.get("purpose"), at=now)
            ctx.publish("consentimiento.revocado", {"contact": d["contact"], "purpose": d.get("purpose"), "n": n})
            return f"{n} consentimiento(s) dado(s) de baja"
        if action.type == "borrar_registro":
            ok = ctx.shared.delete(d["collection"], d["key"])
            if not ok:
                raise ActionError("no existe ese registro")
            ctx.record("registro_borrado", collection=d["collection"], key=str(d["key"]))
            return "borrado"
        raise ActionError(f"archivo no ejecuta '{action.type}'")
