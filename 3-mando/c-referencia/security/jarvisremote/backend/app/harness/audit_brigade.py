"""La Brigada de Auditoría, ensamblada como un DAG sobre el harness (Fase C del
spec + BRIGADA-AUDITORIA.md). Cada estación es un `Agent` que envuelve la función
YA EXISTENTE y probada de `audit_report.py`/`security/` -- no reinventa nada, solo
la vuelve "encajable" en el grafo. El orquestador corre las estaciones en orden.

Flujo (DAG):

    E1 Reconocimiento ─┐
                       ├─► E3 Triage ─► E2 Contexto ─► E5 Redacción ─► E6 Catador ─► E7 Pase
    E4 Config ─────────┘                     └──────────────────────────────┘

ADITIVO y AISLADO: este módulo NO se importa al arrancar el backend ni reemplaza
`generate_client_report` (que sigue siendo el camino de producción). Es la versión
orquestada, para activar cuando se valide contra el backend en vivo. Las estaciones
read-only (escaneo, triage) comparten el checkout: no necesitan git worktrees (esos
son para estaciones que MODIFican archivos, ej. una brigada de reparación futura).

Testeable: cada estación acepta sus funciones-núcleo por inyección (defaults = las
reales), así el DAG completo se prueba con fakes sin tocar LLM ni escáneres.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .. import audit_report as ar
from ..config import settings  # noqa: F401  (referencia para routing futuro)
from ..findings.noise import split_noise
from ..obsidian import vault
from ..quality import store as quality_store
from ..security import config_check
from ..security import store as security_store
from ..security import triage
from .blackboard import ExecutionStore, MemoryBlackboard
from .contracts import AgentResult, Node, Task
from .orchestrator import Budget, Orchestrator, RunReport

logger = logging.getLogger("jarvis.harness.audit")

# Nombres de nodo (estables: las estaciones leen la pizarra por estos nombres).
E1 = "E1_reconocimiento"
E2 = "E2_contexto"
E3 = "E3_triage"
E4 = "E4_config"
E5 = "E5_redaccion"
E6 = "E6_catador"
E7 = "E7_pase"


def _root_of(task: Task) -> Path:
    return Path(task.payload["repo_path"]).resolve()


def _station_model(name: str):
    """(capa A parte 2) Devuelve (cliente, modelo) del registro para esta estación
    si tiene un modelo PROPIO asignado; (None, None) si usa el global — así las
    funciones LLM caen a su cliente/modelo de siempre sin construir uno duplicado.
    Import perezoso del singleton para no acoplar el import a nivel de módulo."""
    from .model_registry import registry
    if name in registry.overrides():
        return registry.client_for(name)
    return None, None


def _station_candidates(name: str, tier: int):
    """(2026-09-29) Candidatos (cliente, modelo) EN ORDEN para el fallback en
    cascada de una estación LLM: el primario (override explícito o default global)
    y después los fallbacks del tier. El caller prueba en orden y para en el primero
    que no falla. Ver model_registry.candidates_for."""
    from .model_registry import registry
    return registry.candidates_for(name, tier)


# --- E1 · Reconocimiento (tier 0) ---------------------------------------------
class ScanStation:
    """Junta los hallazgos crudos de los escáneres ya corridos (cache de
    security/quality store). Correr los escáneres es la tool `security_scan_project`
    (paso previo); acá se cargan, igual que hace `generate_client_report`."""

    name = E1
    tier = 0
    tools = ["security_scan_project", "quality_scan_project"]

    def __init__(self, load_sec=None, load_qual=None) -> None:
        self._load_sec = load_sec or security_store.load_scan
        self._load_qual = load_qual or quality_store.load_scan

    async def run(self, task: Task, bb) -> AgentResult:
        root = _root_of(task)
        if not root.is_dir():
            return AgentResult.fail(f"no es una carpeta: {root}")
        sec = self._load_sec(root)
        qual = self._load_qual(root)
        if sec is None and qual is None:
            return AgentResult.fail(
                "No hay escaneos guardados; corré security_scan_project/quality_scan_project antes."
            )
        return AgentResult(
            ok=True,
            output={
                "root": str(root),
                "sec_findings": list(sec.findings) if sec else [],
                "qual_findings": list(qual.findings) if qual else [],
                "sec_scanned_at": sec.scanned_at if sec else None,
                "sec_tools": list(sec.tools_run) if sec else [],
                "qual_scanned_at": qual.scanned_at if qual else None,
                "qual_tools": list(qual.tools_run) if qual else [],
                "chat": [{"rol": "sistema", "texto": f"Cargué {len(sec.findings) if sec else 0} hallazgos de seguridad y {len(qual.findings) if qual else 0} de calidad de los escáneres."}],
            },
        )


# --- E4 · Config checker (tier 0) ---------------------------------------------
class ConfigStation:
    """Chequeo determinista de configuración (E4). Corre en paralelo a E1."""

    name = E4
    tier = 0
    tools = []

    def __init__(self, scan=None) -> None:
        self._scan = scan or config_check.scan_config

    async def run(self, task: Task, bb) -> AgentResult:
        root = _root_of(task)
        findings = list(self._scan(root))
        return AgentResult(
            ok=True,
            output={
                "config_findings": findings,
                "chat": [{"rol": "sistema", "texto": f"Chequeo de configuración: {len(findings)} hallazgo(s) (DEBUG, SECRET_KEY, archivos sensibles…)."}],
            },
        )


# --- E3 · Triage (tier 2) -----------------------------------------------------
class TriageStation:
    """Une hallazgos de E1 + E4, saca el ruido conocido, y triagea con el LLM los
    que importan (leyendo el código real). Best-effort: si el triage falla, sigue
    con los crudos. Mismo criterio que `generate_client_report`."""

    name = E3
    tier = 3
    tools = ["security_get_finding"]

    def __init__(self, triage_fn=None, split=None) -> None:
        self._triage = triage_fn or triage.triage_findings
        self._split = split or split_noise

    async def run(self, task: Task, bb) -> AgentResult:
        e1 = bb.read(E1) or {}
        e4 = bb.read(E4) or {}
        root = Path(e1.get("root") or task.payload["repo_path"]).resolve()

        sec_raw = list(e1.get("sec_findings", [])) + list(e4.get("config_findings", []))
        qual_raw = list(e1.get("qual_findings", []))
        sec_real, _ = self._split(sec_raw)
        qual_real, _ = self._split(qual_raw)

        to_triage = [
            f for f in sec_real
            if f.triage_status is None and f.severity in ar._TRIAGE_SEVERITIES
        ][: ar._MAX_AUTO_TRIAGE]
        if to_triage:
            triaged = None
            for llm, model in _station_candidates(self.name, self.tier):
                try:
                    triaged = await self._triage(root, to_triage, llm=llm, model=model)
                    break
                except Exception:  # noqa: BLE001 -- fallback: pruebo el siguiente del tier
                    logger.warning("E3 triage falló con %s; pruebo el siguiente del tier.", model)
            if triaged is not None:
                by_id = {f.id: f for f in triaged}
                sec_real = [by_id.get(f.id, f) for f in sec_real]
            else:
                logger.error("E3 triage falló con todos los modelos del tier; sigo sin triagear.")

        sec_fp = [f for f in sec_real if f.triage_status == "false_positive"]
        sec_active_all = [f for f in sec_real if f.triage_status != "false_positive"]
        return AgentResult(
            ok=True,
            output={
                "root": str(root),
                "sec_active_all": sec_active_all,
                "sec_fp": sec_fp,
                "qual_real": qual_real,
                "triaged": len(to_triage),
                "chat": [
                    {"rol": "usuario", "texto": f"Triageá {len(to_triage)} hallazgo(s) importante(s) leyendo el código real, distinguí reales de falsos positivos."},
                    {"rol": "raphael", "texto": f"Revisados {len(to_triage)}: {len(sec_active_all)} reales, {len(sec_fp)} falso(s) positivo(s) descartado(s)."},
                ],
            },
        )


# --- E2 · Contexto por ruta (tier 0) ------------------------------------------
class ContextStation:
    """Separa producción de no-producción (tests/examples/docs/vendor). Solo lo de
    producción entra en los riesgos prioritarios del cliente."""

    name = E2
    tier = 0
    tools = []

    def __init__(self, is_production=None) -> None:
        self._is_prod = is_production or ar._is_production

    async def run(self, task: Task, bb) -> AgentResult:
        e3 = bb.read(E3) or {}
        active_all = e3.get("sec_active_all", [])
        sec_active = [f for f in active_all if self._is_prod(f)]
        sec_nonprod = [f for f in active_all if not self._is_prod(f)]
        return AgentResult(
            ok=True,
            output={
                "sec_active": sec_active,
                "sec_nonprod": sec_nonprod,
                "chat": [{"rol": "sistema", "texto": f"Separé por ruta: {len(sec_active)} en producción, {len(sec_nonprod)} fuera (tests/examples/docs)."}],
            },
        )


# --- E5 · Redacción (tier 2) --------------------------------------------------
class NarrativeStation:
    """Escribe el resumen ejecutivo + riesgos prioritarios en criollo. Best-effort:
    si el LLM no responde, `narrative` queda None y E7 cae al resumen mecánico."""

    name = E5
    tier = 3
    tools = []

    def __init__(self, build_digest=None, narrate=None) -> None:
        self._digest = build_digest or ar._build_llm_digest
        self._narrate = narrate or ar._client_narrative

    async def run(self, task: Task, bb) -> AgentResult:
        e2 = bb.read(E2) or {}
        e3 = bb.read(E3) or {}
        sec_active = e2.get("sec_active", [])
        qual_real = e3.get("qual_real", [])
        project = _root_of(task).name
        digest = self._digest(sec_active, qual_real)
        narrative = None
        for llm, model in _station_candidates(self.name, self.tier):
            try:
                narrative = await self._narrate(project, digest, llm=llm, model=model)
                break
            except Exception:  # noqa: BLE001 -- fallback: pruebo el siguiente del tier
                logger.warning("E5 redacción falló con %s; pruebo el siguiente del tier.", model)
        if narrative is None:
            logger.error("E5 redacción falló con todos los modelos del tier; sigo sin narrativa.")
        chat = [
            {"rol": "usuario", "texto": "Redactá el informe (resumen ejecutivo + riesgos prioritarios) con estos hallazgos:\n" + (digest or "(sin hallazgos)")},
            {"rol": "raphael", "texto": narrative or "(no se generó narrativa; se cae al resumen mecánico)"},
        ]
        return AgentResult(ok=True, output={"narrative": narrative, "chat": chat})


# --- E6 · Catador / QA (tier 2) -----------------------------------------------
class CatadorStation:
    """Verifica la narrativa contra el código real y corrige lo que el código no
    respalde. Best-effort: ante cualquier fallo, deja la narrativa original."""

    name = E6
    tier = 3
    tools = []

    def __init__(self, build_evidence=None, review=None) -> None:
        self._evidence = build_evidence or ar._build_evidence
        self._review = review or ar._catador_review

    async def run(self, task: Task, bb) -> AgentResult:
        e5 = bb.read(E5) or {}
        e2 = bb.read(E2) or {}
        narrative = e5.get("narrative")
        sec_active = e2.get("sec_active", [])
        root = _root_of(task)

        corrections: list[str] = []
        ran = False
        final = narrative
        if narrative:
            try:
                evidence = self._evidence(root, sec_active)
            except Exception:  # noqa: BLE001 -- sin evidencia no hay nada que contrastar
                logger.exception("E6 catador: no pude armar la evidencia; dejo la narrativa original.")
                evidence = ""
            if evidence.strip():
                reviewed = False
                for llm, model in _station_candidates(self.name, self.tier):
                    try:
                        final, corrections = await self._review(root.name, narrative, evidence, llm=llm, model=model)
                        ran, reviewed = True, True
                        break
                    except Exception:  # noqa: BLE001 -- fallback: pruebo el siguiente del tier
                        logger.warning("E6 catador falló con %s; pruebo el siguiente del tier.", model)
                if not reviewed:
                    logger.error("E6 catador falló con todos los modelos del tier; dejo la narrativa original.")
                    final, corrections, ran = narrative, [], False
        if not ran:
            catador_txt = "No verifiqué (sin evidencia de código para contrastar)."
        elif corrections:
            catador_txt = "Corregí el informe contra el código real:\n" + "\n".join(f"- {c}" for c in corrections)
        else:
            catador_txt = "Verifiqué cada afirmación contra el código: sin discrepancias."
        chat = [
            {"rol": "usuario", "texto": "Verificá este informe contra el código real y corregí lo que no esté respaldado."},
            {"rol": "raphael", "texto": catador_txt},
        ]
        return AgentResult(
            ok=True,
            output={"narrative_final": final, "corrections": corrections, "catador_ran": ran, "chat": chat},
        )


# --- E7 · Pase / Agregador (tier 0) -------------------------------------------
class AssembleStation:
    """Ensambla el reporte final (mismo formato que `generate_client_report`) y lo
    guarda como nota en el vault. Determinista."""

    name = E7
    tier = 0
    tools = []

    def __init__(self, save_note=None) -> None:
        self._save = save_note or vault.save_note

    async def run(self, task: Task, bb) -> AgentResult:
        root = _root_of(task)
        e1 = bb.read(E1) or {}
        e2 = bb.read(E2) or {}
        e3 = bb.read(E3) or {}
        e6 = bb.read(E6) or {}

        sec_active = e2.get("sec_active", [])
        sec_nonprod = e2.get("sec_nonprod", [])
        sec_fp = e3.get("sec_fp", [])
        qual_findings = e3.get("qual_real", [])
        narrative = e6.get("narrative_final")
        corrections = e6.get("corrections", [])
        catador_ran = e6.get("catador_ran", False)
        triaged = e3.get("triaged", 0)

        generated_at = datetime.now(timezone.utc).isoformat()
        lines = [f"# Reporte de auditoría de código -- {root.name}", ""]
        lines.append(f"- Proyecto: `{root}`")
        lines.append(f"- Generado: {generated_at}")
        if e1.get("sec_scanned_at"):
            lines.append(
                f"- Escaneo de seguridad: {e1['sec_scanned_at']} "
                f"(corrieron: {', '.join(e1.get('sec_tools') or []) or 'ninguno'})"
            )
        if e1.get("qual_scanned_at"):
            lines.append(
                f"- Escaneo de calidad: {e1['qual_scanned_at']} "
                f"(corrieron: {', '.join(e1.get('qual_tools') or []) or 'ninguno'})"
            )
        if triaged:
            lines.append(
                f"- Triage de falsos positivos: se revisaron {triaged} hallazgo(s) importante(s) "
                f"mirando el código real; {len(sec_fp)} descartado(s)."
            )
        lines.append("")
        lines.append(ar._test_status_line(root))
        lines.append("")

        if narrative:
            lines.append(narrative)
            lines.append("")
        else:
            counts = ar._severity_counts(sec_active)
            lines.append("## Resumen ejecutivo")
            lines.append("")
            lines.append(
                f"{len(sec_active)} hallazgo(s) de seguridad real(es) tras triage "
                f"({counts.get('critical', 0)} crítico(s), {counts.get('high', 0)} alto(s)). "
                "_(La narrativa automática no estuvo disponible; ver el anexo técnico.)_"
            )
            lines.append("")

        lines += ar._catador_section(corrections, catador_ran)
        lines.append("## Anexo técnico -- hallazgos")
        lines.append("")
        lines += ar._findings_table("Hallazgos de seguridad (reales, tras triage)", sec_active)
        lines += ar._nonprod_section(sec_nonprod)
        lines += ar._fp_table(sec_fp)
        lines += ar._findings_table("Hallazgos de calidad", qual_findings)

        content = "\n".join(lines)
        note = self._save(
            title=f"Reporte de auditoría (cliente) -- {root.name} -- {generated_at[:10]}",
            content=content,
            author="jarvis",
            tags=["reportes", "auditoria", "seguridad", "cliente"],
        )
        return AgentResult(
            ok=True,
            output={
                "note_id": getattr(note, "id", None),
                "note_title": getattr(note, "title", None),
                "content": content,
                "security_findings_real": len(sec_active),
                "false_positives": len(sec_fp),
                "nonproduction_findings": len(sec_nonprod),
                "catador_corrections": corrections,
                "chat": [{"rol": "sistema", "texto": f"Armé el reporte final y lo guardé como nota '{getattr(note, 'id', None)}' en el vault."}],
            },
            artifacts=[getattr(note, "id", "") or ""],
        )


def build_audit_dag(stations: dict[str, Any] | None = None) -> list[Node]:
    """Arma el DAG de la brigada. `stations` permite inyectar estaciones fake para
    testear el grafo sin LLM ni escáneres (default: las estaciones reales)."""
    s = stations or {}
    e1 = s.get(E1) or ScanStation()
    e4 = s.get(E4) or ConfigStation()
    e3 = s.get(E3) or TriageStation()
    e2 = s.get(E2) or ContextStation()
    e5 = s.get(E5) or NarrativeStation()
    e6 = s.get(E6) or CatadorStation()
    e7 = s.get(E7) or AssembleStation()
    return [
        Node(e1, on_error="abort"),
        Node(e4, on_error="skip"),  # config es un plus; si falla, el reporte sigue
        Node(e3, depends_on=[E1, E4], on_error="abort"),
        Node(e2, depends_on=[E3], on_error="abort"),
        Node(e5, depends_on=[E2, E3], on_error="skip"),  # narrativa best-effort
        Node(e6, depends_on=[E5, E2], on_error="skip"),  # catador best-effort
        Node(e7, depends_on=[E6, E2, E3, E1], on_error="abort"),
    ]


async def run_audit_brigade(
    repo_path: str,
    stations: dict[str, Any] | None = None,
    budget: Budget | None = None,
) -> dict[str, Any]:
    """Corre la brigada completa sobre `repo_path` y devuelve el resultado de E7
    (el reporte) + el resumen de la corrida. E4 depende de E1 en el grafo solo por
    orden de lectura de la pizarra; en realidad ambos dependen del repo, no entre sí."""
    nodes = build_audit_dag(stations)
    task = Task(id=f"audit:{Path(repo_path).name}", payload={"repo_path": repo_path})
    bb = MemoryBlackboard()
    store = ExecutionStore()
    report: RunReport = await Orchestrator("auditoria").run(nodes, task, bb=bb, store=store, budget=budget)

    e7_rec = store.get(E7)
    out = e7_rec.output if (e7_rec and e7_rec.ok) else {}

    # Estado por estación (para la console multiagente): las 7 en orden, con su
    # estado real de la corrida. JSON-safe (sin objetos Finding).
    stations = []
    for name in (E1, E4, E3, E2, E5, E6, E7):
        rec = store.get(name)
        if rec is not None:
            estado = "ok" if rec.ok else ("abortada" if name in report.aborted else "fallo")
            chat = rec.output.get("chat", []) if isinstance(rec.output, dict) else []
            stations.append({"estacion": name, "estado": estado, "segundos": round(rec.seconds, 2), "error": rec.error, "chat": chat})
        elif name in report.skipped:
            stations.append({"estacion": name, "estado": "salteada", "segundos": 0.0, "error": None, "chat": []})
        else:
            stations.append({"estacion": name, "estado": "no-corrio", "segundos": 0.0, "error": None, "chat": []})

    return {
        "ok": report.ok,
        "run_summary": report.summary,
        "stations": stations,
        "report": out,
    }
