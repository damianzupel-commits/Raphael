"""Dependencias vulnerables (E3). Lee los manifiestos del proyecto y le pregunta a un adaptador de avisos.

Adaptadores (se elige con `SEGURIDAD_ADVISORIES`):
- `osv`: OSV.dev (gratis, sin clave). SALE AL MUNDO el nombre y la versión de cada paquete: por eso está apagado por
  defecto y lo prende Damián a propósito.
- `mock`: tabla fija para pruebas y demos; sus hallazgos van marcados como simulados.
- `off` (default): no consulta nada y el reporte lo dice. Nunca se inventan vulnerabilidades.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from .models import Finding, finding

SEV_MAP = {"CRITICAL": "critical", "HIGH": "high", "MODERATE": "medium", "MEDIUM": "medium", "LOW": "low"}


@dataclass(frozen=True)
class Dep:
    ecosystem: str   # PyPI | npm
    name: str
    version: str
    file: str
    line: int = 1


@dataclass(frozen=True)
class Advisory:
    id: str
    summary: str
    severity: str = "medium"
    fixed_in: str = ""


class AdvisorySource(Protocol):
    name: str
    simulated: bool

    def lookup(self, deps: list[Dep]) -> dict[Dep, list[Advisory]]: ...


def parse_requirements(rel: str, text: str) -> list[Dep]:
    out = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        m = re.match(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]*\])?\s*==\s*([A-Za-z0-9_.+!-]+)", line)
        if m:
            out.append(Dep("PyPI", m.group(1).lower(), m.group(2), rel, n))
    return out


def parse_pyproject(rel: str, text: str) -> list[Dep]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return []
    specs = list(data.get("project", {}).get("dependencies", []))
    for extra in data.get("project", {}).get("optional-dependencies", {}).values():
        specs += extra
    return parse_requirements(rel, "\n".join(specs))


def parse_package_json(rel: str, text: str) -> list[Dep]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    out = []
    for section in ("dependencies", "devDependencies"):
        for name, spec in (data.get(section) or {}).items():
            m = re.match(r"^[\^~=v]*(\d+\.\d+\.\d+[\w.+-]*)$", str(spec).strip())
            if m:
                out.append(Dep("npm", name, m.group(1), rel))
    return out


PARSERS = {"requirements.txt": parse_requirements, "pyproject.toml": parse_pyproject, "package.json": parse_package_json}


def collect_deps(root: Path, files: list[Path]) -> list[Dep]:
    out: list[Dep] = []
    for p in files:
        parser = PARSERS.get(p.name) or (parse_requirements if re.match(r"requirements.*\.txt$", p.name) else None)
        if parser:
            try:
                out += parser(p.relative_to(root).as_posix(), p.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
    return out


class OffSource:
    name, simulated = "off", False

    def lookup(self, deps):  # pragma: no cover - nunca se llama
        return {}


class MockSource:
    """Tabla fija: `table` = {(ecosistema, nombre, versión): [Advisory, …]}. Marcada como simulada."""

    name, simulated = "mock", True

    def __init__(self, table: dict | None = None) -> None:
        self.table = table if table is not None else {("PyPI", "django", "1.11.0"): [
            Advisory("MOCK-0001", "vulnerabilidad de ejemplo (simulada)", "high", "1.11.29")]}

    def lookup(self, deps):
        return {d: self.table[(d.ecosystem, d.name, d.version)] for d in deps if (d.ecosystem, d.name, d.version) in self.table}


class OsvSource:
    name, simulated = "osv", False
    URL = "https://api.osv.dev/v1/querybatch"

    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client or httpx.Client(timeout=30)

    def lookup(self, deps):
        out: dict[Dep, list[Advisory]] = {}
        for i in range(0, len(deps), 500):
            chunk = deps[i:i + 500]
            body = {"queries": [{"package": {"name": d.name, "ecosystem": d.ecosystem}, "version": d.version} for d in chunk]}
            r = self.client.post(self.URL, json=body)
            r.raise_for_status()
            for d, res in zip(chunk, r.json().get("results", []), strict=False):
                advs = [Advisory(v["id"], v.get("summary") or v["id"],
                                 SEV_MAP.get(str((v.get("database_specific") or {}).get("severity", "")).upper(), "medium"))
                        for v in res.get("vulns", [])]
                if advs:
                    out[d] = advs
        return out


def source_from_env(env: dict[str, str]) -> AdvisorySource:
    kind = (env.get("SEGURIDAD_ADVISORIES") or "off").strip().lower()
    return {"osv": OsvSource, "mock": MockSource}.get(kind, OffSource)()


def scan_deps(root: Path, files: list[Path], source: AdvisorySource) -> tuple[list[Finding], str | None]:
    """(hallazgos, motivo por el que no se consultó). Un fallo de red no rompe la auditoría: se avisa."""
    if isinstance(source, OffSource):
        return [], "consulta de avisos apagada (SEGURIDAD_ADVISORIES=off): las dependencias no se revisaron"
    deps = collect_deps(root, files)
    if not deps:
        return [], None
    try:
        hits = source.lookup(deps)
    except (httpx.HTTPError, OSError) as exc:
        return [], f"no se pudo consultar {source.name}: {type(exc).__name__}"
    out = []
    for d, advs in hits.items():
        for a in advs:
            fix = f"Actualizá {d.name} a {a.fixed_in} o más nuevo." if a.fixed_in else f"Actualizá {d.name}; mirá el aviso {a.id}."
            out.append(finding("dependencias", d.file, d.line, a.severity, f"{d.ecosystem}:{d.name}:{a.id}",
                               f"{d.name} {d.version}: {a.summary}", evidence=a.id, fix=fix, simulated=source.simulated))
    return out, None
