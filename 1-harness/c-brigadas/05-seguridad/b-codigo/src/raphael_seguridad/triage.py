"""Triage por reglas (E5): baja el ruido sin borrar nada. Cada cambio de estado deja su razón.

Sin modelo: esta brigada no manda código a ningún modelo. (Decisión de Damián: lo sensible corre en local o en reglas.)"""

from __future__ import annotations

import re

from .models import Finding

TEST_PATH = re.compile(r"(?:^|/)(?:tests?|pruebas|fixtures?|__tests__|examples?|ejemplos?)(?:/|$)|(?:^|/)test_[^/]*\.py$|\.test\.[jt]sx?$")
PLACEHOLDER = re.compile(r"(?i)(changeme|cambiame|example|ejemplo|dummy|placeholder|your[_-]?|tu[_-]?clave|xxx+|\*{4,}|<[^>]+>|\$\{)")
DOC_PATH = re.compile(r"\.(?:md|rst|txt)$|(?:^|/)docs?/")


def triage(items: list[Finding]) -> list[Finding]:
    for f in items:
        if f.status != "open":
            continue
        if f.tool == "secretos" and f.rule_id in ("password-assign", "jwt") and PLACEHOLDER.search(f.evidence):
            f.status, f.reasoning = "false_positive", "valor de relleno (placeholder), no una credencial real"
        elif f.tool in ("secretos", "config") and TEST_PATH.search(f.file) and f.severity != "critical":
            f.status, f.reasoning = "test", "está en tests o ejemplos: revisar, pero no es producción"
        elif f.tool == "config" and DOC_PATH.search(f.file):
            f.status, f.reasoning = "false_positive", "aparece en documentación"
    return items
