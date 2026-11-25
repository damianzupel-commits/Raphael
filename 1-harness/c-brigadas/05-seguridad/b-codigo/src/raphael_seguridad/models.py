"""Hallazgos normalizados: el mismo formato para secretos, dependencias, configuración, pentest y vigilancia."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field

SEVERITIES = ("critical", "high", "medium", "low", "info")
RANK = {s: i for i, s in enumerate(SEVERITIES)}


@dataclass
class Finding:
    id: str
    tool: str                 # secretos | dependencias | config | nmap | zap | sqlmap | vigilancia (o "mock-..." si es simulado)
    file: str                 # ruta relativa con '/', o el objetivo (host:puerto, url)
    line: int
    severity: str
    rule_id: str
    message: str
    evidence: str = ""        # siempre tachada: nunca un secreto completo
    fix: str = ""             # cómo corregirlo
    status: str = "open"      # open | false_positive | test
    reasoning: str = ""       # por qué el triage lo bajó
    simulated: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> Finding:
        return Finding(**{k: v for k, v in d.items() if k in Finding.__dataclass_fields__})


def make_id(tool: str, file: str, line: int, rule_id: str) -> str:
    """Estable: el mismo hallazgo da el mismo id en corridas sucesivas (sirve para comparar y marcar corregidos)."""
    return hashlib.sha256(f"{tool}:{file}:{line}:{rule_id}".encode()).hexdigest()[:16]


def finding(tool: str, file: str, line: int, severity: str, rule_id: str, message: str, *, evidence: str = "",
            fix: str = "", simulated: bool = False) -> Finding:
    if severity not in RANK:
        raise ValueError(f"severidad inválida: {severity!r}")
    return Finding(make_id(tool, file, line, rule_id), tool, file, line, severity, rule_id, message, evidence, fix,
                   simulated=simulated)


def sort_findings(items: list[Finding]) -> list[Finding]:
    return sorted(items, key=lambda f: (RANK[f.severity], f.file, f.line, f.rule_id))


def redact(value: str, keep: int = 4) -> str:
    """Tacha un secreto: deja solo los últimos `keep` caracteres (y nada si es corto)."""
    value = value.strip()
    if len(value) <= keep * 2:
        return "*" * len(value)
    return "*" * 6 + value[-keep:]


@dataclass
class ScanResult:
    root: str
    at: str
    steps: list[dict] = field(default_factory=list)       # E1..E7: nombre, estado y detalle
    skipped: dict[str, str] = field(default_factory=dict)  # herramienta -> motivo (se avisa, no se inventa)
    findings: list[Finding] = field(default_factory=list)

    def counts(self, include_closed: bool = False) -> dict[str, int]:
        out = dict.fromkeys(SEVERITIES, 0)
        for f in self.findings:
            if include_closed or f.status == "open":
                out[f.severity] += 1
        return out

    def to_dict(self) -> dict:
        return {"root": self.root, "at": self.at, "steps": self.steps, "skipped": self.skipped,
                "findings": [f.to_dict() for f in self.findings]}

    @staticmethod
    def from_dict(d: dict) -> ScanResult:
        return ScanResult(d["root"], d["at"], d.get("steps", []), d.get("skipped", {}),
                          [Finding.from_dict(f) for f in d.get("findings", [])])
