"""Detector de secretos expuestos (E2). Reglas fijas: no adivina con un modelo. La evidencia sale siempre tachada."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from .models import Finding, finding, redact

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".data", "dist", "build", ".mypy_cache",
             ".ruff_cache", ".pytest_cache"}
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".gz", ".sqlite", ".db", ".exe", ".dll", ".jar",
            ".apk", ".woff", ".woff2", ".ttf", ".mp4", ".mp3", ".lock", ".pyc"}
MAX_BYTES = 1_000_000

# (rule_id, severidad, regex con el secreto en el grupo 1 o en todo el match, mensaje)
RULES: tuple[tuple[str, str, re.Pattern, str], ...] = (
    ("aws-access-key", "critical", re.compile(r"\b(AKIA[0-9A-Z]{16})\b"), "clave de acceso de AWS"),
    ("private-key", "critical", re.compile(r"(-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----)"),
     "clave privada en el repositorio"),
    ("github-token", "critical", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{30,})\b"), "token de GitHub"),
    ("openai-key", "critical", re.compile(r"\b(sk-(?:or-v1-|proj-)?[A-Za-z0-9_-]{32,})\b"), "clave de API de un proveedor de IA"),
    ("slack-token", "high", re.compile(r"\b(xox[abprs]-[A-Za-z0-9-]{10,})\b"), "token de Slack"),
    ("google-api-key", "high", re.compile(r"\b(AIza[0-9A-Za-z_-]{35})\b"), "clave de API de Google"),
    ("meta-token", "high", re.compile(r"\b(EAA[A-Za-z0-9]{40,})\b"), "token de acceso de Meta"),
    ("nvidia-key", "high", re.compile(r"\b(nvapi-[A-Za-z0-9_-]{30,})\b"), "clave de API de NVIDIA"),
    ("jwt", "medium", re.compile(r"\b(eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})\b"),
     "JWT embebido"),
    ("password-assign", "high",
     re.compile(r"""(?i)\b(?:password|passwd|pwd|secret|api[_-]?key|token)\b["']?\s*[:=]\s*["']([^"'\s]{6,})["']"""),
     "credencial escrita en el código"),
)
FIXES = {
    "private-key": "Sacala del repo, rotá la clave (la anterior ya se considera comprometida) y guardala fuera de git.",
}
DEFAULT_FIX = "Sacá el valor del código, rotalo (el que está en el historial ya se considera filtrado) y leelo de una variable de entorno."


def iter_files(root: Path) -> Iterator[Path]:
    for p in sorted(root.rglob("*")):
        if not p.is_file() or any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            continue
        if p.suffix.lower() in SKIP_EXT or p.stat().st_size > MAX_BYTES:
            continue
        yield p


def read_text(p: Path) -> str | None:
    try:
        data = p.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:2048]:
        return None
    return data.decode("utf-8", errors="replace")


def scan_text(rel: str, text: str) -> list[Finding]:
    out: list[Finding] = []
    for n, line in enumerate(text.splitlines(), 1):
        if len(line) > 2000:
            continue
        for rule_id, sev, rx, msg in RULES:
            m = rx.search(line)
            if not m:
                continue
            secret = m.group(1)
            out.append(finding("secretos", rel, n, sev, rule_id, f"Posible {msg}", evidence=redact(secret),
                               fix=FIXES.get(rule_id, DEFAULT_FIX)))
            break   # una regla por línea alcanza
    return out


def scan_secrets(root: Path, files: list[Path] | None = None) -> list[Finding]:
    out: list[Finding] = []
    for p in files if files is not None else iter_files(root):
        text = read_text(p)
        if text is not None:
            out += scan_text(p.relative_to(root).as_posix(), text)
    return out
