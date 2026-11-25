"""Shell de la PC. Portado de `shell_exec.py`: subprocess con tope de tiempo duro, muerte del árbol de procesos y salida
acotada.

Cambio respecto de JarvisRemote: en POSIX el proceso arranca en su propia sesión (`start_new_session`). Antes se mataba
el grupo de procesos con `killpg` sin haberlo separado, o sea el del propio servidor.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Protocol

MAX_TIMEOUT_SECONDS = 600.0
MAX_OUTPUT_CHARS = 20000


class ShellRunner(Protocol):
    def run(self, command: str, cwd: Path, timeout: float) -> dict: ...


def truncate_output(text: str) -> tuple[str, bool]:
    return (text[:MAX_OUTPUT_CHARS], True) if len(text) > MAX_OUTPUT_CHARS else (text, False)


def kill_process_tree(pid: int) -> None:
    """Mata el proceso y todos sus hijos (en Windows un `cmd /c` puede dejar subprocesos huérfanos)."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW)
        return
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


class RealShell:
    """Corre comandos de verdad. Quien lo llama ya pasó el interruptor, el guardarraíl y la aprobación."""

    def run(self, command: str, cwd: Path, timeout: float) -> dict:
        effective = min(float(timeout), MAX_TIMEOUT_SECONDS)
        kwargs: dict = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        proc = subprocess.Popen(command, cwd=str(cwd), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace", **kwargs)
        timed_out = False
        try:
            stdout, stderr = proc.communicate(timeout=effective)
        except subprocess.TimeoutExpired:
            timed_out = True
            kill_process_tree(proc.pid)
            stdout, stderr = proc.communicate()
        stdout, out_cut = truncate_output(stdout)
        stderr, err_cut = truncate_output(stderr)
        return {"command": command, "cwd": str(cwd), "exit_code": proc.returncode, "stdout": stdout, "stderr": stderr,
                "timed_out": timed_out, "stdout_truncated": out_cut, "stderr_truncated": err_cut}


class MockShell:
    """No ejecuta nada: anota el comando y contesta lo que se le pidió (por defecto, salida vacía y código 0)."""

    def __init__(self, responses: dict[str, dict] | None = None) -> None:
        self.responses = dict(responses or {})
        self.calls: list[dict] = []

    def run(self, command: str, cwd: Path, timeout: float) -> dict:
        self.calls.append({"command": command, "cwd": str(cwd), "timeout": timeout})
        base = {"command": command, "cwd": str(cwd), "exit_code": 0, "stdout": f"[simulado] {command}", "stderr": "",
                "timed_out": False, "stdout_truncated": False, "stderr_truncated": False, "simulated": True}
        return {**base, **self.responses.get(command, {})}
