import os
from pathlib import Path

from dotenv import load_dotenv

TRAY_DIR = Path(__file__).resolve().parent
BACKEND_DIR = TRAY_DIR.parent / "backend"
ENV_PATH = BACKEND_DIR / ".env"

load_dotenv(ENV_PATH)

HOST = os.getenv("HOST", "127.0.0.1")
PORT = os.getenv("PORT", "8000")
API_KEY = os.getenv("API_KEY", "")

# Mismo env var que usa el backend para su propio presupuesto de espera al LLM
# (`app/config.py::llm_request_timeout_seconds`, default 1800s) -- un turno de
# chat puede incluir un tool lento (nmap_scan admite hasta 1200s) más una o más
# idas y vueltas al LLM local, así que el timeout HTTP de este cliente tiene
# que ser al menos tan largo como lo que el backend mismo está dispuesto a
# esperar. Antes esto estaba hardcodeado en 600s acá y en voice_listener.py,
# bug real confirmado 2026-08-15: con un modelo local lento (30B parcialmente
# en CPU) el backend seguía trabajando de verdad bien pasados los 600s, pero
# el cliente ya había mostrado un error de timeout y descartado la respuesta.
CHAT_REQUEST_TIMEOUT_SECONDS = float(os.getenv("LLM_REQUEST_TIMEOUT_SECONDS", "1800"))

# Para pegarle al backend desde la tray, "0.0.0.0" (bind-all) no sirve como
# destino: si el backend bindea ahi, igual hay que pegarle por localhost.
_target_host = "127.0.0.1" if HOST in ("0.0.0.0", "") else HOST

BASE_URL = f"http://{_target_host}:{PORT}"
HEALTH_URL = f"{BASE_URL}/api/health"
DOCS_URL = f"{BASE_URL}/docs"
CHAT_URL = f"{BASE_URL}/api/chat"
# Espejado del chat en vivo (2026-10-06): WebSocket al que se suscribe la tray para
# recibir lo que se escribe desde el celular (y viceversa), y el id de este cliente
# (para que el backend no le reenvíe su propio eco). La conversación compartida es
# "default" (la misma que ya usa la tray y a la que se pasa el celular).
WS_CHAT_URL = f"ws://{_target_host}:{PORT}/ws/chat"
CLIENT_ID = "tray-pc"
SHARED_CONVERSATION_ID = "default"
CODEBASE_INDEX_URL = f"{BASE_URL}/api/codebase/index"
CODEBASE_RECENT_URL = f"{BASE_URL}/api/codebase/recent"
CODEBASE_GRAPH_URL = f"{BASE_URL}/api/codebase/graph"
CODEBASE_FILE_URL = f"{BASE_URL}/api/codebase/file"
OBSIDIAN_NOTES_URL = f"{BASE_URL}/api/obsidian/notes"
OBSIDIAN_GRAPH_URL = f"{BASE_URL}/api/obsidian/graph"
OBSIDIAN_ACTIVATION_URL = f"{BASE_URL}/api/obsidian/activation"
INVESTIGATION_CASES_URL = f"{BASE_URL}/api/investigation/cases"
INVESTIGATION_GRAPH_URL = f"{BASE_URL}/api/investigation"  # + /{case_id}/graph
BRIGADA_MODEL_CONFIG_URL = f"{BASE_URL}/api/brigada/model-config"
BRIGADA_RUN_URL = f"{BASE_URL}/api/brigada/run"
TRADING_BRIGADA_RUN_URL = f"{BASE_URL}/api/trading/brigada/run"
TRADING_BACKTEST_RUN_URL = f"{BASE_URL}/api/trading/backtest/run"

# Preferimos el intérprete del venv del backend (ahi están instaladas sus
# dependencias). Si no existe, caemos a "python" del PATH.
_venv_python = BACKEND_DIR / ".venv" / "Scripts" / "python.exe"
BACKEND_PYTHON = str(_venv_python) if _venv_python.exists() else "python"

LOG_PATH = TRAY_DIR / "backend.log"

# Imagen que representa a Raphael (avatar de bienvenida + ícono de ventana).
# Agregada 2026-09-01 (pedido de Damian). Convertida de .webp a .png para que Qt
# la cargue sin depender del plugin webp.
ASSETS_DIR = TRAY_DIR / "assets"
RAPHAEL_IMAGE = ASSETS_DIR / "raphael.png"
RAPHAEL_ICON = ASSETS_DIR / "raphael_icon.png"
# Versión desenfocada, SOLO para el fondo animado de la ventana: las líneas finas
# de la imagen nítida "brillaban"/temblaban al desplazarse lento; el blur las
# suaviza y el movimiento queda imperceptible (pedido de Damian, 2026-09-01).
RAPHAEL_BG = ASSETS_DIR / "raphael_bg.png"

# Transcript del chat, para que la ventana muestre "todo lo que hablamos" al
# reabrir (pedido de Damian, 2026-09-01). Se guarda bajo backend/data/ que está
# gitignoreado (repo público: el chat NO se commitea). Es el historial VISIBLE;
# la memoria real del modelo la persiste el backend aparte (app/agent.py).
HISTORY_PATH = BACKEND_DIR / "data" / "tray_chat_history.json"

POLL_INTERVAL_SECONDS = 3

# Los 3 tiers del proyecto, mostrados en el selector con nombres simples --
# el id real (nombre de Ollama) queda oculto de la UI. "Hard" corta al mismo
# modelo que "Medio" (jarvis-text-hard es un alias de Ollama de jarvis-text-v2,
# ver `ollama cp`) porque lo que lo distingue no es el modelo de texto sino que
# ese tier es el pensado para tareas más pesadas (ej. generación de video, ya
# disponible como tool para el agente sin importar el tier activo). Usar un id
# de Ollama propio para Hard en vez de reusar "jarvis-text-v2" es necesario
# para que el selector pueda recordar cuál de los dos eligió el usuario.
AVAILABLE_MODELS = [
    {"id": "jarvis-text-lite", "label": "Lite"},
    {"id": "jarvis-text-v2", "label": "Medio"},
    {"id": "jarvis-text-hard", "label": "Hard"},
]
