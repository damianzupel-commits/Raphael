"""E4 de la brigada de auditoría: chequeo DETERMINISTA de configuración.

Los escáneres SAST (Semgrep/Bandit) miran patrones de código, pero se les
escapan riesgos de CONFIGURACIÓN del framework y del repositorio:
`DEBUG=True`, `ALLOWED_HOSTS=['*']`, `SECRET_KEY` hardcodeada, `app.run(debug=True)`
y archivos sensibles (`.env`, bases de datos, claves privadas) sueltos en el árbol
del proyecto. Esta estación los cubre.

Sin LLM (Tier 0 de la brigada): acá la calidad la da la COBERTURA, no el modelo.
Motivado por la calibración (ver `docs/BRIGADA-AUDITORIA.md` §E4 y
`audit-targets/CALIBRACION.md`): en studybud se escaparon riesgos reales de
configuración que ningún escáner miró.

La salida son `Finding` normales (tool="config-check"), con `triage_status="real"`
porque son deterministas -- no necesitan que el LLM los vuelva a juzgar. El
reporte los pasa por el mismo pipeline (E2 contexto por ruta, tablas, etc.).
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path

from ..findings.models import Finding, make_finding_id

_TOOL = "config-check"
_TRIAGE_REASON = "Chequeo determinista de configuración (E4 de la brigada)."

# Directorios que no se auditan (dependencias, artefactos, control de versiones).
_SKIP_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules",
    "site-packages", "__pycache__", "dist", "build", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", ".idea", ".vscode", ".tox", ".eggs",
}

# No leemos archivos gigantes línea por línea (probablemente datos, no config).
_MAX_PY_BYTES = 2_000_000

# --- Chequeos por línea sobre archivos .py -------------------------------------
# (rule_id, patrón, severity, message, cwe, owasp)
_LINE_CHECKS: list[tuple[str, "re.Pattern[str]", str, str, list[str], list[str]]] = [
    (
        "CFG001-debug-true",
        re.compile(r"^\s*DEBUG\s*=\s*True\b"),
        "high",
        "DEBUG=True: expone trazas y el debugger interactivo; en producción "
        "significa fuga de información y, con Flask/Werkzeug, ejecución de código.",
        ["CWE-489"], ["A05:2021-Security Misconfiguration"],
    ),
    (
        "CFG002-allowed-hosts-wildcard",
        re.compile(r"""ALLOWED_HOSTS\s*=\s*\[\s*['"]\*['"]"""),
        "medium",
        "ALLOWED_HOSTS=['*']: acepta cualquier cabecera Host, habilitando "
        "Host header injection y cache poisoning.",
        ["CWE-16"], ["A05:2021-Security Misconfiguration"],
    ),
    (
        "CFG003-hardcoded-secret-key",
        re.compile(
            r"""(?:^\s*SECRET_KEY\s*=|\.secret_key\s*=|\.config\[\s*['"]SECRET_KEY['"]\s*\]\s*=)\s*['"][^'"]{4,}['"]"""
        ),
        "high",
        "SECRET_KEY hardcodeada en el código: cualquiera con acceso al repo puede "
        "forjar sesiones o tokens. Tiene que venir de una variable de entorno.",
        ["CWE-798"], ["A05:2021-Security Misconfiguration"],
    ),
    (
        "CFG004-flask-run-debug",
        re.compile(r"\.run\([^)]*debug\s*=\s*True"),
        "high",
        "app.run(debug=True): expone el debugger de Werkzeug, que permite "
        "ejecución de código arbitrario.",
        ["CWE-489"], ["A05:2021-Security Misconfiguration"],
    ),
]

# --- Archivos sensibles sueltos en el árbol ------------------------------------
# (rule_id, patrón fnmatch sobre el nombre, severity, descripción)
_SENSITIVE_FILES: list[tuple[str, str, str, str]] = [
    ("CFG010-env-file", ".env", "high", "archivo .env (variables de entorno; suele tener secretos)"),
    ("CFG010-env-file", ".env.*", "high", "archivo .env (variables de entorno; suele tener secretos)"),
    ("CFG011-database", "*.sqlite3", "medium", "base de datos embebida en el árbol del proyecto"),
    ("CFG011-database", "*.sqlite", "medium", "base de datos embebida en el árbol del proyecto"),
    ("CFG011-database", "*.db", "medium", "base de datos embebida en el árbol del proyecto"),
    ("CFG012-private-key", "*.pem", "high", "clave privada o certificado"),
    ("CFG012-private-key", "*.key", "high", "clave privada o certificado"),
    ("CFG012-private-key", "*.p12", "high", "clave privada o certificado"),
    ("CFG012-private-key", "*.pfx", "high", "clave privada o certificado"),
    ("CFG012-private-key", "id_rsa", "high", "clave SSH privada"),
    ("CFG013-credentials", "credentials*.json", "high", "archivo de credenciales"),
]


# `.env.example` / `.env.sample` / etc. son TEMPLATES (se commitean a propósito,
# no tienen secretos) -- no son un hallazgo.
_ENV_TEMPLATE_SUFFIXES = (".example", ".sample", ".template", ".dist", ".tpl")


def _looks_like_sqlite(path: Path) -> bool:
    """True si el archivo empieza con la firma de una base SQLite real. Evita el
    falso positivo de un `*.db` que no es una base (ej. `Dockerfile.db`)."""
    try:
        with path.open("rb") as fh:
            return fh.read(16).startswith(b"SQLite format 3")
    except OSError:
        return False


def _iter_files(root: Path):
    """Recorre el árbol saltando dependencias/artefactos. Devuelve rutas absolutas."""
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        parts = set(p.lower() for p in path.relative_to(root).parts)
        if parts & _SKIP_DIRS:
            continue
        yield path


def _load_gitignore(root: Path) -> list[str]:
    gi = root / ".gitignore"
    if not gi.is_file():
        return []
    try:
        lines = gi.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    out = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line.rstrip("/"))
    return out


def _is_gitignored(rel_posix: str, name: str, patterns: list[str]) -> bool:
    """Heurística simple: ¿el archivo matchea alguna línea del .gitignore?
    Cubre los casos comunes (`*.db`, `.env`, `db.sqlite3`, rutas). No implementa
    la spec completa de gitignore -- alcanza para no gritar por lo que ya está
    correctamente ignorado."""
    for pat in patterns:
        p = pat.lstrip("/")
        if fnmatch.fnmatch(name, p) or fnmatch.fnmatch(rel_posix, p) or fnmatch.fnmatch(rel_posix, f"*/{p}"):
            return True
    return False


def scan_config(root: str | Path) -> list[Finding]:
    """Corre el chequeo de configuración sobre `root` y devuelve los hallazgos.

    Determinista, sin LLM. Cada hallazgo trae `triage_status="real"` para que el
    reporte no lo mande a triage (no hace falta: es un patrón de config sin
    ambigüedad). El contexto por ruta (E2) lo aplica el reporte, no esta estación."""
    root = Path(root).resolve()
    findings: list[Finding] = []
    if not root.is_dir():
        return findings

    gitignore = _load_gitignore(root)

    for path in _iter_files(root):
        rel = path.relative_to(root).as_posix()
        name = path.name

        # 1) Chequeos por línea sobre .py
        if path.suffix == ".py":
            try:
                if path.stat().st_size > _MAX_PY_BYTES:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                for rule_id, pattern, severity, message, cwe, owasp in _LINE_CHECKS:
                    if pattern.search(line):
                        findings.append(
                            Finding(
                                id=make_finding_id(_TOOL, rel, lineno, rule_id),
                                tool=_TOOL,
                                file=rel,
                                line=lineno,
                                end_line=None,
                                severity=severity,
                                rule_id=rule_id,
                                message=message,
                                cwe=list(cwe),
                                owasp=list(owasp),
                                confidence="high",
                                triage_status="real",
                                triage_reasoning=_TRIAGE_REASON,
                            )
                        )

        # 2) Archivos sensibles sueltos (una vez por archivo, sin duplicar rule_id)
        seen_rules: set[str] = set()
        for rule_id, glob, severity, desc in _SENSITIVE_FILES:
            if rule_id in seen_rules:
                continue
            if fnmatch.fnmatch(name, glob):
                if _is_gitignored(rel, name, gitignore):
                    continue
                # Guardas de precisión (falsos positivos vistos en código real):
                if rule_id == "CFG010-env-file" and name.lower().endswith(_ENV_TEMPLATE_SUFFIXES):
                    continue  # .env.example y compañía son templates, no secretos
                if rule_id == "CFG011-database" and not _looks_like_sqlite(path):
                    continue  # un *.db que no es una base real (ej. Dockerfile.db)
                seen_rules.add(rule_id)
                findings.append(
                    Finding(
                        id=make_finding_id(_TOOL, rel, 1, rule_id),
                        tool=_TOOL,
                        file=rel,
                        line=1,
                        end_line=None,
                        severity=severity,
                        rule_id=rule_id,
                        message=(
                            f"Archivo sensible en el árbol del proyecto: {desc}. "
                            "Verificá que esté en .gitignore y que no se haya commiteado."
                        ),
                        cwe=["CWE-538"],
                        owasp=["A05:2021-Security Misconfiguration"],
                        confidence="medium",
                        triage_status="real",
                        triage_reasoning=_TRIAGE_REASON,
                    )
                )

    return findings
