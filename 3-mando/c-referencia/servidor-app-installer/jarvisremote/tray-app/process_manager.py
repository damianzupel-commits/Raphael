"""Arranca/para el backend como subproceso y le manda stdout+stderr a un log file."""

import subprocess
import sys
import threading
import time

import config

_process: subprocess.Popen | None = None
_lock = threading.Lock()


def _find_listening_pid(port: int) -> int | None:
    """Busca qué PID tiene el puerto del backend en LISTENING, sin asumir que
    coincide con `_process` -- durante desarrollo el backend se reinició muchas
    veces a mano (por fuera de la tray), así que `_process` no siempre refleja
    el proceso real corriendo. Sin esto, `stop()`/`start()` podían terminar
    lanzando un segundo backend compitiendo por el mismo puerto."""
    try:
        output = subprocess.check_output(
            ["netstat", "-ano"], text=True, creationflags=subprocess.CREATE_NO_WINDOW
        )
    except Exception:
        return None
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0] == "TCP" and parts[1].endswith(f":{port}") and parts[3] == "LISTENING":
            try:
                return int(parts[-1])
            except ValueError:
                continue
    return None


def _port_in_use(port) -> bool:
    return _find_listening_pid(port) is not None


def _wait_port_listening(port, timeout: float) -> bool:
    """Espera hasta que ALGO quede escuchando el puerto (backend arriba), o hasta
    el timeout. Sirve para confirmar que start() realmente levantó el backend en
    vez de reportar éxito a ciegas (y comerse un 10048 silencioso)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _port_in_use(port):
            return True
        time.sleep(0.5)
    return False


def _wait_port_released(port, timeout: float = 8.0) -> bool:
    """Espera hasta que el puerto quede LIBRE (backend viejo terminó de soltarlo),
    o hasta el timeout. Clave anti-10048: sin esto, un start() disparado justo
    después de un stop() encontraba el puerto todavía ocupado por el proceso que
    se estaba cerrando y el nuevo backend chocaba (error 10048)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _port_in_use(port):
            return True
        time.sleep(0.3)
    return False


def is_running() -> bool:
    with _lock:
        if _process is not None and _process.poll() is None:
            return True
        return _find_listening_pid(config.PORT) is not None


def start() -> str:
    global _process
    with _lock:
        if _process is not None and _process.poll() is None:
            return "El backend ya está corriendo."
        # Si YA hay algo escuchando el puerto (backend externo, p.ej. lanzado a
        # mano en PowerShell, u otra tray), NO lanzamos un segundo backend: nos
        # "conectamos" al existente. Un solo backend, todos los clientes se atan.
        if _port_in_use(config.PORT):
            return "El backend ya está corriendo — me conecto al existente."

        log_file = open(config.LOG_PATH, "a", encoding="utf-8")
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        _process = subprocess.Popen(
            [config.BACKEND_PYTHON, "run.py"],
            cwd=str(config.BACKEND_DIR),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            # Sin esto, el backend hereda el stdin de la tray (pythonw.exe, sin
            # consola en absoluto) -- un handle de stdin inválido/heredado de una
            # cadena sin consola rompe el spawn de subprocesos DEL BACKEND, como
            # el que hace Playwright para lanzar Chromium (browser_open fallaba
            # 100% de las veces con "BrowserType.launch: spawn UNKNOWN", bug real
            # encontrado el 26/07 durante las pruebas de voz). DEVNULL le da al
            # backend un stdin válido y vacío en vez de uno heredado y roto.
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        pid = _process.pid

    # Fuera del lock: confirmamos que el backend LEVANTÓ de verdad (o falló), en
    # vez de reportar éxito a ciegas. El import del backend es pesado, damos
    # margen. Así, si chocó por 10048 (puerto ocupado) y run.py murió, lo decimos.
    if _wait_port_listening(config.PORT, timeout=30.0):
        return f"Backend iniciado (pid {pid})."
    with _lock:
        murio = _process is None or _process.poll() is not None
    if murio:
        return "El backend no pudo arrancar (¿puerto 8000 ocupado por otro proceso? mirá backend.log)."
    return f"Backend arrancando (pid {pid})… está tardando más de lo normal."


def stop(only_own: bool = False) -> str:
    """Detiene el backend. `only_own=True`: SOLO detiene el backend que lanzó ESTA
    tray; si el backend lo levantaste por afuera (PowerShell) o es de otra tray, lo
    deja intacto. Se usa al CERRAR la tray, para que cerrar un cliente no te mate un
    backend compartido que estás usando desde otro lado. Con `only_own=False`
    (menú "Detener backend" y cambio de modelo) sí baja cualquier backend del puerto."""
    global _process
    with _lock:
        proc = _process
        _process = None

    if proc is not None and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
        # Esperar a que el puerto quede LIBRE antes de volver: así un start()
        # inmediato (ej. cambio de modelo) no choca con el que se está cerrando.
        _wait_port_released(config.PORT)
        return f"Backend detenido (pid {proc.pid})."

    # `_process` no era nuestro (o ya murió). Si nos pidieron solo lo propio, no
    # tocamos un backend externo/compartido.
    if only_own:
        return "No había un backend propio para detener (dejo intacto cualquiera externo)."

    # `_process` no coincide con la realidad (reinicio manual, u otra tray) --
    # verificar por el puerto real antes de reportar "no estaba corriendo".
    pid = _find_listening_pid(config.PORT)
    if pid is not None:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            creationflags=subprocess.CREATE_NO_WINDOW,
            capture_output=True,
        )
        _wait_port_released(config.PORT)
        return f"Backend detenido (pid {pid})."
    return "El backend no estaba corriendo."


def set_active_model(model_id: str) -> str:
    """Cambia el modelo activo del backend: reescribe LMSTUDIO_MODEL en
    backend/.env y reinicia el proceso para que lo tome (el backend lee el .env
    una sola vez, al arrancar). Usado por el selector de modelo de la UI."""
    lines = config.ENV_PATH.read_text(encoding="utf-8").splitlines()
    new_lines = []
    found = False
    for line in lines:
        if line.startswith("LMSTUDIO_MODEL="):
            new_lines.append(f"LMSTUDIO_MODEL={model_id}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"LMSTUDIO_MODEL={model_id}")
    config.ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    stop()
    return start()
