"""Tools de la brigada: lo que usan los efímeros del jefe. Las arma `validate` (el `setup` del manifiesto).

Ninguna escribe en el proyecto. `autorreparacion_proponer` guarda una propuesta EN SECO (diff y razón, la misma validación y
las mismas líneas rojas que el comando `proponer`). Aplicar y revertir un arreglo NO son tools: son las acciones
`aplicar_arreglo` y `revertir_arreglo` (aprobación, irreversibles, atadas a la huella de la propuesta) y las sigue pidiendo
el cocinero `aplicar` a pedido de la persona. Los hallazgos y las reflexiones viven en el espacio propio de la introspección,
que las tools no ven: el análisis de acá no los guarda.
"""

from __future__ import annotations

from datetime import datetime

from . import analyzer, guardrail, proposals
from .config import repair_config
from .cooks.introspect import LIMITES, LINEAS_ROJAS
from .cooks.propose import Propose


class _ToolCtx:
    """Lo mínimo que usa el cocinero `proponer` del contexto (el modelo no hace falta: `redactar` no es tool)."""

    def __init__(self, setup_ctx) -> None:
        self.config, self.shared = setup_ctx.config, setup_ctx.shared

    @staticmethod
    def now() -> datetime:
        return datetime.now()

    @staticmethod
    def record(*_a, **_k) -> None:
        return None


def make_tools(ctx) -> dict:
    tc = _ToolCtx(ctx)
    cook = Propose()

    def autorreparacion_propuestas(status: str = "") -> list[dict]:
        """Las propuestas de arreglo, sin los snippets. `status`: propuesta, aplicada, revertida, descartada, rechazada."""
        return [proposals.brief(p) for p in ctx.shared.list(proposals.COLLECTION) if not status or p.get("status") == status]

    def autorreparacion_ver_propuesta(proposal_id: str) -> dict:
        """Una propuesta con su diff, su razón y su estado."""
        p = proposals.load(ctx.shared, proposal_id)
        return p if p is not None else {"ok": False, "motivo": f"no existe la propuesta '{proposal_id}'"}

    def autorreparacion_proponer(file: str, old_snippet: str, new_snippet: str, rationale: str,
                                 commit_message: str = "") -> dict:
        """Guarda una propuesta de arreglo en seco: reemplazar `old_snippet` (aparece UNA vez) por `new_snippet` en `file`."""
        data = {"file": file, "old_snippet": old_snippet, "new_snippet": new_snippet, "rationale": rationale,
                "commit_message": commit_message}
        return cook._propose(data, tc)

    def autorreparacion_linea_roja(path: str) -> dict:
        """Dice si una ruta es línea roja (autenticación, secretos, políticas, esta brigada…): no se toca ni con aprobación."""
        cfg = repair_config(ctx.config)
        motivo = guardrail.check_all([str(path)], cfg.extra_protected)
        return {"path": path, "protegida": motivo is not None, "motivo": motivo}

    def autorreparacion_analizar(entries: list | None = None) -> dict:
        """Busca patrones de falla (escrituras repetidas, bloques abandonados, errores repetidos) en el registro de tool calls.
        Sin `entries` lee el archivo `audit_log_path` de la config. No guarda hallazgos."""
        cfg = repair_config(ctx.config)
        if entries is None:
            if not cfg.audit_log_path:
                return {"ok": False, "motivo": "no hay registro para analizar: pasá 'entries' o cargá audit_log_path"}
            entries = analyzer.read_log(cfg.audit_log_path)
        if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
            return {"ok": False, "motivo": "'entries' tiene que ser una lista de objetos"}
        found = analyzer.analyze(entries, cfg.min_repeats)
        return {"ok": True, "patrones": len(found), "hallazgos": found, "guardado": False}

    def autorreparacion_autoconocimiento() -> dict:
        """Qué hace esta brigada, qué tiene prohibido y qué NO sabe de sí."""
        return {"brigada": "Autorreparación", "corre_en": "la PC de Damián (no en la nube)",
                "lineas_rojas": LINEAS_ROJAS, "lineas_rojas_de_fabrica": len(guardrail.DEFAULT_PROTECTED),
                "limites_honestos": LIMITES}

    return {f.__name__: f for f in (autorreparacion_propuestas, autorreparacion_ver_propuesta, autorreparacion_proponer,
                                    autorreparacion_linea_roja, autorreparacion_analizar, autorreparacion_autoconocimiento)}
