"""Compila un reporte legible (Markdown) de auditoría de código para un
proyecto: hallazgos abiertos (seguridad + calidad), qué fixes/ediciones ya se
aplicaron (con su commit de git, todos revertibles) y un resumen ejecutivo.
Se guarda como nota en el vault de Obsidian (autor "jarvis", ver
`app/obsidian/vault.py`) para que quede versionado y visible en la pestaña
Obsidian de la UI -- no solo como texto de chat que se pierde apenas se cierra
la conversación.

Lee del cache de escaneos (`security/store.py`, `quality/store.py`) y del log
de auditoría (`audit_log.read_entries`) -- no vuelve a correr ningún escáner
ni inventa qué se aplicó, solo compila lo que ya quedó registrado.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import audit_log
from .config import settings
from .findings.models import Finding
from .findings.noise import KNOWN_NOISE_RULES as _KNOWN_NOISE_RULES
from .findings.noise import SEVERITY_ORDER as _SEVERITY_ORDER
from .findings.noise import split_noise as _split_noise
from .llm_client import client
from .obsidian import vault
from .quality import store as quality_store
from .security import config_check
from .security import store as security_store
from .security import triage
from .testing import store as test_store

logger = logging.getLogger("jarvis.audit_report")

_MAX_FINDINGS_PER_SECTION = 200
# Cuántos GRUPOS de hallazgos (agrupados por regla) se le pasan al LLM para la
# narrativa. Acotado para que el prompt quede chico y enfocado en lo que importa.
_MAX_DIGEST_GROUPS = 40
# Tope de hallazgos a triagear automáticamente en el reporte client-facing: solo
# los que IMPORTAN (critical/high/medium) y que no estén ya triageados. Cota el
# costo (una llamada al LLM por hallazgo) sin dejar entrar falsos positivos en los
# riesgos prioritarios -- justo el caso del `flask lint` del Test B (2026-09-03).
_MAX_AUTO_TRIAGE = 30
_TRIAGE_SEVERITIES = ("critical", "high", "medium")

# --- E2 (brigada): contexto por ruta (2026-09-06) --------------------------
# Clasifica un hallazgo por DÓNDE vive el archivo. Para un reporte de CLIENTE, lo
# que está en tests/examples/docs/vendor NO es un riesgo de negocio en producción
# (un `debug=True` en la suite de tests del propio framework no es "RCE en
# producción"). Esto NO toca el triage -- que a propósito juzga el patrón sin mirar
# el path (ver security/triage.py) -- solo decide qué entra en los RIESGOS
# PRIORITARIOS que ve el cliente. Motivado por la calibración de flask-oficial
# (2026-09-06): sus "altos" eran debug=True en tests y XSS en examples/.
_NONPROD_CONTEXTS = ("tests", "examples", "docs", "vendor")


def _path_context(file: str) -> str:
    """'production' | 'tests' | 'examples' | 'docs' | 'vendor' según la ruta del
    archivo. Determinista, sin LLM (estación E2 de la brigada de auditoría)."""
    norm = file.replace("\\", "/").lower()
    segments = [s for s in norm.split("/") if s]
    name = segments[-1] if segments else norm
    seg_set = set(segments)
    if (
        seg_set & {"test", "tests", "testing", "__tests__", "spec", "specs"}
        or name.startswith("test_")
        or name.endswith(("_test.py", ".test.js", ".test.ts", ".spec.js", ".spec.ts"))
    ):
        return "tests"
    if seg_set & {"example", "examples", "sample", "samples", "demo", "demos", "tutorial", "tutorials"}:
        return "examples"
    if seg_set & {"doc", "docs", "documentation"}:
        return "docs"
    if seg_set & {
        "vendor", "vendored", "third_party", "third-party", "node_modules",
        "site-packages", "dist", "build", "migrations",
    }:
        return "vendor"
    return "production"


def _is_production(finding: Finding) -> bool:
    return _path_context(finding.file) not in _NONPROD_CONTEXTS


def _severity_counts(findings: list[Finding]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    return counts


def _entry_matches_root(entry: dict, root: Path) -> bool:
    args = entry.get("arguments") or {}
    raw = args.get("path")
    if not raw:
        return False
    try:
        return Path(raw).resolve() == root
    except OSError:
        return False


def _findings_table(title: str, findings: list[Finding]) -> list[str]:
    lines = [f"## {title} ({len(findings)})", ""]
    if not findings:
        lines.append("Ninguno.")
        lines.append("")
        return lines

    lines.append("| Severidad | Archivo | Línea | Regla (herramienta) | Mensaje |")
    lines.append("|---|---|---|---|---|")
    # El ruido conocido (ver _KNOWN_NOISE_RULES) se ordena al final de la tabla,
    # después de todo lo demás por severidad -- sigue visible, pero no compite
    # por atención con los hallazgos reales.
    ordered = sorted(
        findings,
        key=lambda f: (f.rule_id in _KNOWN_NOISE_RULES, _SEVERITY_ORDER.get(f.severity, 9), f.file, f.line),
    )
    for f in ordered[:_MAX_FINDINGS_PER_SECTION]:
        msg = f.message.replace("|", "\\|").replace("\n", " ").strip()[:160]
        rule_label = f"`{f.rule_id}` ({f.tool})"
        if f.rule_id in _KNOWN_NOISE_RULES:
            rule_label += " -- ruido conocido"
        lines.append(f"| {f.severity} | `{f.file}` | {f.line} | {rule_label} | {msg} |")
    if len(findings) > _MAX_FINDINGS_PER_SECTION:
        lines.append("")
        lines.append(f"_(+{len(findings) - _MAX_FINDINGS_PER_SECTION} más, omitidos por espacio)_")
    lines.append("")
    return lines


def _test_status_line(root: Path) -> str:
    """Línea de estado de la última corrida de tests real (`code_run_tests` /
    el paso automático dentro de `security_audit_find_fix_verify`) -- agregada
    2026-08-10 para que el reporte NUNCA pueda leerse como "todo resuelto" sin
    decir explícitamente si hubo (o no) una verificación funcional real de por
    medio, no solo análisis estático. A propósito no bloquea/lanza excepción
    si nunca se corrió: muchos proyectos auditados acá (ej. apps
    deliberadamente vulnerables tipo pygoat/NodeGoat, usadas para probar el
    pipeline de seguridad) no tienen ninguna suite de tests real, y eso no
    debería impedir generar el resto del reporte -- solo se marca en voz alta
    en vez de omitirse en silencio."""
    last_run = test_store.load_last_run(root)
    if last_run is None:
        return (
            "⚠ Nunca se corrió una verificación de tests real sobre este proyecto (code_run_tests) -- "
            "los hallazgos de este reporte están basados solo en análisis estático, no en que el "
            "proyecto siga funcionando de verdad."
        )
    if not last_run.detected:
        return (
            f"ℹ No se detectó ninguna suite de tests real en este proyecto (última verificación: "
            f"{last_run.ran_at}) -- no es una falla, simplemente no hay nada que correr."
        )
    if last_run.passed:
        return f"✓ Última corrida de tests real: EN VERDE ({last_run.ran_at}, comando: `{last_run.command}`)."
    return (
        f"✗ Última corrida de tests real: FALLÓ ({last_run.ran_at}, comando: `{last_run.command}`, "
        f"exit_code={last_run.exit_code}) -- no dar este proyecto por estable hasta corregir esto."
    )


def generate_report(path: str) -> dict:
    root = Path(path).resolve()
    if not root.is_dir():
        raise NotADirectoryError(str(root))

    sec_scan = security_store.load_scan(root)
    qual_scan = quality_store.load_scan(root)
    if sec_scan is None and qual_scan is None:
        raise ValueError(
            "No hay escaneos guardados para este proyecto -- corré security_scan_project y/o "
            "quality_scan_project antes de generar el reporte."
        )

    sec_findings = sec_scan.findings if sec_scan else []
    qual_findings = qual_scan.findings if qual_scan else []
    sec_real, sec_noise = _split_noise(sec_findings)
    qual_real, qual_noise = _split_noise(qual_findings)
    sec_counts = _severity_counts(sec_real)
    qual_counts = _severity_counts(qual_real)

    fix_entries = [
        e
        for e in audit_log.read_entries(tool="code_apply_fix")
        if e.get("ok") and (e.get("result") or {}).get("committed") and _entry_matches_root(e, root)
    ]
    edit_entries = [
        e
        for e in audit_log.read_entries(tool="fs_write_file")
        if e.get("ok") and (e.get("result") or {}).get("committed") and _entry_matches_root(e, root)
    ]

    generated_at = datetime.now(timezone.utc).isoformat()

    lines = [f"# Reporte de auditoría de código -- {root.name}", ""]
    lines.append(f"- Proyecto: `{root}`")
    lines.append(f"- Generado: {generated_at}")
    if sec_scan:
        lines.append(
            f"- Último escaneo de seguridad: {sec_scan.scanned_at} "
            f"(corrieron: {', '.join(sec_scan.tools_run) or 'ninguno'})"
        )
    if qual_scan:
        lines.append(
            f"- Último escaneo de calidad: {qual_scan.scanned_at} "
            f"(corrieron: {', '.join(qual_scan.tools_run) or 'ninguno'})"
        )
    lines.append("")

    lines.append("## Resumen ejecutivo")
    lines.append("")
    lines.append(_test_status_line(root))
    lines.append("")
    total_open = len(sec_real) + len(qual_real)
    total_noise = len(sec_noise) + len(qual_noise)
    summary_bits = []
    if sec_real:
        summary_bits.append(
            f"{len(sec_real)} hallazgo(s) de seguridad real(es) "
            f"({sec_counts.get('critical', 0)} crítico(s), {sec_counts.get('high', 0)} alto(s))"
        )
    if qual_real:
        summary_bits.append(
            f"{len(qual_real)} hallazgo(s) de calidad ({qual_counts.get('high', 0)} de severidad 'alta' "
            "según el propio analizador (Ruff/mypy/ESLint/tsc, el que haya corrido) -- no es un nivel de riesgo "
            "de seguridad)"
        )
    if fix_entries or edit_entries:
        summary_bits.append(
            f"{len(fix_entries)} fix(es) y {len(edit_entries)} edición(es) general(es) ya aplicados, "
            "todos revertibles con git revert"
        )
    if total_open == 0 and not summary_bits:
        lines.append("Sin hallazgos abiertos y sin actividad registrada todavía.")
    elif total_open == 0:
        lines.append("Sin hallazgos reales abiertos. " + ". ".join(summary_bits) + ".")
    else:
        lines.append(". ".join(summary_bits) + ".")
    if total_noise:
        noise_rule_ids = sorted({f.rule_id for f in sec_noise + qual_noise})
        noise_desc = "; ".join(f"{rid} ({_KNOWN_NOISE_RULES[rid]})" for rid in noise_rule_ids)
        lines.append("")
        lines.append(
            f"_Se excluyeron {total_noise} hallazgo(s) del conteo de arriba por ser ruido conocido: {noise_desc}. "
            "No se descartaron del escaneo -- siguen en las tablas de detalle más abajo, marcados como tal._"
        )
    lines.append("")

    lines += _findings_table("Hallazgos de seguridad", sec_findings)
    lines += _findings_table("Hallazgos de calidad", qual_findings)

    lines.append(f"## Fixes aplicados ({len(fix_entries)})")
    lines.append("")
    if not fix_entries:
        lines.append("Ninguno todavía.")
    else:
        lines.append("| Commit | Archivo | Mensaje |")
        lines.append("|---|---|---|")
        for e in fix_entries:
            result = e.get("result") or {}
            args = e.get("arguments") or {}
            commit_hash = result.get("commit_hash") or "?"
            file_ = result.get("file") or args.get("file") or "?"
            message = (args.get("commit_message") or "").replace("|", "\\|")
            lines.append(f"| `{commit_hash}` | `{file_}` | {message} |")
    lines.append("")

    lines.append(f"## Ediciones generales auditadas ({len(edit_entries)})")
    lines.append("")
    lines.append(
        "Escrituras vía fs_write_file dentro de este proyecto (ya indexado por Codebase y con git) -- "
        "no vienen de un hallazgo puntual, pero pasan por el mismo circuito auditado y reversible."
    )
    lines.append("")
    if not edit_entries:
        lines.append("Ninguna todavía.")
    else:
        lines.append("| Commit | Archivo |")
        lines.append("|---|---|")
        for e in edit_entries:
            result = e.get("result") or {}
            args = e.get("arguments") or {}
            commit_hash = result.get("commit_hash") or "?"
            file_ = args.get("file") or "?"
            lines.append(f"| `{commit_hash}` | `{file_}` |")
    lines.append("")

    content = "\n".join(lines)
    note = vault.save_note(
        title=f"Reporte de auditoría -- {root.name} -- {generated_at[:10]}",
        content=content,
        author="jarvis",
        tags=["reportes", "auditoria", "seguridad", "calidad"],
    )

    last_test_run = test_store.load_last_run(root)

    return {
        "note_id": note.id,
        "note_title": note.title,
        "project": str(root),
        "security_findings": len(sec_findings),
        "quality_findings": len(qual_findings),
        "fixes_applied": len(fix_entries),
        "general_edits_applied": len(edit_entries),
        "tests": last_test_run.to_dict() if last_test_run else None,
        "content_preview": content[:2000],
    }


# ---------------------------------------------------------------------------
# Capa CLIENT-FACING (2026-09-03): encima del reporte mecánico de arriba, una
# narrativa escrita por el LLM para el DUEÑO de una PyME (no técnico): resumen
# ejecutivo de negocio + riesgos prioritarios explicados en criollo. Las tablas
# crudas quedan como anexo técnico. Es lo que convierte "corrí escáneres" en "te
# entrego una auditoría". No toca `generate_report` (mecánico) para no romper
# nada; es una función NUEVA que la tool usa, con fallback a la mecánica.
# ---------------------------------------------------------------------------

_CONSULTANT_SYSTEM = (
    "Sos un consultor de ciberseguridad escribiendo un informe para el DUEÑO de una PyME, que "
    "NO es técnico. Te paso los hallazgos de una auditoría de código, ya agrupados por tipo. "
    "Escribí en español rioplatense, claro, sin jerga innecesaria. Devolvé SOLO markdown con "
    "EXACTAMENTE estas dos secciones:\n\n"
    "## Resumen ejecutivo\n"
    "2 a 4 frases: qué tan expuesto está el sistema y qué es lo más urgente, en lenguaje de "
    "NEGOCIO (el riesgo real: robo de datos de clientes, toma de control del servidor, caída del "
    "servicio, etc.). NO listes conteos ni nombres de herramientas. Hablale al dueño, no al programador.\n\n"
    "## Riesgos prioritarios\n"
    "Los 5 a 8 más importantes, AGRUPADOS por tipo (no repitas el mismo tipo). Por cada uno, un "
    "subtítulo `### <título claro del riesgo>` y tres líneas en negrita:\n"
    "**Qué es:** una frase simple.\n"
    "**Por qué te importa:** el impacto concreto en el negocio.\n"
    "**Cómo se arregla:** la acción concreta (ej. actualizar tal librería, sacar debug, etc.).\n\n"
    "Reglas: NO inventes hallazgos que no estén en la lista. NO devuelvas tablas ni el detalle "
    "técnico crudo (eso va aparte). Priorizá por riesgo real, no por cantidad."
)


def _build_llm_digest(sec_real: list[Finding], qual_real: list[Finding]) -> str:
    """Agrupa los hallazgos por (herramienta, regla), ordena por severidad y
    cantidad, y arma un texto compacto para pasarle al LLM. Solo seguridad (lo que
    importa para el riesgo); la calidad no entra en la narrativa de negocio."""
    groups: dict[tuple[str, str], list[Finding]] = defaultdict(list)
    for f in sec_real:
        groups[(f.tool, f.rule_id)].append(f)

    rows = []
    for (tool, rule), items in groups.items():
        # min por orden de severidad = la severidad MÁS ALTA del grupo (0=critical).
        top = min(items, key=lambda f: _SEVERITY_ORDER.get(f.severity, 9))
        example = items[0]
        msg = (example.message or "").replace("\n", " ").strip()[:220]
        rows.append(
            (
                _SEVERITY_ORDER.get(top.severity, 9),
                -len(items),
                f"- [{top.severity}] {rule} ({tool}) ×{len(items)} — ej: {example.file}:{example.line} — {msg}",
            )
        )
    rows.sort(key=lambda r: (r[0], r[1]))
    return "\n".join(r[2] for r in rows[:_MAX_DIGEST_GROUPS])


async def _client_narrative(project_name: str, digest: str, llm=None, model: str | None = None) -> str | None:
    """Le pide al LLM la narrativa client-facing (resumen ejecutivo + riesgos
    prioritarios). Best-effort: si el LLM falla o no hay hallazgos, devuelve None
    y el reporte cae a un resumen mecánico simple. `llm`/`model` opcionales
    (capa A parte 2): la estación E5 puede usar su propio modelo/endpoint."""
    if not digest.strip():
        return None
    try:
        resp = await (llm or client).chat.completions.create(
            model=model or settings.lmstudio_model,
            messages=[
                {"role": "system", "content": _CONSULTANT_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"Proyecto auditado: {project_name}\n\n"
                        f"Hallazgos de seguridad agrupados (severidad, regla, herramienta, cantidad, "
                        f"ejemplo de ubicación y mensaje):\n{digest}"
                    ),
                },
            ],
            temperature=0.4,
        )
        text = (resp.choices[0].message.content or "").strip()
        return text or None
    except Exception:  # noqa: BLE001 -- narrativa best-effort; nunca tira el reporte
        logger.exception("No se pudo generar la narrativa client-facing del reporte.")
        return None


def _fp_table(fps: list[Finding]) -> list[str]:
    """Sección de hallazgos DESCARTADOS por el triage (falsos positivos). Se
    muestran igual, con la RAZÓN concreta, por transparencia -- nunca se borran."""
    if not fps:
        return []
    lines = [
        f"### Descartados por triage -- falsos positivos ({len(fps)})",
        "",
        "El análisis miró el código real alrededor de estos hallazgos y los descartó. "
        "Se listan por transparencia (con la razón), no cuentan como riesgo:",
        "",
        "| Archivo | Línea | Regla (herramienta) | Razón del descarte |",
        "|---|---|---|---|",
    ]
    for f in sorted(fps, key=lambda x: (x.file, x.line)):
        reason = (f.triage_reasoning or "").replace("|", "\\|").replace("\n", " ").strip()[:220]
        lines.append(f"| `{f.file}` | {f.line} | `{f.rule_id}` ({f.tool}) | {reason} |")
    lines.append("")
    return lines


# ---------------------------------------------------------------------------
# E6 (brigada): el Catador / QA (2026-09-06, QW-3). Verifica la narrativa
# client-facing contra el CÓDIGO REAL antes de entregarla. Nació de la
# calibración de flask-oficial: la narrativa dijo "sesiones con MD5" cuando el
# código es `hashlib.sha1`, y "RCE en producción" para un `debug=True` que estaba
# en tests. El Catador recibe la narrativa + fragmentos del código real de los
# hallazgos y corrige toda afirmación que el código no respalde. Es la estación
# que convierte "la IA redacta" en "la IA redacta y se verifica sola". Best-effort:
# ante cualquier fallo, devuelve la narrativa original sin romper el reporte.
# ---------------------------------------------------------------------------

_MAX_EVIDENCE_FINDINGS = 12

_CATADOR_SYSTEM = (
    "Sos un revisor senior de ciberseguridad haciendo control de calidad de un INFORME que va a "
    "un cliente. Te paso (A) el borrador del informe y (B) fragmentos del CÓDIGO REAL de los "
    "hallazgos citados. Tu trabajo es que el informe NO diga nada que el código no respalde. "
    "Corregí, SIN agregar riesgos nuevos:\n"
    "1) Todo detalle técnico que el código contradiga. Ej: si el informe dice 'MD5' pero el código "
    "muestra `sha1`, corregilo al algoritmo real. No afirmes un dato que no esté en el código.\n"
    "2) Toda exageración de impacto que el código no sostenga (ej. llamar 'RCE en producción' a algo "
    "que no lo es).\n"
    "3) Si un riesgo se apoya SOLO en código marcado como no productivo (tests/examples/docs), bajale "
    "el tono o sacalo de los riesgos prioritarios: no es un riesgo de negocio en producción.\n\n"
    "NO inventes hallazgos, NO agregues secciones, NO cambies el formato. Dejá el informe casi igual "
    "salvo las correcciones necesarias. Respondé SOLO un objeto JSON, nada alrededor:\n"
    '{"corrected_report": "<el markdown corregido, completo>", "corrections": ["<qué corregiste, una línea c/u>"]}\n'
    "Si no hay nada que corregir, devolvé el informe tal cual en corrected_report y corrections vacío."
)


def _build_evidence(root: Path, findings: list[Finding]) -> str:
    """Fragmentos de código real (numerados, la línea marcada con '>>') de los
    hallazgos activos, para que el Catador contraste la narrativa contra el código.
    Reusa `triage._code_context`. Acotado a los N más severos."""
    ordered = sorted(findings, key=lambda f: _SEVERITY_ORDER.get(f.severity, 9))
    blocks = []
    for f in ordered[:_MAX_EVIDENCE_FINDINGS]:
        ctx = _path_context(f.file)
        label = "" if ctx == "production" else f" [ruta NO productiva: {ctx}]"
        snippet = triage._code_context(root, f)
        blocks.append(
            f"### {f.rule_id} ({f.tool}) — {f.file}:{f.line}{label}\n"
            f"Mensaje del escáner: {f.message.strip()[:200]}\n"
            f"Código real:\n{snippet}"
        )
    return "\n\n".join(blocks)


async def _catador_review(project_name: str, narrative: str, evidence: str, llm=None, model: str | None = None) -> tuple[str, list[str]]:
    """Estación Catador (E6): valida y corrige la narrativa contra el código real.
    Devuelve (narrativa_final, correcciones). Best-effort: ante cualquier fallo
    devuelve la narrativa original y sin correcciones -- nunca tira el reporte."""
    if not narrative.strip() or not evidence.strip():
        return narrative, []
    try:
        resp = await (llm or client).chat.completions.create(
            # Tier 2 de la brigada: acá es donde conviene enchufar un modelo de
            # razonamiento (DeepSeek R1 / frontier), ver F1-6 del roadmap.
            model=model or settings.lmstudio_model,
            messages=[
                {"role": "system", "content": _CATADOR_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"Proyecto: {project_name}\n\n"
                        f"=== A) BORRADOR DEL INFORME ===\n{narrative}\n\n"
                        f"=== B) CÓDIGO REAL DE LOS HALLAZGOS ===\n{evidence}"
                    ),
                },
            ],
            temperature=0,
        )
        content = (resp.choices[0].message.content or "").strip()
        start = content.index("{")
        end = content.rindex("}") + 1
        data = json.loads(content[start:end])
        corrected = str(data.get("corrected_report") or "").strip()
        corrections = [str(c).strip() for c in (data.get("corrections") or []) if str(c).strip()]
        if not corrected:
            return narrative, []
        return corrected, corrections
    except Exception:  # noqa: BLE001 -- QA best-effort; nunca tira el reporte
        logger.exception("El Catador (QA del reporte) falló; devuelvo la narrativa sin verificar.")
        return narrative, []


def _catador_section(corrections: list[str], ran: bool) -> list[str]:
    """Nota de transparencia: qué corrigió el Catador. Si no corrigió nada pero
    corrió, deja constancia de que verificó igual (eso también es señal de calidad)."""
    if not ran:
        return []
    lines = ["## Verificación (Catador)", ""]
    if not corrections:
        lines.append(
            "Se verificó cada afirmación del informe contra el código real. No se encontraron "
            "discrepancias que corregir."
        )
    else:
        lines.append(
            "Antes de entregar, se contrastó el informe contra el código real y se corrigieron estas "
            "afirmaciones (transparencia):"
        )
        lines.append("")
        for c in corrections:
            lines.append(f"- {c}")
    lines.append("")
    return lines


def _nonprod_section(nonprod: list[Finding]) -> list[str]:
    """Hallazgos en código NO productivo (tests/examples/docs/vendor). No son
    riesgo de negocio en producción; se listan aparte, fuera de los riesgos
    prioritarios. Motivado por flask-oficial (debug=True en tests, XSS en examples)."""
    if not nonprod:
        return []
    lines = [
        f"### Hallazgos en código no productivo ({len(nonprod)})",
        "",
        "Estos hallazgos están en archivos de test, ejemplos, documentación o dependencias de "
        "terceros -- no son un riesgo de tu sistema en producción. Se listan aparte por completitud:",
        "",
        "| Contexto | Archivo | Línea | Regla (herramienta) |",
        "|---|---|---|---|",
    ]
    for f in sorted(nonprod, key=lambda x: (x.file, x.line)):
        lines.append(f"| {_path_context(f.file)} | `{f.file}` | {f.line} | `{f.rule_id}` ({f.tool}) |")
    lines.append("")
    return lines


async def generate_client_report(path: str) -> dict:
    """Camino de auditoría CLIENT-FACING. Desde 2026-09-21 DELEGA en la brigada
    (el DAG de estaciones, ver `app/harness/audit_brigade.py`), validada en vivo
    sobre pygoat. Si la brigada no completa o falla por lo que sea, cae al pipeline
    lineal probado de siempre (`_generate_client_report_linear`). Es la convergencia
    (mejora #1): un solo punto de entrada, la brigada como camino real, el lineal
    como red de seguridad. Import perezoso de la brigada para no crear un ciclo
    (audit_brigade importa este módulo)."""
    try:
        from .harness.audit_brigade import run_audit_brigade

        brig = await run_audit_brigade(path)
        rep = brig.get("report") or {}
        if not brig.get("ok") or not rep.get("note_id"):
            raise RuntimeError("la brigada no completó el reporte (caigo al lineal)")
        return {
            "note_id": rep.get("note_id"),
            "note_title": rep.get("note_title"),
            "project": str(Path(path).resolve()),
            "security_findings_real_after_triage": rep.get("security_findings_real"),
            "false_positives_discarded": rep.get("false_positives"),
            "nonproduction_findings": rep.get("nonproduction_findings"),
            "catador_corrections": rep.get("catador_corrections", []),
            "pipeline": "brigada",
            "run_summary": brig.get("run_summary"),
            "content_preview": (rep.get("content") or "")[:2000],
        }
    except (NotADirectoryError, ValueError):
        raise  # errores de uso reales (proyecto inexistente / sin escaneos) -> propagar
    except Exception:  # noqa: BLE001
        logger.exception("La brigada falló; caigo al pipeline lineal de reporte.")
        return await _generate_client_report_linear(path)


async def _generate_client_report_linear(path: str) -> dict:
    """Genera el reporte CLIENT-FACING: corre TRIAGE de falsos positivos sobre los
    hallazgos que importan (el LLM mira el código real), y con los que quedan reales
    arma la narrativa del LLM (resumen ejecutivo de negocio + riesgos prioritarios en
    criollo). Los falsos positivos van a una sección aparte con su razón. Las tablas
    crudas quedan de anexo técnico. Se guarda como nota nueva (tag 'cliente')."""
    root = Path(path).resolve()
    if not root.is_dir():
        raise NotADirectoryError(str(root))

    sec_scan = security_store.load_scan(root)
    qual_scan = quality_store.load_scan(root)
    if sec_scan is None and qual_scan is None:
        raise ValueError(
            "No hay escaneos guardados para este proyecto -- corré security_scan_project y/o "
            "quality_scan_project antes de generar el reporte."
        )

    sec_findings = sec_scan.findings if sec_scan else []
    qual_findings = qual_scan.findings if qual_scan else []

    # --- E4 (brigada): chequeo determinista de configuración (2026-09-19) -------
    # Lo que los escáneres SAST no miran: DEBUG=True, ALLOWED_HOSTS=['*'],
    # SECRET_KEY hardcodeada, app.run(debug=True), archivos sensibles sueltos.
    # Sus hallazgos entran al MISMO pipeline (E2 contexto por ruta, tablas). Vienen
    # con triage_status="real" (deterministas, no van a triage con LLM). Best-effort:
    # si falla, el reporte sigue con lo que ya había.
    try:
        config_findings = config_check.scan_config(root)
        if config_findings:
            sec_findings = list(sec_findings) + config_findings
    except Exception:  # noqa: BLE001
        logger.exception("E4 config-check falló; sigo sin él.")

    sec_real, _ = _split_noise(sec_findings)
    qual_real, _ = _split_noise(qual_findings)
    generated_at = datetime.now(timezone.utc).isoformat()

    # --- TRIAGE automático de falsos positivos (la mejora de raíz, 2026-09-03) ---
    # Solo los que importan (critical/high/medium) y no estén ya triageados, acotado.
    # El LLM lee el código real y baja los que no son explotables (ej. subprocess en
    # un comando CLI de dev sin input de usuario). Así NO se cuelan en los riesgos
    # prioritarios que ve el cliente.
    to_triage = [
        f for f in sec_real if f.triage_status is None and f.severity in _TRIAGE_SEVERITIES
    ][:_MAX_AUTO_TRIAGE]
    if to_triage:
        try:
            triaged = await triage.triage_findings(root, to_triage)
            by_id = {f.id: f for f in triaged}
            sec_real = [by_id.get(f.id, f) for f in sec_real]
        except Exception:  # noqa: BLE001 -- si el triage falla, seguimos con los crudos
            logger.exception("Auto-triage del reporte falló; sigo sin triagear.")

    sec_fp = [f for f in sec_real if f.triage_status == "false_positive"]
    sec_active_all = [f for f in sec_real if f.triage_status != "false_positive"]
    # E2: separar producción de no-producción. Solo lo de producción entra en los
    # riesgos prioritarios del cliente; lo de tests/examples/docs va a una sección aparte.
    sec_active = [f for f in sec_active_all if _is_production(f)]
    sec_nonprod = [f for f in sec_active_all if not _is_production(f)]

    digest = _build_llm_digest(sec_active, qual_real)
    narrative = await _client_narrative(root.name, digest)

    # E6: el Catador verifica la narrativa contra el código real (QW-3) y corrige
    # afirmaciones que el código no respalde (ej. "MD5" cuando es sha1).
    catador_corrections: list[str] = []
    catador_ran = False
    if narrative:
        evidence = _build_evidence(root, sec_active)
        narrative, catador_corrections = await _catador_review(root.name, narrative, evidence)
        catador_ran = bool(evidence.strip())

    lines = [f"# Reporte de auditoría de código -- {root.name}", ""]
    lines.append(f"- Proyecto: `{root}`")
    lines.append(f"- Generado: {generated_at}")
    if sec_scan:
        lines.append(
            f"- Escaneo de seguridad: {sec_scan.scanned_at} "
            f"(corrieron: {', '.join(sec_scan.tools_run) or 'ninguno'})"
        )
    if qual_scan:
        lines.append(
            f"- Escaneo de calidad: {qual_scan.scanned_at} "
            f"(corrieron: {', '.join(qual_scan.tools_run) or 'ninguno'})"
        )
    if to_triage:
        lines.append(
            f"- Triage de falsos positivos: se revisaron {len(to_triage)} hallazgo(s) "
            f"importante(s) mirando el código real; {len(sec_fp)} descartado(s) como falso positivo."
        )
    lines.append("")
    # La salvedad honesta de tests se mantiene BIEN VISIBLE, arriba de todo.
    lines.append(_test_status_line(root))
    lines.append("")

    if narrative:
        lines.append(narrative)
        lines.append("")
    else:
        # Fallback mecánico si la narrativa no salió.
        sec_counts = _severity_counts(sec_active)
        lines.append("## Resumen ejecutivo")
        lines.append("")
        lines.append(
            f"{len(sec_active)} hallazgo(s) de seguridad real(es) tras triage "
            f"({sec_counts.get('critical', 0)} crítico(s), {sec_counts.get('high', 0)} alto(s)). "
            "_(La narrativa automática no estuvo disponible en esta corrida; ver el anexo técnico.)_"
        )
        lines.append("")

    lines += _catador_section(catador_corrections, catador_ran)

    lines.append("## Anexo técnico -- hallazgos")
    lines.append("")
    lines += _findings_table("Hallazgos de seguridad (reales, tras triage)", sec_active)
    lines += _nonprod_section(sec_nonprod)
    lines += _fp_table(sec_fp)
    lines += _findings_table("Hallazgos de calidad", qual_findings)

    content = "\n".join(lines)
    note = vault.save_note(
        title=f"Reporte de auditoría (cliente) -- {root.name} -- {generated_at[:10]}",
        content=content,
        author="jarvis",
        tags=["reportes", "auditoria", "seguridad", "cliente"],
    )
    last_test_run = test_store.load_last_run(root)
    return {
        "note_id": note.id,
        "note_title": note.title,
        "project": str(root),
        "security_findings": len(sec_findings),
        "security_findings_real_after_triage": len(sec_active),
        "false_positives_discarded": len(sec_fp),
        "nonproduction_findings": len(sec_nonprod),
        "catador_corrections": catador_corrections,
        "triaged": len(to_triage),
        "quality_findings": len(qual_findings),
        "narrative_generated": narrative is not None,
        "tests": last_test_run.to_dict() if last_test_run else None,
        "content_preview": content[:2000],
    }
