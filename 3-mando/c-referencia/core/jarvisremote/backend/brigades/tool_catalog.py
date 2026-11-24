"""Catálogo LIVIANO de tools + política de privilegios para brigadas creadas por borrador (Etapa 2).

Una brigada creada desde una descripción es DATO (JSON), no código: lo único que puede pedir de las tools es nombres.
Este módulo responde dos preguntas sin importar nada pesado:

  1. ¿Existe esa tool, y en qué módulo de `app.tools` vive? -> `catalog()` lee los archivos de `app/tools/` con `ast`
     (busca `@register_tool(name=...)`); NO importa los módulos (no carga phone_link/scapy/pywinauto) y NO ejecuta
     código. El módulo que hay que importar para registrarla sale de acá: un borrador nunca nombra módulos a mano.
  2. ¿Puede una brigada creada por borrador tenerla? -> `classify(nombre)` devuelve un nivel:
       "ok"           herramienta normal.
       "sensible"     permitida, pero con ALTO PRIVILEGIO: escribe en disco/vault, actúa sobre la red, sale a internet,
                      controla un navegador. Se marca en la revisión que ve Damian antes de activar.
       "denegada"     NO se puede conceder por borrador: ejecuta comandos, modifica código, borra/mueve archivos,
                      toca credenciales, controla PC/celular, decide por Damian (confirmar/rechazar propuestas),
                      delega a la nube con costo. Dárselas a una brigada requiere código y revisión humana, no un chat.
       "desconocida"  no está en el catálogo (typo, o una tool inventada por el modelo): se rechaza.

Esta política es DEFENSA EN PROFUNDIDAD: la aprobación de Damian al activar es la línea roja, pero lo que él ve y aprueba
no debería poder incluir, de entrada, una shell o un autoedit del código. Los gates propios de cada tool (scope de
pentest, dry-run -> confirm, flags) siguen valiendo igual para las tools sensibles.
"""

from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent.parent / "app" / "tools"

# --- denegadas: nombre exacto o prefijo -> motivo ---------------------------------------------------------------
DENEGADAS_EXACTAS: dict[str, str] = {
    "pc_run_command": "ejecuta comandos arbitrarios en la PC",
    "phone_run_command": "ejecuta comandos arbitrarios en el celular",
    "selfrepair_propose_fix": "modifica el código del propio Raphael",
    "code_apply_fix": "modifica código",
    "security_audit_find_fix_verify": "aplica fixes de código",
    "fs_delete_path": "borra archivos (destructivo)",
    "fs_move_path": "mueve/renombra archivos (destructivo)",
    "malware_quarantine_delete": "elimina definitivamente de la cuarentena",
    "malware_quarantine_restore": "restaura archivos maliciosos de la cuarentena",
    "malware_rebuild_integrity_baseline": "reescribe la línea base de integridad",
    "web_credential_save": "guarda credenciales",
    "web_credential_list": "lista credenciales",
    "web_login": "inicia sesión con credenciales",
    "form_get_saved_credential": "lee credenciales guardadas",
    "form_list_saved_credentials": "lista credenciales guardadas",
    "browser_generate_password": "genera contraseñas de cuentas",
    "browser_preview_submit": "envía formularios web",
    "opencode_run_task": "delega código a una CLI externa",
    "planear_con_opus": "delega a un modelo de nube con costo",
    "raphael_modo_prueba": "cambia el modo de operación del sistema",
}
DENEGADAS_PREFIJOS: tuple[tuple[str, str], ...] = (
    ("desktop_", "controla el escritorio (mouse/teclado/ventanas)"),
    ("phone_", "controla el celular"),
    ("recording_", "graba la pantalla"),
    ("cloud_expert_", "manda código/contenido a un modelo de nube"),
    ("investigation_confirm_", "confirmar es decisión de Damian, no de una brigada"),
    ("investigation_reject_", "rechazar es decisión de Damian, no de una brigada"),
)
# Excepción de los prefijos denegados: escanea red desde el celular; sigue siendo sensible y pasa por el gate de scope.
_EXCEPCIONES = {"phone_nmap_scan"}

# --- sensibles: permitidas, con aviso en la revisión ------------------------------------------------------------
SENSIBLES_EXACTAS: dict[str, str] = {
    "fs_write_file": "escribe archivos en disco",
    "fs_create_dir": "crea carpetas en disco",
    "obsidian_save_note": "escribe notas en el vault",
    "obsidian_ingerir_web": "ingiere contenido web al vault",
    "obsidian_reindexar": "reindexa el vault (costoso)",
    "memoria_recordar": "escribe en la memoria",
    "memoria_corregir": "modifica la memoria",
    "memoria_olvidar": "borra de la memoria",
    "memoria_consolidar": "reescribe la memoria",
    "nmap_scan": "escaneo ACTIVO de red (pasa por el gate de authorized_targets.yaml)",
    "phone_nmap_scan": "escaneo ACTIVO de red desde el celular (gate de scope)",
    "sqlmap_scan": "envía payloads de inyección SQL (gate de scope)",
    "zap_scan": "escaneo web ACTIVO (gate de scope)",
    "packet_capture_scan": "captura tráfico de red (gate de scope)",
    "web_get": "sale a internet",
    "web_scrape": "sale a internet",
    "research_topic": "sale a internet y escribe notas",
    "youtube_ingest_playlist": "sale a internet y escribe notas",
    "youtube_ingest_video": "sale a internet y escribe notas",
    "shodan_host_search": "consulta un servicio externo con datos del target",
    "ip_geolocate": "consulta un servicio externo con una IP",
    "crypto_address_trace": "consulta un servicio externo con una dirección",
    "generate_image": "consume GPU",
    "generate_video": "consume GPU",
}
SENSIBLES_PREFIJOS: tuple[tuple[str, str], ...] = (
    ("browser_", "controla un navegador"),
    ("investigation_", "escribe en el store de casos de investigación"),
    ("video_", "crea archivos en la carpeta de video y usa CPU sostenida (ffmpeg / Whisper)"),
)
# investigation_* de solo lectura: no son sensibles.
_SOLO_LECTURA = {"investigation_list_pending_proposals", "video_listar", "video_info", "video_escenas", "video_proyecto_ver"}


@lru_cache(maxsize=1)
def catalog() -> dict[str, str]:
    """{nombre de tool -> módulo de `app.tools` que la registra}. Lectura estática (ast): no importa nada."""
    out: dict[str, str] = {}
    for path in sorted(_TOOLS_DIR.glob("*.py")):
        if path.name.startswith("_"):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and getattr(dec.func, "id", None) == "register_tool":
                    for kw in dec.keywords:
                        if kw.arg == "name" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                            out[kw.value.value] = path.stem
    return out


def classify(name: str) -> dict:
    """{"nivel": ok|sensible|denegada|desconocida, "motivo": str, "modulo": str|None}."""
    module = catalog().get(name)
    if module is None:
        return {"nivel": "desconocida", "motivo": "no existe en el catálogo de tools", "modulo": None}
    if name in DENEGADAS_EXACTAS:
        return {"nivel": "denegada", "motivo": DENEGADAS_EXACTAS[name], "modulo": module}
    if name not in _EXCEPCIONES:
        for prefix, why in DENEGADAS_PREFIJOS:
            if name.startswith(prefix):
                return {"nivel": "denegada", "motivo": why, "modulo": module}
    if name in SENSIBLES_EXACTAS:
        return {"nivel": "sensible", "motivo": SENSIBLES_EXACTAS[name], "modulo": module}
    if name not in _SOLO_LECTURA:
        for prefix, why in SENSIBLES_PREFIJOS:
            if name.startswith(prefix):
                return {"nivel": "sensible", "motivo": why, "modulo": module}
    return {"nivel": "ok", "motivo": "", "modulo": module}


def modules_for(tool_names) -> tuple[str, ...]:
    """Módulos de `app.tools` a importar para registrar esas tools (ordenados, sin repetir). Solo del catálogo."""
    cat = catalog()
    return tuple(sorted({cat[t] for t in tool_names if t in cat}))
