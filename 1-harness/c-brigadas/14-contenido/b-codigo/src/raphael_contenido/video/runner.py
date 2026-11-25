"""Quién corre ffmpeg: el real (subproceso en la PC) y el simulado (para los tests y para probar sin ffmpeg instalado).

Los dos tienen la misma forma: `exe()` (el ejecutable) y `run(cmd, timeout, cwd) -> (código, stderr)`. El simulado no corre
nada: anota cada comando, deja un archivo de salida chico (y falla si ya existía, como ffmpeg con `-n`) y contesta las
lecturas de duración y pistas con datos fijos que se pueden cambiar por archivo.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


class RealRunner:
    """ffmpeg de verdad: `VIDEO_FFMPEG_PATH`, el del PATH o el de `imageio-ffmpeg`. Sin shell, con prioridad baja."""

    real = True

    def exe(self) -> str:
        from .edicion import VideoError

        exe = os.getenv("VIDEO_FFMPEG_PATH", "").strip() or shutil.which("ffmpeg")
        if not exe:
            try:
                import imageio_ffmpeg  # opcional: trae un ffmpeg propio (pip install imageio-ffmpeg)

                exe = imageio_ffmpeg.get_ffmpeg_exe()
            except Exception:  # noqa: BLE001
                exe = None
        if not exe or not (shutil.which(exe) or Path(exe).is_file()):
            raise VideoError("ffmpeg no está instalado en esta PC. Instalalo (winget install Gyan.FFmpeg, o pip install imageio-ffmpeg) "
                             "o indicá su ruta en VIDEO_FFMPEG_PATH.")
        return exe

    @staticmethod
    def _popen_kwargs() -> dict:
        if sys.platform == "win32":
            return {"creationflags": 0x00004000 | 0x08000000}  # BELOW_NORMAL_PRIORITY_CLASS | CREATE_NO_WINDOW
        return {"preexec_fn": lambda: os.nice(10)}

    def run(self, cmd: list[str], timeout: float, cwd: str | None) -> tuple[int, str]:
        from .edicion import VideoError

        try:
            p = subprocess.run(cmd, capture_output=True, timeout=timeout, cwd=cwd, **self._popen_kwargs())
        except subprocess.TimeoutExpired:
            raise VideoError(f"ffmpeg superó el tiempo máximo ({int(timeout)} s) y se cortó.") from None
        return p.returncode, p.stderr.decode("utf-8", "replace")

    def available(self) -> bool:
        try:
            self.exe()
            return True
        except Exception:  # noqa: BLE001
            return False


class SimulatedRunner:
    """ffmpeg de mentira. `media` = {nombre de archivo: {duracion_s, ancho, alto, fps, video, audio}} para lo que se lea."""

    real = False
    DEFAULT = {"duracion_s": 10.0, "ancho": 1080, "alto": 1920, "fps": 30, "video": True, "audio": True}

    def __init__(self, media: dict | None = None) -> None:
        self.media = dict(media or {})
        self.calls: list[list[str]] = []

    def exe(self) -> str:
        return "ffmpeg-simulado"

    def available(self) -> bool:
        return True

    def _facts(self, path: str) -> dict:
        return {**self.DEFAULT, **self.media.get(Path(path).name, {})}

    def run(self, cmd: list[str], timeout: float, cwd: str | None) -> tuple[int, str]:
        self.calls.append(list(cmd))
        args = cmd[1:]
        # lectura de datos de un archivo: `-i x` sin salida
        if len(args) >= 2 and args[-2] == "-i":
            f = self._facts(args[-1])
            h, rest = divmod(f["duracion_s"], 3600)
            m, sec = divmod(rest, 60)
            lines = [f"  Duration: {int(h):02d}:{int(m):02d}:{sec:05.2f}, start: 0.000000, bitrate: 1000 kb/s"]
            if f["video"]:
                lines.append(f"  Stream #0:0: Video: h264, yuv420p, {f['ancho']}x{f['alto']}, {f['fps']} fps, 30 tbr")
            if f["audio"]:
                lines.append("  Stream #0:1: Audio: aac, 48000 Hz, stereo")
            return 1, "\n".join(lines)   # ffmpeg sin salida devuelve 1 y lista los datos en stderr
        if any("silencedetect" in a for a in args):
            return 0, ""
        out = Path(args[-1])
        if not out.is_absolute() and cwd:
            out = Path(cwd) / out
        if out.suffix:
            if out.exists():
                return 1, f"File '{out}' already exists. Exiting."
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"SIMULADO")
        return 0, ""
