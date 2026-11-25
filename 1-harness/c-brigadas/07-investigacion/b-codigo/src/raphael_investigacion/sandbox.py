"""Espacio aislado para correr prototipos de código (solo Python) de la brigada Ideas y prototipos.

Qué hace: revisa el código antes de correrlo (imports y llamadas que no entran), lo escribe en una carpeta temporal vacía,
lo corre con el intérprete en modo aislado (`-I`), entorno vacío, tope de tiempo, de memoria y de tamaño de archivos
(donde el sistema lo permite), y devuelve la salida acotada. La carpeta se borra al terminar.

Qué NO es: un sandbox de sistema operativo. No garantiza aislamiento de red ni de disco fuera de la carpeta temporal (en
Windows tampoco hay topes de memoria). Por eso correr un prototipo SIEMPRE pide aprobación de una persona que vio el
código, y la tool es peligrosa: no se carga en la nube.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
import time

DENIED_IMPORTS = frozenset({
    "socket", "ssl", "subprocess", "ctypes", "multiprocessing", "shutil", "urllib", "http", "ftplib", "smtplib", "telnetlib",
    "requests", "httpx", "aiohttp", "pty", "signal", "resource", "webbrowser", "xmlrpc", "socketserver", "asyncio.subprocess"})
DENIED_CALLS = frozenset({"eval", "exec", "compile", "__import__", "breakpoint", "input"})
DENIED_ATTRS = frozenset({"system", "popen", "fork", "forkpty", "kill", "killpg", "execv", "execve", "execvp", "spawnl",
                          "spawnv", "remove", "rmdir", "unlink", "removedirs", "rmtree", "chmod", "chown", "startfile"})
MAX_OUTPUT = 20_000
MAX_CODE = 100_000


def review_code(code: str) -> list[str]:
    """Problemas que impiden correrlo (lista vacía = pasa la revisión). Es una revisión estática: ayuda, no garantiza."""
    if len(code) > MAX_CODE:
        return [f"el código pasa los {MAX_CODE} caracteres"]
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"no compila: {exc.msg} (línea {exc.lineno})"]
    problems: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            problems += [f"import no permitido: {a.name}" for a in node.names if a.name.split(".")[0] in DENIED_IMPORTS]
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in DENIED_IMPORTS:
            problems.append(f"import no permitido: {node.module}")
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id in DENIED_CALLS:
                problems.append(f"llamada no permitida: {f.id}()")
            elif isinstance(f, ast.Attribute) and f.attr in DENIED_ATTRS:
                problems.append(f"llamada no permitida: .{f.attr}()")
    return sorted(set(problems))


def _limits(memory_mb: int, cpu_seconds: int):
    def apply() -> None:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        resource.setrlimit(resource.RLIMIT_AS, (memory_mb * 1024 * 1024, memory_mb * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_FSIZE, (5 * 1024 * 1024, 5 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
    return apply


def run_python(code: str, *, timeout: float = 10.0, memory_mb: int = 256) -> dict:
    problems = review_code(code)
    if problems:
        return {"ran": False, "problems": problems, "exit_code": None, "stdout": "", "stderr": "", "timed_out": False, "seconds": 0.0}
    with tempfile.TemporaryDirectory(prefix="raphael-proto-") as tmp:
        script = os.path.join(tmp, "main.py")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(code)
        kw: dict = {}
        if os.name == "posix":
            kw["preexec_fn"] = _limits(memory_mb, max(1, int(timeout) + 1))
        t0 = time.monotonic()
        try:
            proc = subprocess.run([sys.executable, "-I", script], cwd=tmp, env={"PYTHONIOENCODING": "utf-8"}, capture_output=True,  # noqa: S603
                                  timeout=timeout, text=True, encoding="utf-8", errors="replace", **kw)
            out = {"exit_code": proc.returncode, "stdout": proc.stdout[:MAX_OUTPUT], "stderr": proc.stderr[:MAX_OUTPUT],
                   "timed_out": False}
        except subprocess.TimeoutExpired as exc:
            def cut(b: bytes | str | None) -> str:
                return (b.decode("utf-8", "replace") if isinstance(b, bytes) else (b or ""))[:MAX_OUTPUT]
            out = {"exit_code": None, "stdout": cut(exc.stdout), "stderr": cut(exc.stderr), "timed_out": True}
    return {"ran": True, "problems": [], "seconds": round(time.monotonic() - t0, 2), **out}
