"""Forense: casos, ingesta de evidencia entregada, entidades (propuestas), fusiones, línea de tiempo, grafo e informes."""

from __future__ import annotations

import re

from raphael_core import ActionError

from ..casefile import CaseError
from .base import InvCook


class Forensics(InvCook):
    name = "forense"
    version = "2.0.0"
    description = "Analiza chats, CSV, documentos, EXIF y logs de servidor entregados; casos, línea de tiempo, grafo e informes."
    interest_pattern = re.compile(r"\bcasos?\b|evidencia|forens|artefacto|grafo|entidad|exif|whatsapp|telegram|\bcsv\b|server ?log")
    commands = {
        "casos": "los casos abiertos", "caso": "resumen de un caso {'case'}", "nodo": "un nodo y sus vecinos {'case','node'}",
        "linea_tiempo": "eventos ordenados y huecos {'case'}", "grafo": "métricas del grafo {'case'}",
        "pendientes": "propuestas y fusiones por confirmar {'case'}", "verificar_log": "comprueba el registro {'case'}",
        "informe": "el informe como texto {'case','format': md|html|json}",
        "crear_caso": "crea un caso {'title','description'}", "ingerir": "ingresa un archivo {'case','path','kind','mapping'}",
        "extraer_entidades": "propone entidades de un artefacto {'case','artefacto','modelo': bool}",
        "sugerir_fusiones": "sugiere identidades repetidas {'case'}", "verificar_artefacto": "recalcula el hash {'case','sha256'}"}

    def run_command(self, name, data, ctx):
        inv = self.inv(ctx)
        case = data.get("case", "")
        if name == "casos":
            return [{"id": c["id"], "title": c["title"], "status": c["status"]} for c in inv.cases.list()]
        if name == "caso":
            return inv.case_view(case)
        if name == "nodo":
            return inv.node_view(case, data.get("node", ""))
        if name == "linea_tiempo":
            return inv.reports.timeline(case, float(data.get("gap_hours", 24)))
        if name == "grafo":
            return inv.reports.graph(case)
        if name == "pendientes":
            return inv.pending(case)
        if name == "verificar_log":
            return inv.cases.verify_log(case)
        if name == "informe":
            return {"format": data.get("format", "md"), "text": inv.reports.render(case, data.get("format", "md"))}
        if name == "crear_caso":
            return inv.cases.create(data.get("title", ""), data.get("description", ""))
        if name == "ingerir":
            return inv.ingest(case, data.get("path", ""), kind=data.get("kind") or None, mapping=data.get("mapping"))
        if name == "extraer_entidades":
            if data.get("modelo"):
                return inv.entities.extract_with_model(case, data.get("artefacto", ""))
            r = inv.entities.extract(case, data.get("artefacto", ""))
            return {"creadas": len(r["created"]), "descartadas": len(r["discarded"])}
        if name == "sugerir_fusiones":
            return inv.entities.suggest_fusions(case)
        if name == "verificar_artefacto":
            return inv.cases.verify_artifact(case, data.get("sha256", ""))
        return super().run_command(name, data, ctx)

    def run_action(self, action, ctx):
        inv, d = self.inv(ctx), action.data
        case = d.get("case", "")
        if action.type == "confirmar_propuesta":
            p = inv.entities.confirm(case, d.get("id", ""))
            return f"Propuesta {p['id']} confirmada: {p['node']['tipo']} en el caso {case}."
        if action.type == "rechazar_propuesta":
            inv.entities.reject(case, d.get("id", ""), d.get("reason", ""))
            return f"Propuesta {d.get('id')} rechazada."
        if action.type == "confirmar_fusion":
            f = inv.entities.confirm_fusion(case, d.get("id", ""))
            return f"Fusión {f['id']} confirmada: {f['a']} y {f['b']} quedan vinculados (mismo_que); ninguno se borró."
        if action.type == "rechazar_fusion":
            inv.entities.reject_fusion(case, d.get("id", ""), d.get("reason", ""))
            return f"Fusión {d.get('id')} rechazada."
        if action.type == "retractar":
            inv.cases.retract(case, d.get("kind", ""), d.get("id", ""), d.get("reason", ""))
            return f"{d.get('kind')} {d.get('id')} retractado (queda en el historial con su motivo)."
        if action.type == "exportar_informe":
            r = inv.reports.export(case, d.get("format", "md"))
            return f"Informe generado: {r['path']}" if r["path"] else r["aviso"]
        raise ActionError(f"forense no ejecuta '{action.type}'")

    def health(self, ctx):
        from raphael_core import Health
        cases = self.inv(ctx).cases
        bad = [c["id"] for c in cases.list() if not cases.verify_log(c["id"])["ok"]]
        return Health(not bad, "ok" if not bad else f"registro alterado en: {', '.join(bad)}")


__all__ = ["CaseError", "Forensics"]
