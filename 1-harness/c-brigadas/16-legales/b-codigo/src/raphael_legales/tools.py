"""Tools de la brigada: lo que usan los efímeros del jefe. Las arma `validate` (el `setup` del manifiesto).

Reusan el código de los cocineros (`execute` y `command`), así que las validaciones, el aviso legal y las fuentes son los
mismos. Armar un borrador, revisar un texto, verificar una norma y anotar una baja son automáticos (como sus acciones);
EMITIR un documento pide la aprobación de la persona en cada uso y es irreversible. Registrar un consentimiento y borrar un
registro NO son tools: los pide la persona (o llega el evento de quien lo recibió). Como las tools no publican eventos, los
avisos `documento.borrador_creado`, `revision.lista`, `riesgo.detectado` y compañía no salen cuando el trabajo pasa por acá.
"""

from __future__ import annotations

from datetime import datetime

from raphael_core import Action, ActionError

from . import archive
from .cooks.archive import Archive
from .cooks.compliance import Compliance
from .cooks.documents import Documents
from .cooks.risks import MAX_TEXT, Risks
from .templates import TEMPLATES


class _ToolCtx:
    """Lo que usan los cocineros de legales del contexto para trabajar sobre `shared`; sin modelo y sin eventos."""

    def __init__(self, setup_ctx) -> None:
        self.config, self.shared = setup_ctx.config, setup_ctx.shared

    @staticmethod
    def now() -> datetime:
        return datetime.now()

    @staticmethod
    def has_ai(*_a, **_k) -> bool:
        return False

    @staticmethod
    def publish(*_a, **_k) -> None:
        return None

    @staticmethod
    def record(*_a, **_k) -> None:
        return None


def make_tools(ctx) -> dict:
    tc = _ToolCtx(ctx)
    docs, risks_, comp, arch = Documents(), Risks(), Compliance(), Archive()

    def _seguro(fn):
        try:
            return fn()
        except ActionError as exc:
            return {"ok": False, "motivo": str(exc)}

    def legales_plantillas() -> list[dict]:
        """Las plantillas de documentos y las variables que pide cada una."""
        return docs.command("plantillas", {}, tc)

    def legales_borrador(kind: str, values: dict | None = None) -> dict:
        """Arma un borrador desde una plantilla (politica_privacidad, terminos_condiciones, presupuesto, contrato_servicio, carta)
        con los datos del negocio y los `values` que falten. Para una carta, el cuerpo va en values['cuerpo']. Queda como
        BORRADOR en el archivo: no se envía ni se firma."""
        def hacer():
            if kind not in TEMPLATES:
                raise ActionError(f"no hay plantilla '{kind}' (hay: {', '.join(TEMPLATES)})")
            version = archive.next_version(tc.shared, kind)
            doc_id = archive.doc_key(kind, version)
            docs.execute(Action("generar_borrador", {"kind": kind, "values": values or {}, "brief": "", "doc_id": doc_id,
                                                     "version": version}), tc)
            return {"doc_id": doc_id, **(archive.get_doc(tc.shared, doc_id) or {})}
        return _seguro(hacer)

    def legales_documentos(kind: str = "", state: str = "") -> list[dict]:
        """Los documentos del archivo, sin el texto. `state`: borrador o emitido."""
        return arch.command("documentos", {"kind": kind or None, "state": state or None}, tc)

    def legales_ver_documento(doc_id: str) -> dict:
        """Un documento completo (con su texto, lo que falta completar y sus fuentes)."""
        return _seguro(lambda: arch.command("ver", {"doc_id": doc_id}, tc))

    def legales_emitir_documento(doc_id: str, text: str = "") -> dict:
        """Da un borrador por bueno: queda una versión EMITIDA e inmutable. Si todavía tiene [COMPLETAR] o [VERIFICAR], no emite.
        Cada uso pide la aprobación de la persona."""
        data = {"doc_id": doc_id, **({"text": text} if text else {})}
        return _seguro(lambda: {"ok": True, "resultado": arch.execute(Action("emitir_documento", data), tc)})

    def legales_checklist() -> dict:
        """El checklist de cumplimiento para un pyme argentino, con el estado de cada ítem y de su fuente."""
        return comp.command("checklist", {}, tc)

    def legales_normas() -> list[dict]:
        """Las normas de partida y cuándo se consultó cada fuente oficial."""
        return comp.command("normas", {}, tc)

    def legales_verificar_norma(id: str) -> dict:
        """Consulta la fuente oficial pública de una norma y anota cuándo; avisa si la página cambió. Sin red queda 'sin verificar'."""
        return _seguro(lambda: {"ok": True, "resultado": comp.execute(Action("verificar_norma", {"id": id}), tc)})

    def legales_revisar_texto(text: str, ref: str = "") -> dict:
        """Revisa un texto antes de publicarlo (por reglas) y marca los riesgos legales. No aprueba nada, solo avisa."""
        def hacer():
            if not str(text).strip():
                raise ActionError("falta el texto a revisar")
            rid = f"rev-{tc.shared.next('reviews')}"
            risks_.execute(Action("revisar_texto", {"id": rid, "text": str(text)[:MAX_TEXT], "ref": str(ref or "")}), tc)
            return tc.shared.get("reviews", rid)
        return _seguro(hacer)

    def legales_revisiones(limit: int = 20) -> list[dict]:
        """Las últimas revisiones de riesgos."""
        return risks_.command("revisiones", {"limit": min(max(int(limit), 1), 100)}, tc)

    def legales_consentimientos(todos: bool = False) -> list[dict]:
        """Los consentimientos activos de los contactos (con `todos` también las bajas)."""
        return arch.command("consentimientos", {"all": bool(todos)}, tc)

    def legales_registrar_baja(contact: str, purpose: str = "") -> dict:
        """Anota la baja de un contacto (de un propósito, o de todos) y se respeta al instante: marca, no borra."""
        if not str(contact).strip():
            return {"ok": False, "motivo": "falta el contacto"}
        return _seguro(lambda: {"ok": True, "resultado": arch.execute(
            Action("registrar_baja", {"contact": contact, "purpose": purpose or None}), tc)})

    return {f.__name__: f for f in (
        legales_plantillas, legales_borrador, legales_documentos, legales_ver_documento, legales_emitir_documento,
        legales_checklist, legales_normas, legales_verificar_norma, legales_revisar_texto, legales_revisiones,
        legales_consentimientos, legales_registrar_baja)}
