"""Los tres cocineros de Seguridad: auditor (defensa), pentest (ataque, solo PC) y vigilancia (defensa pasiva)."""

from __future__ import annotations

import re
from datetime import datetime

from raphael_core import Action, ActionError, Cook, Health, Message, Origin, Reply, Trust
from raphael_core.text_es import normalize

from .audit import run_audit
from .defensive import probes_from_env, run_watch
from .deps import source_from_env
from .guardrail import TargetNotAuthorized, authorize
from .models import SEVERITIES, Finding, ScanResult, sort_findings
from .pentest import NotLocalEdition, PentestUnavailable, ensure_local_edition, run_pentest
from .report import render, summary_line
from .settings import Settings

PURGEABLE = ("auditorias", "pentests", "alertas", "accesos")
COOLDOWN_HOURS = 6


def _owner_only(msg: Message) -> bool:
    """Lo de terceros es dato, nunca una orden: estos cocineros solo le contestan a la persona dueña."""
    return msg.trust == Trust.TRUSTED


def edition_of(ctx) -> str:
    """La edición que anotó `setup`. Sin dato se asume la más restrictiva (nube): el pentest nunca arranca por descuido."""
    return (ctx.shared.get("estado", "modo") or {}).get("edition", "cloud")


def _summ(findings: list[dict]) -> dict:
    c = dict.fromkeys(SEVERITIES, 0)
    for f in findings:
        if f.get("status", "open") == "open":
            c[f["severity"]] += 1
    return c


def _query(ctx, collection: str, data: dict) -> list[dict]:
    """Hallazgos guardados, filtrados por severidad o herramienta."""
    out: list[dict] = []
    for doc in ctx.shared.list(collection):
        out += doc.get("findings", [doc] if "severity" in doc else [])
    return [f for f in out if f.get("status", "open") == "open"
            and (not data.get("severity") or f["severity"] == data["severity"])
            and (not data.get("tool") or f["tool"] == data["tool"])]


class Auditor(Cook):
    name = "auditor"
    version = "2.0.0"
    description = "Audita repos autorizados: secretos expuestos, dependencias vulnerables y configuración. Solo lee."
    commands = {"auditar": "audita un repo autorizado {'repo': ruta}", "hallazgos": "hallazgos abiertos {'severity','tool'}",
                "ultimo_reporte": "el último reporte de un repo {'repo'}", "repos": "repos autorizados para auditar",
                "purgar": "borra el historial {'what': auditorias|pentests|alertas|accesos} (pide aprobación)"}

    def interest(self, msg, ctx):
        return 0.6 if _owner_only(msg) and re.search(r"audit|secretos expuestos|vulnerabilidad", normalize(msg.text)) else 0.0

    def handle(self, msg, ctx):
        if self.interest(msg, ctx) == 0:
            return None
        last = ctx.shared.list("auditorias")
        if not last:
            return Reply("Todavía no auditamos ningún repo. Pedime auditar uno de la lista autorizada.")
        return Reply("Última auditoría: " + summary_line(ScanResult.from_dict(last[-1]["result"])))

    def command(self, name, data, ctx):
        s = Settings.build(ctx.config)
        if name == "repos":
            return s.repos
        if name == "auditar":
            return self._audit(data, ctx, s)
        if name == "hallazgos":
            return [f.to_dict() for f in sort_findings([Finding.from_dict(f) for f in _query(ctx, "auditorias", data)])]
        if name == "ultimo_reporte":
            doc = ctx.shared.get("auditorias", _key(s.allowed_repo(data["repo"]))) if data.get("repo") else None
            docs = [doc] if doc else ctx.shared.list("auditorias")[-1:]
            if not docs:
                raise ActionError("todavía no hay ninguna auditoría guardada")
            return render(ScanResult.from_dict(docs[-1]["result"]))
        if name == "purgar":
            what = data.get("what", "")
            if what not in PURGEABLE:
                raise ActionError(f"'what' tiene que ser uno de {PURGEABLE}")
            return ctx.request(Action("purgar_historial", {"what": what}, f"Borrar el historial de {what} de Seguridad",
                                      origin=Origin.OWNER))
        return super().command(name, data, ctx)

    def _audit(self, data, ctx, s: Settings) -> dict:
        try:
            root = s.allowed_repo(str(data.get("repo", "")))
        except PermissionError as exc:
            raise ActionError(str(exc)) from None
        prev_doc = ctx.shared.get("auditorias", _key(root))
        prev = ScanResult.from_dict(prev_doc["result"]) if prev_doc else None
        res = run_audit(root, source_from_env(s.env), now=ctx.now(), previous=prev)
        ctx.shared.put("auditorias", _key(root), {"repo": str(root), "result": res.to_dict(), "findings": [f.to_dict() for f in res.findings]})
        ctx.publish("seguridad.auditoria_terminada", {"repo": root.name, "counts": res.counts()})
        for f in res.findings:
            if f.status == "open" and f.severity == "critical" and f.rule_id != "limpio":
                ctx.publish("seguridad.hallazgo_critico", {"repo": root.name, "rule": f.rule_id, "file": f.file, "line": f.line})
        return {"summary": summary_line(res), "counts": res.counts(), "skipped": res.skipped, "report": render(res)}

    def execute(self, action: Action, ctx):
        if action.type == "purgar_historial":
            n = ctx.shared.purge([action.data["what"]])
            return f"Listo: borré {n} registros de {action.data['what']}."
        return super().execute(action, ctx)

    def health(self, ctx):
        return Health(True, "ok")


def _key(path) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(path).lower()).strip("_")[-60:] or "repo"


class Pentest(Cook):
    name = "pentest"
    version = "2.0.0"
    description = "Pentest activo (nmap, ZAP, sqlmap) sobre objetivos que Damián autorizó. Solo en su PC y con aprobación por corrida."
    commands = {"pentest_proponer": "propone una corrida {'kind': nmap|zap|sqlmap, 'target', 'option'} (pide aprobación)",
                "pentest_estado": "estado: edición, adaptador y objetivos autorizados", "pentest_resultados": "resultados guardados"}

    def interest(self, msg, ctx):
        return 0.6 if _owner_only(msg) and re.search(r"pentest|nmap|escane|sqlmap", normalize(msg.text)) else 0.0

    def handle(self, msg, ctx):
        if self.interest(msg, ctx) == 0:
            return None
        if edition_of(ctx) != "personal":
            return Reply("El pentest activo no corre acá: solo en tu PC, nunca en el servidor.")
        return Reply("Puedo proponer un escaneo; cada corrida te la pido aprobar y solo va a objetivos de tu lista autorizada. Decime el objetivo y el tipo (nmap, zap o sqlmap).")

    def command(self, name, data, ctx):
        s = Settings.build(ctx.config)
        if name == "pentest_estado":
            ed = edition_of(ctx)
            return {"edition": ed, "disponible": ed == "personal", "adaptador": s.env.get("SEGURIDAD_PENTEST_ADAPTER", "real"),
                    "objetivos_autorizados_archivo": s.targets_file or "(sin archivo: solo red privada, loopback y Tailscale)"}
        if name == "pentest_resultados":
            return _query(ctx, "pentests", data)
        if name == "pentest_proponer":
            kind, target, option = str(data.get("kind", "")), str(data.get("target", "")), str(data.get("option", ""))
            try:
                ensure_local_edition(edition_of(ctx))
                authorize(target, s.targets_file)
            except (NotLocalEdition, TargetNotAuthorized) as exc:
                raise ActionError(str(exc)) from None
            if kind not in ("nmap", "zap", "sqlmap"):
                raise ActionError("kind tiene que ser nmap, zap o sqlmap")
            return ctx.request(Action("pentest_corrida", {"kind": kind, "target": target, "option": option},
                                      f"Escaneo {kind} sobre {target}", origin=Origin.OWNER))
        return super().command(name, data, ctx)

    def execute(self, action: Action, ctx):
        if action.type != "pentest_corrida":
            return super().execute(action, ctx)
        s = Settings.build(ctx.config)
        d = action.data
        try:   # se vuelve a validar al ejecutar: la lista o la edición pudieron cambiar mientras esperaba el OK
            found = run_pentest(d["kind"], d["target"], edition=edition_of(ctx), env=s.env, authorized_file=s.targets_file,
                                option=d.get("option", ""))
        except (NotLocalEdition, TargetNotAuthorized, PentestUnavailable, ValueError) as exc:
            raise ActionError(str(exc)) from None
        n = ctx.shared.next("pentests")
        found = sort_findings(found)
        ctx.shared.put("pentests", n, {"n": n, "kind": d["kind"], "target": d["target"], "at": ctx.now().isoformat(timespec="seconds"),
                                       "simulated": any(f.simulated for f in found), "findings": [f.to_dict() for f in found]})
        ctx.publish("seguridad.pentest_terminado", {"n": n, "kind": d["kind"], "counts": _summ([f.to_dict() for f in found])})
        sim = " (SIMULADO: no son datos reales)" if any(f.simulated for f in found) else ""
        return f"Pentest #{n} ({d['kind']}) terminado{sim}: {len(found)} hallazgos."

    def health(self, ctx):
        return Health(True, "pasivo: el pentest no corre acá" if edition_of(ctx) != "personal" else "ok")


class Watch(Cook):
    name = "vigilancia"
    version = "2.0.0"
    description = "Vigila la propia instalación: logins fallidos, tokens por vencer, certificado, servicio y backups. Avisa, no actúa."
    commands = {"vigilar": "corre los chequeos ahora", "alertas": "alertas abiertas"}

    def interest(self, msg, ctx):
        return 0.5 if _owner_only(msg) and re.search(r"vigilancia|alertas?|certificado|backups?", normalize(msg.text)) else 0.0

    def handle(self, msg, ctx):
        if self.interest(msg, ctx) == 0:
            return None
        open_ = ctx.shared.list("alertas", state="open")
        return Reply("No hay alertas abiertas." if not open_ else f"Hay {len(open_)} alertas abiertas: " + "; ".join(a["message"] for a in open_[:3]))

    def on_event(self, event, data, ctx):
        if event == "acceso.fallido":
            n = ctx.shared.next("accesos")
            ctx.shared.put("accesos", n, {"n": n, "at": ctx.now().isoformat(timespec="seconds"),
                                          "source": str(data.get("source") or data.get("ip") or "?")[:80]})

    def command(self, name, data, ctx):
        if name == "alertas":
            return ctx.shared.list("alertas", state="open")
        if name == "vigilar":
            return self.sweep(ctx)
        return super().command(name, data, ctx)

    def tick(self, now: datetime, ctx):
        mins = int(Settings.build(ctx.config).watch.get("interval_minutes", 15))
        last = ctx.shared.get("estado", "ultima_vigilancia")
        if last and (now - datetime.fromisoformat(last["at"])).total_seconds() < mins * 60:
            return
        self.sweep(ctx)

    def sweep(self, ctx) -> dict:
        s = Settings.build(ctx.config)
        now = ctx.now()
        for e in ctx.shared.list("accesos"):   # los intentos viejos no hacen falta: se guarda un día
            if (now - datetime.fromisoformat(e["at"])).total_seconds() > 86400:
                ctx.shared.delete("accesos", e["n"])
        found = run_watch(s.watch, probes_from_env(s.env), now, ctx.shared.list("accesos"))
        ctx.shared.put("estado", "ultima_vigilancia", {"at": now.isoformat(timespec="seconds")})
        live = {f.id for f in found}
        for a in ctx.shared.list("alertas", state="open"):   # lo que ya no se ve, se cierra solo
            if a["id"] not in live:
                ctx.shared.put("alertas", a["id"], {**a, "state": "resuelta", "closed": now.isoformat(timespec="seconds")})
        new = 0
        for f in sort_findings(found):
            prev = ctx.shared.get("alertas", f.id)
            fresh = prev is None or prev["state"] != "open" or \
                (now - datetime.fromisoformat(prev["notified"])).total_seconds() > COOLDOWN_HOURS * 3600
            doc = {**f.to_dict(), "state": "open", "first": (prev or {}).get("first", now.isoformat(timespec="seconds")),
                   "notified": now.isoformat(timespec="seconds") if fresh else prev["notified"]}
            ctx.shared.put("alertas", f.id, doc)
            if fresh:
                new += 1
                ctx.publish("seguridad.alerta", {"severity": f.severity, "rule": f.rule_id, "message": f.message, "fix": f.fix})
        return {"alertas": len(found), "nuevas": new}

    def health(self, ctx):
        return Health(True, "ok")
