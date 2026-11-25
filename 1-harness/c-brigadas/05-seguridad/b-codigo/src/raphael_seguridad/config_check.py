"""Revisión estática de configuración (E4): cosas que se ven en el texto, sin ejecutar nada."""

from __future__ import annotations

import re
from pathlib import Path

from .models import Finding, finding
from .secrets_scan import iter_files, read_text

# (rule_id, severidad, qué archivos (sufijos o nombres), regex, mensaje, cómo corregirlo)
_PY = (".py",)
RULES: tuple[tuple[str, str, tuple[str, ...], re.Pattern, str, str], ...] = (
    ("debug-on", "medium", (".py", ".env", ".yaml", ".yml"), re.compile(r"(?i)^\s*(?:DEBUG|FLASK_DEBUG)\s*[:=]\s*(?:true|1)\b"),
     "modo debug prendido", "Apagalo en producción (DEBUG=False)."),
    ("tls-verify-off", "high", _PY, re.compile(r"verify\s*=\s*False"), "verificación de certificados apagada",
     "Dejá verify=True; si el certificado es propio, apuntá verify a su CA."),
    ("shell-true", "high", _PY, re.compile(r"subprocess\.\w+\([^)]*shell\s*=\s*True"), "subprocess con shell=True",
     "Pasá la lista de argumentos y sacá shell=True."),
    ("eval-exec", "high", _PY, re.compile(r"(?<![\w.])(?:eval|exec)\("), "eval/exec sobre datos que pueden ser de terceros",
     "Reemplazalo por un parser (ast.literal_eval, json) o una tabla de funciones permitidas."),
    ("yaml-unsafe", "medium", _PY, re.compile(r"yaml\.load\((?![^)]*Loader)"), "yaml.load sin SafeLoader", "Usá yaml.safe_load."),
    ("weak-hash", "low", _PY, re.compile(r"hashlib\.(?:md5|sha1)\("), "hash débil (md5/sha1)",
     "Para contraseñas usá argon2/bcrypt; para integridad, sha256."),
    ("sql-concat", "high", _PY, re.compile(r"""(?i)\.execute\(\s*f?["'][^"']*(?:select|insert|update|delete)[^"']*["']\s*(?:%|\+|\.format)|\.execute\(\s*f["'][^"']*(?:select|insert|update|delete)[^"']*\{"""),
     "consulta SQL armada con texto (inyección)", "Usá parámetros: execute(sql, (valor,))."),
    ("cors-any", "medium", (".py", ".yaml", ".yml", ".json", ".js", ".ts"),
     re.compile(r"""(?i)(?:allow_origins|cors_origins|Access-Control-Allow-Origin)["']?\s*[:=,]?\s*[\[\(]?\s*["']\*["']"""),
     "CORS abierto a cualquier origen", "Listá los orígenes permitidos."),
    ("hosts-any", "medium", _PY, re.compile(r"ALLOWED_HOSTS\s*=\s*\[\s*['\"]\*['\"]"), "ALLOWED_HOSTS acepta cualquier host",
     "Listá los dominios reales."),
    ("chmod-777", "medium", (".sh", ".bat", ".py", ".yml", ".yaml", "Dockerfile"), re.compile(r"chmod\s+(?:-R\s+)?0?777"),
     "permisos 777", "Dá solo los permisos que hacen falta (600/640/750)."),
    ("bind-all", "low", (".py", ".yaml", ".yml", ".bat", ".sh"), re.compile(r"""(?:host\s*=\s*|--host[ =])["']?0\.0\.0\.0"""),
     "servicio escuchando en todas las interfaces", "Si no hace falta afuera, escuchá solo en 127.0.0.1."),
)
ENV_TEMPLATES = (".plantilla", ".example", ".sample", ".template")


def check_config(root: Path, files: list[Path] | None = None) -> list[Finding]:
    out: list[Finding] = []
    for p in files if files is not None else iter_files(root):
        rel = p.relative_to(root).as_posix()
        name = p.name
        if (name == ".env" or (name.startswith(".env.") and not name.endswith(ENV_TEMPLATES))) \
                and ".data" not in rel:
            out.append(finding("config", rel, 1, "high", "env-committed",
                               "archivo de variables de entorno dentro del proyecto (puede terminar en git)",
                               fix="Agregalo al .gitignore y dejá solo una plantilla (.env.plantilla) sin valores."))
        text = read_text(p)
        if text is None:
            continue
        if name == "Dockerfile" and not re.search(r"(?m)^\s*USER\s+(?!root\b)\S+", text):
            out.append(finding("config", rel, 1, "medium", "docker-root", "el contenedor corre como root",
                               fix="Agregá una línea USER con un usuario sin privilegios."))
        for n, line in enumerate(text.splitlines(), 1):
            for rule_id, sev, exts, rx, msg, fix in RULES:
                if (p.suffix in exts or name in exts) and rx.search(line):
                    out.append(finding("config", rel, n, sev, rule_id, msg.capitalize(), evidence=line.strip()[:120], fix=fix))
    return out
