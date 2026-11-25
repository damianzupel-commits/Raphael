"""Aplicar arreglo: escribe una propuesta en el código SOLO con la aprobación de la persona.

Camino: comando `aplicar` -> pide la acción `aplicar_arreglo` (nivel `aprobacion`, `irreversible`: nunca baja a automático)
-> queda pendiente -> la persona aprueba -> recién ahí `execute` escribe. Defensas, todas en código:
- la acción lleva solo el `proposal_id` y la huella; los snippets salen de la propuesta guardada, no de lo que llegue;
- si la huella no coincide con la propuesta, no aplica (nadie reusa una aprobación para colar otro cambio);
- línea roja otra vez al aplicar (ver guardrail.py);
- el snippet tiene que seguir apareciendo una sola vez (si el archivo cambió, no aplica);
- si hay `verify_command` y falla, se deshace solo y la propuesta queda `revertida_por_verificacion`;
- `revertir_arreglo` (también con aprobación) vuelve atrás el cambio con el reemplazo inverso.
Portado de `selfrepair/gate.py`, `selfrepair/guardrail.py` y `codeedit/fixer.py` (JarvisRemote).
"""

from __future__ import annotations

from raphael_core import Action, ActionError, Cook, Origin

from .. import fixer, guardrail, proposals
from ..config import ROOT_ENV, repair_config, resolve_root

APPLY, REVERT = "aplicar_arreglo", "revertir_arreglo"


class Apply(Cook):
    name = "aplicar"
    version = "2.0.0"
    description = "Aplica un arreglo propuesto cuando la persona lo aprueba, con línea roja, verificación y vuelta atrás."
    commands = {
        "aplicar": "Pide aprobación para aplicar una propuesta {'proposal_id'}",
        "revertir": "Pide aprobación para deshacer una propuesta ya aplicada {'proposal_id'}",
    }

    def _setup(self, ctx):
        cfg = repair_config(ctx.config)
        root = resolve_root(cfg)
        if root is None:
            raise ActionError(f"no hay carpeta del proyecto a reparar: cargá {ROOT_ENV} o `root` en la config")
        if not root.is_dir():
            raise ActionError(f"la carpeta a reparar no existe: {root}")
        return cfg, root

    def _proposal(self, ctx, proposal_id) -> dict:
        p = proposals.load(ctx.shared, proposal_id)
        if p is None:
            raise ActionError(f"no existe la propuesta '{proposal_id}'")
        if p.get("digest") != proposals.digest(p["file"], p["old_snippet"], p["new_snippet"]):
            raise ActionError(f"la propuesta {proposal_id} no es consistente (cambió después de guardarse): no la toco")
        return p

    def _guard(self, cfg, p) -> None:
        reason = guardrail.check(p["file"], cfg.extra_protected)
        if reason:
            raise ActionError(reason)

    # --- pedir la acción (queda pendiente)
    def command(self, name, data, ctx):
        if name not in ("aplicar", "revertir"):
            return super().command(name, data, ctx)
        cfg, root = self._setup(ctx)
        p = self._proposal(ctx, data.get("proposal_id"))
        self._guard(cfg, p)
        if name == "aplicar":
            if p["status"] != proposals.PROPOSED:
                raise ActionError(f"la propuesta {p['id']} está '{p['status']}': solo se aplica una pendiente")
            try:
                fixer.plan(root, p["file"], p["old_snippet"], p["new_snippet"])      # que todavía aplique
            except (fixer.FixError, PermissionError) as exc:
                raise ActionError(f"ya no aplica: {exc}") from None
            action = Action(APPLY, {"proposal_id": p["id"], "digest": p["digest"], "diff": p["diff"][:4000]},
                            f"Aplicar el arreglo {p['id']} en {p['file']}: {p['rationale'][:120]}", origin=Origin.OWNER)
        else:
            if p["status"] != proposals.APPLIED:
                raise ActionError(f"la propuesta {p['id']} está '{p['status']}': solo se revierte una aplicada")
            action = Action(REVERT, {"proposal_id": p["id"], "digest": p["digest"]},
                            f"Deshacer el arreglo {p['id']} en {p['file']}", origin=Origin.OWNER)
        res = ctx.request(action)
        ctx.record("arreglo_pedido", id=p["id"], accion=action.type, estado=res.get("state"))
        return res

    # --- ejecutar (ya aprobada)
    def execute(self, action, ctx):
        if action.type not in (APPLY, REVERT):
            raise ActionError(f"aplicar no ejecuta '{action.type}'")
        cfg, root = self._setup(ctx)
        p = self._proposal(ctx, action.data.get("proposal_id"))
        if action.data.get("digest") != p["digest"]:
            raise ActionError("la aprobación no corresponde a esta propuesta (la huella no coincide): no aplico nada")
        self._guard(cfg, p)
        return self._apply(p, cfg, root, ctx) if action.type == APPLY else self._revert(p, cfg, root, ctx)

    def _apply(self, p, cfg, root, ctx) -> str:
        if p["status"] != proposals.PROPOSED:
            raise ActionError(f"la propuesta {p['id']} está '{p['status']}': solo se aplica una pendiente")
        try:
            pl = fixer.plan(root, p["file"], p["old_snippet"], p["new_snippet"])
        except (fixer.FixError, PermissionError) as exc:
            raise ActionError(f"ya no aplica: {exc}") from None
        fixer.write_text(pl.target, pl.updated)
        ok, tail = fixer.verify(cfg.verify_command, root, cfg.verify_timeout_seconds)
        if not ok:
            fixer.write_text(pl.target, pl.original)                    # vuelta atrás automática
            p["status"] = proposals.FAILED_CHECK
            p["check_output"] = tail[:2000]
            proposals.save(ctx.shared, p)
            ctx.record("arreglo_deshecho_por_verificacion", id=p["id"], file=p["file"])
            raise ActionError(f"apliqué {p['id']} pero la verificación falló y lo deshice solo. Salida:\n{tail}")
        git = fixer.commit_file(root, p["file"], p["commit_message"]) if cfg.git_commit else \
            {"committed": False, "commit": None, "note": "git_commit apagado en la config"}
        p.update(status=proposals.APPLIED, applied_at=ctx.now().isoformat(timespec="seconds"), commit=git["commit"])
        proposals.save(ctx.shared, p)
        ctx.record("arreglo_aplicado", id=p["id"], file=p["file"], commit=git["commit"])
        ctx.publish("arreglo.aplicado", {"proposal_id": p["id"], "file": p["file"], "commit": git["commit"]})
        return (f"Listo: apliqué {p['id']} en {p['file']} ({git['note']}"
                f"{'; verificado' if cfg.verify_command else '; sin verificación'}). Para deshacerlo: revertir {p['id']}.")

    def _revert(self, p, cfg, root, ctx) -> str:
        if p["status"] != proposals.APPLIED:
            raise ActionError(f"la propuesta {p['id']} está '{p['status']}': solo se revierte una aplicada")
        try:
            pl = fixer.plan(root, p["file"], p["new_snippet"], p["old_snippet"])     # reemplazo inverso
        except (fixer.FixError, PermissionError) as exc:
            raise ActionError(f"no se puede deshacer solo ({exc}): el archivo cambió después. Revisalo a mano.") from None
        fixer.write_text(pl.target, pl.updated)
        git = fixer.commit_file(root, p["file"], f"revert: {p['commit_message']}") if cfg.git_commit else \
            {"committed": False, "commit": None, "note": "git_commit apagado en la config"}
        p.update(status=proposals.REVERTED, reverted_at=ctx.now().isoformat(timespec="seconds"), revert_commit=git["commit"])
        proposals.save(ctx.shared, p)
        ctx.record("arreglo_revertido", id=p["id"], file=p["file"], commit=git["commit"])
        ctx.publish("arreglo.revertido", {"proposal_id": p["id"], "file": p["file"], "commit": git["commit"]})
        return f"Deshecho: {p['id']} volvió atrás en {p['file']} ({git['note']})."

    # --- la persona rechazó la aprobación
    def on_event(self, event, data, ctx):
        if event != "pendiente.rechazado" or data.get("brigade") != ctx.brigade or data.get("type") != APPLY:
            return
        p = proposals.load(ctx.shared, (data.get("data") or {}).get("proposal_id"))
        if p and p["status"] == proposals.PROPOSED:
            p["status"] = proposals.REJECTED
            p["reject_reason"] = str(data.get("reason") or "")[:300]
            proposals.save(ctx.shared, p)
