"""Configuración amigable para el usuario (2026-10-11, pedido de Damian).

Un ESQUEMA único con TODAS las opciones que un usuario toca, agrupadas por sección,
con etiqueta clara + descripción + tipo de control. El panel web (/configuracion) se
arma solo desde acá; guardar escribe al `backend/.env` (la mayoría pide reiniciar el
backend para tomar efecto).

Separa lo amigable de lo técnico: acá va lo que el usuario cambia. Los gates duros
(authorized_targets.yaml, líneas rojas, scope de pentest) NO se exponen para editar —
`apply()` solo escribe keys que están en el esquema, así el panel no puede tocar nada
fuera de esta lista.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_ENV = Path(__file__).resolve().parent.parent / ".env"

# tipo: toggle | text | number | select (con "options").
SCHEMA: list[dict] = [
    {"section": "🎭 Personalización", "fields": [
        {"key": "ASSISTANT_NAME", "label": "Nombre del asistente", "desc": "Cómo se llama tu IA.", "type": "text", "default": "Raphael"},
        {"key": "USER_NAME", "label": "Tu nombre", "desc": "Para que te hable personalizado.", "type": "text", "default": ""},
        {"key": "ASSISTANT_TONE", "label": "Tono", "desc": "Cómo te habla.", "type": "select", "options": ["relajado", "formal", "directo", "técnico"], "default": "relajado"},
        {"key": "UI_THEME", "label": "Tema de color", "desc": "Paleta del panel y el orbe.", "type": "select", "options": ["cian", "violeta", "verde", "ámbar"], "default": "cian"},
    ]},
    {"section": "🗣 Voz", "fields": [
        {"key": "VOICE_LISTENER_ENABLED", "label": "Escucha continua \"hey Jarvis\"", "desc": "Te escucha sin tocar el teclado.", "type": "toggle", "default": False},
    ]},
    {"section": "⚙️ Modo de trabajo", "fields": [
        {"key": "TEST_MODE", "label": "Modo prueba (free)", "desc": "Todo gratis, sin gastar crédito. Usa modelos free.", "type": "toggle", "default": False},
        {"key": "DIFFICULTY_ROUTER_ENABLED", "label": "Router de dificultad", "desc": "Escala a Claude solo en tareas pesadas.", "type": "toggle", "default": False},
        {"key": "OPS_SUPERVISOR_ENABLED", "label": "Supervisor de Operaciones (Sonnet)", "desc": "Revisa cada acción en la PC/celular y frena llamados claramente malos. Agrega un paso antes de cada tool.", "type": "toggle", "default": False},
        {"key": "OPS_WATCHDOG_ENABLED", "label": "Watchdog de Operaciones", "desc": "Destraba una acción colgada: si una tool de PC/celular tarda demasiado, la corta y sigue.", "type": "toggle", "default": False},
        {"key": "OPS_WATCHDOG_TIMEOUT_SECONDS", "label": "Cortar acción colgada a los (seg)", "desc": "Cuánto espera antes de destrabar una tool colgada.", "type": "number", "default": 300},
    ]},
    {"section": "🔑 Modelos y APIs por tier", "fields": [
        {"key": "LMSTUDIO_MODEL", "label": "Modelo principal", "desc": "El que usa el chat normal. Nombre exacto del modelo.", "type": "text", "default": "local-model"},
        {"key": "LMSTUDIO_BASE_URL", "label": "Endpoint principal (nube)", "desc": "URL base del proveedor del modelo principal.", "type": "text", "default": "http://localhost:1234/v1"},
        {"key": "LLM_API_KEY", "label": "API key principal (nube)", "desc": "Key del proveedor principal. También es el fallback de los tiers de nube.", "type": "secret", "default": ""},

        {"key": "TIER1_MODEL", "label": "Tier 1 · Local — modelo", "desc": "Tareas de fondo (consolidación, memoria). Vacío = jarvis-text-v2.", "type": "text", "default": ""},
        {"key": "TIER1_BASE_URL", "label": "Tier 1 · Local — endpoint", "desc": "Vacío = Ollama local (127.0.0.1:11434).", "type": "text", "default": ""},
        {"key": "TIER1_API_KEY", "label": "Tier 1 · Local — API key", "desc": "Normalmente no hace falta (local).", "type": "secret", "default": ""},

        {"key": "TIER2_FREE_MODELS", "label": "Tier 2 · Free — modelos", "desc": "Lista separada por comas. Rotan si uno se cae.", "type": "text", "default": ""},
        {"key": "TIER2_BASE_URL", "label": "Tier 2 · Free — endpoint", "desc": "Vacío = OpenRouter. O la URL de OmniRoute local.", "type": "text", "default": ""},
        {"key": "TIER2_API_KEY", "label": "Tier 2 · Free — API key", "desc": "Key del gateway free.", "type": "secret", "default": ""},

        {"key": "TIER3_MODEL", "label": "Tier 3 · Pesado — modelo", "desc": "Tareas que piden cabeza. Vacío = Sonnet 5.5.", "type": "text", "default": ""},
        {"key": "TIER3_BASE_URL", "label": "Tier 3 · Pesado — endpoint", "desc": "Vacío = usa el endpoint principal (nube).", "type": "text", "default": ""},
        {"key": "TIER3_API_KEY", "label": "Tier 3 · Pesado — API key", "desc": "Vacío = usa la API key principal.", "type": "secret", "default": ""},

        {"key": "TIER4_MODEL", "label": "Tier 4 · Especial — modelo", "desc": "Lo más duro. Vacío = Opus 5.5.", "type": "text", "default": ""},
        {"key": "TIER4_BASE_URL", "label": "Tier 4 · Especial — endpoint", "desc": "Vacío = usa el endpoint principal (nube).", "type": "text", "default": ""},
        {"key": "TIER4_API_KEY", "label": "Tier 4 · Especial — API key", "desc": "Vacío = usa la API key principal.", "type": "secret", "default": ""},
    ]},
    {"section": "🗺️ Fuentes del mapa (keys)", "fields": [
        {"key": "FIRMS_MAP_KEY", "label": "NASA FIRMS (incendios)", "desc": "Key gratis en firms.modaps.eosdis.nasa.gov/api. Habilita la capa 🔥 Incendios.", "type": "secret", "default": ""},
        {"key": "WINDY_WEBCAMS_KEY", "label": "Windy Webcams (cámaras públicas)", "desc": "Key gratis en api.windy.com. Habilita la capa 📷 Cámaras (solo cámaras publicadas).", "type": "secret", "default": ""},
        {"key": "OPENWEATHER_KEY", "label": "OpenWeather (clima)", "desc": "Key gratis en openweathermap.org. (Capa de clima — próximamente.)", "type": "secret", "default": ""},
        {"key": "OPENCELLID_KEY", "label": "OpenCelliD (torres de celular)", "desc": "Key gratis en opencellid.org. Habilita la capa de antenas (por área).", "type": "secret", "default": ""},
        {"key": "OPENCELLID_BBOX", "label": "OpenCelliD — área (bbox)", "desc": "latSur,lonOeste,latNorte,lonEste. OpenCelliD es por área, no global.", "type": "text", "default": "-35.0,-59.0,-34.3,-58.2"},
        {"key": "AISSTREAM_KEY", "label": "AISStream (barcos / AIS)", "desc": "Key gratis en aisstream.io. Habilita la capa 🚢 Barcos (stream en vivo). Requiere reiniciar el backend.", "type": "secret", "default": ""},
        {"key": "SHODAN_KEY", "label": "Shodan (hosts expuestos)", "desc": "Key en shodan.io. Habilita la capa 🛰 Shodan y la tool shodan_host_search. OSINT de infraestructura pública.", "type": "secret", "default": ""},
        {"key": "SHODAN_QUERY", "label": "Shodan — query de la capa", "desc": "Qué busca la capa del mapa (ej. product:nginx, port:554, country:AR).", "type": "text", "default": "product:nginx"},
    ]},
    {"section": "📥 Conocimiento", "fields": [
        {"key": "PLAYLIST_WATCH_URL", "label": "Playlist de YouTube a vigilar", "desc": "Se ingiere sola. Pegá la URL.", "type": "text", "default": ""},
        {"key": "PLAYLIST_WATCH_INTERVAL_MINUTES", "label": "Revisar cada (minutos)", "desc": "Cada cuánto chequea la playlist.", "type": "number", "default": 15},
        {"key": "PLAYLIST_WATCH_MAX_PER_RUN", "label": "Videos por tanda", "desc": "Máximo que ingiere por chequeo.", "type": "number", "default": 8},
        {"key": "CONSOLIDATION_ENABLED", "label": "Consolidación (\"sueño\")", "desc": "Resume y reorganiza el vault cada tanto (modelo local).", "type": "toggle", "default": False},
        {"key": "CONSOLIDATION_INTERVAL_HOURS", "label": "Consolidar cada (horas)", "desc": "", "type": "number", "default": 24},
        {"key": "CURIOSITY_ENABLED", "label": "Curiosidad", "desc": "Detecta huecos en tus notas.", "type": "toggle", "default": False},
        {"key": "PROACTIVE_LEARNING_ENABLED", "label": "Aprendizaje proactivo", "desc": "Por iniciativa propia, amplía investigaciones abiertas y llena huecos del vault. Gasta modelo.", "type": "toggle", "default": False},
    ]},
    {"section": "🔐 Permisos y control", "fields": [
        {"key": "DESKTOP_CONTROL_ENABLED", "label": "Controlar esta PC", "desc": "Mouse, teclado y ventanas.", "type": "toggle", "default": True},
        {"key": "PC_SHELL_ENABLED", "label": "Shell real en la PC", "desc": "Correr comandos reales. Potente.", "type": "toggle", "default": True},
        {"key": "PHONE_SHELL_ENABLED", "label": "Comandos en el celular (Termux)", "desc": "Ejecución real en el teléfono.", "type": "toggle", "default": True},
        {"key": "PHONE_CAMERA_ENABLED", "label": "Cámara del celular", "desc": "Sacar fotos o video corto.", "type": "toggle", "default": True},
        {"key": "FS_ALLOW_DELETE", "label": "Permitir borrar archivos", "desc": "Si está apagado, lee/crea pero no borra.", "type": "toggle", "default": False},
        {"key": "SELF_REDESIGN_ENABLED", "label": "Autorreparación", "desc": "Propone mejoras a su propio código (aplicar siempre pide tu OK).", "type": "toggle", "default": True},
        {"key": "SCREEN_RECORDING_ENABLED", "label": "Grabación de pantalla", "desc": "Documenta el trabajo en video.", "type": "toggle", "default": True},
        {"key": "BROWSER_HEADLESS", "label": "Navegador invisible", "desc": "El navegador que usa corre sin ventana.", "type": "toggle", "default": False},
    ]},
]

_KEYS = {f["key"] for sec in SCHEMA for f in sec["fields"]}
_SECRET_KEYS = {f["key"] for sec in SCHEMA for f in sec["fields"] if f["type"] == "secret"}
_BOOL_TRUE = {"1", "true", "yes", "on"}
# Valores que, para una API key ya seteada, el .env trae por default y NO son una key real.
# Si el valor guardado es uno de estos (o vacío), tratamos la key como "sin configurar".
_PLACEHOLDER_SECRETS = {"", "not-needed", "lm-studio", "ollama"}


def _read_env() -> dict:
    vals: dict[str, str] = {}
    if _ENV.is_file():
        for line in _ENV.read_text(encoding="utf-8", errors="surrogateescape").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            vals[k.strip()] = v.strip()
    return vals


def current() -> dict:
    """Valor actual de cada opción (del .env, o el env del proceso, o el default).

    Las API keys (type=secret) NUNCA se devuelven: el valor sale como "" y si está
    configurada se indica aparte (ver `secrets_set`). Así el panel nunca recibe la key
    en claro, aunque la pida con credencial."""
    env = _read_env()
    out: dict = {}
    for sec in SCHEMA:
        for f in sec["fields"]:
            k = f["key"]
            raw = env.get(k, os.getenv(k))
            if f["type"] == "secret":
                out[k] = ""  # nunca exponer la key
            elif f["type"] == "toggle":
                out[k] = (raw.lower() in _BOOL_TRUE) if isinstance(raw, str) else bool(f["default"])
            elif f["type"] == "number":
                try:
                    n = float(raw) if raw not in (None, "") else float(f["default"])
                    out[k] = int(n) if n == int(n) else n
                except (TypeError, ValueError):
                    out[k] = f["default"]
            else:
                out[k] = raw if raw is not None else f["default"]
    return out


def secrets_set() -> dict:
    """{key: True/False} para cada campo secreto, según si hay una key REAL guardada
    (no vacía ni un placeholder tipo 'not-needed'). El panel lo usa para mostrar
    'configurada' vs 'sin configurar' sin ver el valor."""
    env = _read_env()
    out: dict = {}
    for k in _SECRET_KEYS:
        raw = env.get(k, os.getenv(k))
        out[k] = bool(raw) and str(raw).strip() not in _PLACEHOLDER_SECRETS
    return out


def schema_with_values() -> dict:
    return {"schema": SCHEMA, "values": current(), "secrets": secrets_set()}


def apply(changes: dict) -> list[str]:
    """Escribe los cambios al .env (SOLO keys del esquema; lo demás se ignora, por
    seguridad). Preserva el resto del archivo. Devuelve las keys escritas."""
    text = _ENV.read_text(encoding="utf-8", errors="surrogateescape") if _ENV.is_file() else ""
    lines = text.splitlines()
    written: list[str] = []
    for k, v in changes.items():
        if k not in _KEYS:
            continue
        # Una key secreta vacía = "no la toco" (el panel manda "" cuando el usuario no la
        # cambió). Así no se pisa una key existente con un valor vacío por accidente.
        if k in _SECRET_KEYS and (v is None or str(v).strip() == ""):
            continue
        sval = ("true" if v else "false") if isinstance(v, bool) else str(v)
        pat = re.compile(rf"^#?\s*{re.escape(k)}\s*=")
        done = False
        for i, ln in enumerate(lines):
            if pat.match(ln):
                lines[i] = f"{k}={sval}"
                done = True
                break
        if not done:
            lines.append(f"{k}={sval}")
        written.append(k)
    _ENV.write_text("\n".join(lines) + "\n", encoding="utf-8", errors="surrogateescape")
    return written
