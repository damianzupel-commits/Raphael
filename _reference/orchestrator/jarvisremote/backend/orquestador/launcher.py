"""Piezas del arranque "como app" del Orquestador: detectar si ya corre, esperar a que esté
listo, abrir una ventana estilo app (sin barra de navegador), detenerlo y avisar errores sin consola.

Pensado para correr con `pythonw.exe` (sin ventana de consola): no hay stdout, así que los errores
van a un log y a un cuadro de mensaje en vez de a una terminal que nadie está mirando.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "orquestador.log"  # backend/data/ está gitignoreado
_PROFILE_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "RaphaelOrquestador" / "browser-profile"


def healthy(port: int, timeout: float = 1.0) -> bool:
    """¿Hay YA un orquestador nuestro escuchando en ese puerto? (no cualquier cosa en el puerto)."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        return bool(data.get("ok")) and "brigades" in data
    except Exception:  # noqa: BLE001
        return False


_BACKEND = Path(__file__).resolve().parent.parent
# Lo que, si cambia después de que el proceso arrancó, lo deja VIEJO: el código del orquestador/brigadas y el .env.
_WATCH = (("orquestador", ("*.py", "*.html")), ("brigades", ("*.py",)), ("scout", ("*.py",)), ("validation", ("*.py",)))


def code_mtime() -> float:
    """Fecha de la última modificación del código y la config que usa el orquestador (0 si no se puede leer)."""
    latest = 0.0
    try:
        for sub, pats in _WATCH:
            for pat in pats:
                for f in (_BACKEND / sub).glob(pat):
                    latest = max(latest, f.stat().st_mtime)
        env = _BACKEND / ".env"
        if env.exists():
            latest = max(latest, env.stat().st_mtime)
    except OSError:
        pass
    return latest


def started_at(port: int, timeout: float = 1.0) -> float | None:
    """Cuándo arrancó el orquestador que escucha en `port` (None si no informa: uno anterior a este chequeo)."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=timeout) as r:
            v = json.loads(r.read().decode("utf-8")).get("started")
        return float(v) if v is not None else None
    except Exception:  # noqa: BLE001
        return None


def is_stale(port: int) -> bool:
    """¿El orquestador que corre es VIEJO (arrancó antes de que cambiaran su código o su .env, o ni siquiera informa cuándo
    arrancó)? Reabrir la ventana sobre un proceso así muestra el código viejo aunque el disco ya tenga el nuevo: hay que
    reiniciarlo de verdad. Un `started` desconocido cuenta como viejo (es de antes de este chequeo)."""
    started = started_at(port)
    if started is None:
        return True
    return started + 1.0 < code_mtime()


def wait_ready(port: int, timeout: float = 60.0) -> bool:
    """Polling al health hasta que responda (o se acabe el tiempo)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if healthy(port):
            return True
        time.sleep(0.4)
    return False


def _browser_candidates() -> list[Path]:
    pf = [os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")]
    local = os.environ.get("LOCALAPPDATA", "")
    rel = [
        r"Microsoft\Edge\Application\msedge.exe",          # Edge: viene con Windows 11
        r"BraveSoftware\Brave-Browser\Application\brave.exe",
        r"Google\Chrome\Application\chrome.exe",
    ]
    out = [Path(base) / r for r in rel for base in pf if base]
    if local:
        out += [Path(local) / r for r in rel[1:]]
    return out


def find_browser() -> Path | None:
    return next((p for p in _browser_candidates() if p.is_file()), None)


def open_app_window(url: str) -> str:
    """Abre `url` en una ventana estilo app (Edge/Brave/Chrome con --app: sin pestañas ni barra
    de direcciones). Perfil propio y aparte: no mezcla historial/cookies con tu navegador. Si no
    hay ningún Chromium instalado, cae al navegador por defecto. Devuelve cómo se abrió."""
    exe = find_browser()
    if exe is None:
        webbrowser.open(url)
        return "navegador por defecto"
    _PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(
        [str(exe), f"--app={url}", f"--user-data-dir={_PROFILE_DIR}", "--no-first-run",
         "--no-default-browser-check", "--window-size=1100,820"],
        creationflags=flags, close_fds=True,
    )
    return f"ventana app ({exe.stem})"


def stop(port: int) -> int | None:
    """Detiene el orquestador que escucha en `port`. Solo mata un proceso si su línea de comando
    es run_orquestador (nunca otro servicio que casualmente use el puerto). Devuelve el PID o None."""
    import psutil

    for conn in psutil.net_connections(kind="tcp"):
        if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.port == port and conn.pid:
            proc = psutil.Process(conn.pid)
            if "run_orquestador" in " ".join(proc.cmdline()):
                proc.terminate()
                return conn.pid
    return None


def redirect_output_if_windowless() -> None:
    """Con pythonw no hay stdout/stderr (None) y uvicorn revienta al loguear: se redirigen a un log."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log = open(LOG_PATH, "a", encoding="utf-8", buffering=1)  # noqa: SIM115 — vive lo que viva el proceso
    sys.stdout = sys.stdout or log
    sys.stderr = sys.stderr or log


def message_box(title: str, text: str) -> None:
    """Aviso visible cuando no hay consola. Silencioso si no se puede (no-Windows)."""
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)  # MB_ICONERROR
    except Exception:  # noqa: BLE001
        pass
