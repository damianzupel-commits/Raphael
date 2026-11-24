"""Clasificación técnico vs personal de un episodio (Decisión 8 del spec).

Criterio: heurística por origen/contenido + (opcional) el modelo al destilar,
y **ante la duda, SIEMPRE `personal`** (fail-safe hacia lo privado). Que un
episodio técnico caiga como personal solo lo hace más privado; al revés sería
el error grave (mandar algo personal a la nube). Ver §7.

Fase 1: heurística por palabras clave. Si el turno es claramente de trabajo
técnico (código, seguridad, pentest, trading, la web, el propio repo) → tecnico.
Cualquier otra cosa, o si hay señales personales → personal.
"""

from __future__ import annotations

from .schema import Sensitivity

# Señales de trabajo TÉCNICO (si aparecen y NO hay señal personal fuerte → tecnico).
_TECNICO_HINTS = (
    "código", "codigo", "function", "función", "funcion", "clase", "bug", "commit",
    "vulnerab", "cve", "semgrep", "bandit", "pentest", "nmap", "sqlmap", "exploit",
    "malware", "yara", "escaneo", "auditor", "backend", "endpoint", "api", "tool",
    "repo", "git", "test", "pytest", "trading", "backtest", "ifvg", "smc", "scraper",
    "scrape", "web_get", "spec", "config", "raphael", "jarvis", "harness", "brigada",
    "docker", "servidor", "deploy", "refactor", "stacktrace", "traceback", "logs",
)

# Señales PERSONALES fuertes: si aparecen, gana personal aunque haya jerga técnica.
_PERSONAL_HINTS = (
    "me siento", "mi hija", "mi familia", "mi vieja", "mi viejo", "mi mamá", "mi papá",
    "psicológ", "psicolog", "terapia", "emocion", "angustia", "ansiedad", "miedo",
    "sueño", "relación", "relacion", "pareja", "personal", "íntimo", "intimo",
    "infancia", "recuerdo de", "me pasa que", "no sé qué hacer con mi",
)


def classify(text: str, *, dominio: str = "") -> Sensitivity:
    """Devuelve 'tecnico' o 'personal'. Fail-safe: si no hay señal técnica clara,
    o hay cualquier señal personal, → personal."""
    low = (text or "").lower()

    # Señal personal fuerte gana siempre.
    if any(h in low for h in _PERSONAL_HINTS):
        return "personal"

    # El dominio ya puede marcarlo como técnico (viene del skill activo).
    tecnico_dominios = {"auditoria", "security_audit", "pentesting", "malware_protection",
                        "trading", "datos_externos", "code_delegation", "web"}
    if dominio in tecnico_dominios:
        return "tecnico"

    # Suficiente jerga técnica y ninguna señal personal → tecnico.
    hits = sum(1 for h in _TECNICO_HINTS if h in low)
    if hits >= 2:
        return "tecnico"

    # Ante la duda: personal (fail-safe hacia lo privado).
    return "personal"
