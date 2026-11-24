"""Motor de VOZ LOCAL del orquestador: habla con `voice/worker.py` (subproceso persistente) y expone STT y TTS.

Todo es local y privado: el audio y los textos no salen de la PC (el worker corre sin red y con los modelos en disco).
Apagable con `VOICE_ENABLED=0`. No usa la GPU por default (`VOICE_STT_DEVICE=cpu`).

Qué intérprete usa el worker (en orden): `VOICE_PYTHON` -> el Python actual si ya tiene faster-whisper y piper-tts ->
el venv del prototipo viejo `cerebro-fenix/_Jarvis-Local/venv` (que ya los tiene). Si ninguno sirve, `status()` dice
EXACTAMENTE qué instalar; no se inventa nada.
"""

from __future__ import annotations

import asyncio
import importlib.util
import itertools
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parent.parent
WORKER = Path(__file__).resolve().parent / "worker.py"
VOICE_NAME = "es_AR-daniela-high"
MAX_AUDIO_BYTES = 20 * 1024 * 1024
MAX_SPEAK_CHARS = 1200
_PROTOTIPO = Path.home() / "cerebro-fenix" / "_Jarvis-Local"
INSTALAR = "pip install -r backend/requirements-voice.txt (faster-whisper + piper-tts) o apuntá VOICE_PYTHON a un Python que los tenga"


class VoiceError(RuntimeError):
    """Error de voz con un mensaje claro para mostrar."""


def enabled() -> bool:
    return os.getenv("VOICE_ENABLED", "1").strip().lower() not in ("0", "false", "no", "off")


def pick_python() -> str | None:
    """Intérprete que tiene las librerías de voz (ver docstring del módulo). None si ninguno."""
    env = os.getenv("VOICE_PYTHON", "").strip()
    if env:
        return env if Path(env).is_file() else None
    if all(importlib.util.find_spec(m) for m in ("faster_whisper", "piper")):
        return sys.executable
    proto = _PROTOTIPO / "venv" / "Scripts" / "python.exe"
    return str(proto) if proto.is_file() else None


def pick_voice() -> str | None:
    """Ruta del .onnx de Piper es-AR: VOICE_PIPER_VOICE -> backend/data/voices -> la voz del prototipo viejo."""
    env = os.getenv("VOICE_PIPER_VOICE", "").strip()
    cands = [Path(env)] if env else []
    cands += [BACKEND / "data" / "voices" / f"{VOICE_NAME}.onnx", _PROTOTIPO / "voices" / f"{VOICE_NAME}.onnx"]
    return next((str(p) for p in cands if p.is_file()), None)


# --- texto -> algo que se pueda LEER en voz alta ---------------------------------------------------------------------
def limpiar_para_voz(text: str, max_chars: int = MAX_SPEAK_CHARS) -> str:
    """Saca el markdown y lo que no se lee bien (código, tablas, URLs, wikilinks) y recorta en un límite de oración."""
    t = text or ""
    t = re.sub(r"```.*?```", " ", t, flags=re.S)                     # bloques de código
    t = re.sub(r"`([^`]*)`", r"\1", t)                                # código en línea
    t = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), t)  # [[nota]] -> nota
    t = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", t)                  # [texto](url) -> texto
    t = re.sub(r"https?://\S+", "un enlace", t)
    t = re.sub(r"^\s*#{1,6}\s*", "", t, flags=re.M)                   # títulos
    t = re.sub(r"^\s*[-*+]\s+", "", t, flags=re.M)                    # viñetas
    t = re.sub(r"^\s*\d+[.)]\s+", "", t, flags=re.M)                  # listas numeradas
    t = re.sub(r"^\s*\|?[\s:|-]{3,}\|?\s*$", " ", t, flags=re.M)      # separadores de tabla
    t = t.replace("|", ", ")
    t = re.sub(r"[*_~>]+", "", t)                                     # énfasis y citas
    t = re.sub(r"\s*\n\s*", ". ", t)
    t = re.sub(r"\.\s*\.", ".", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" .")
    if len(t) > max_chars:
        cut = t[:max_chars]
        k = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
        t = (cut[: k + 1] if k > max_chars // 3 else cut).strip() + " Cortado por largo."
    return t


class VoiceEngine:
    """Habla con el worker. Un pedido a la vez (el worker es de un solo hilo); si muere, se relanza en el próximo pedido."""

    def __init__(self, cmd: list[str] | None = None, env: dict[str, str] | None = None) -> None:
        self._cmd_override = cmd
        self._env_extra = env or {}
        self._proc: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()
        self._ids = itertools.count(1)
        self._status: dict | None = None

    # --- proceso -------------------------------------------------------------------------------------------------
    def _command(self) -> list[str]:
        if self._cmd_override:
            return self._cmd_override
        py = pick_python()
        if not py:
            raise VoiceError("no hay un Python con faster-whisper y piper-tts. Instalá: " + INSTALAR)
        return [py, str(WORKER)]

    def _env(self) -> dict[str, str]:
        env = dict(os.environ)
        voice = pick_voice()
        if voice:
            env.setdefault("VOICE_PIPER_VOICE", voice)
        env.update({"HF_HUB_OFFLINE": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
        env.update(self._env_extra)
        return env

    async def _ensure(self) -> asyncio.subprocess.Process:
        if self._proc is not None and self._proc.returncode is None:
            return self._proc
        self._proc = await asyncio.create_subprocess_exec(
            *self._command(), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
            env=self._env(), cwd=str(BACKEND))
        return self._proc

    async def _call(self, req: dict, timeout: float) -> dict:
        async with self._lock:
            proc = await self._ensure()
            rid = next(self._ids)
            req = {**req, "id": rid}
            try:
                proc.stdin.write((json.dumps(req, ensure_ascii=False) + "\n").encode("utf-8"))
                await proc.stdin.drain()
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=timeout)
            except (asyncio.TimeoutError, BrokenPipeError, ConnectionResetError):
                await self._kill()
                raise VoiceError("el motor de voz no respondió a tiempo; se reinicia en el próximo pedido") from None
            if not line:
                await self._kill()
                raise VoiceError("el motor de voz se cerró inesperadamente; se reinicia en el próximo pedido")
            res = json.loads(line.decode("utf-8"))
            if not res.get("ok"):
                raise VoiceError(res.get("error") or "falló el motor de voz")
            return res

    async def _kill(self) -> None:
        if self._proc is not None and self._proc.returncode is None:
            try:
                self._proc.kill()
                await self._proc.wait()
            except ProcessLookupError:
                pass
        self._proc = None

    async def close(self) -> None:
        async with self._lock:
            await self._kill()

    # --- API -----------------------------------------------------------------------------------------------------
    async def status(self, refresh: bool = False) -> dict:
        """Qué hay disponible, sin cargar modelos. Nunca lanza: si falta algo, lo explica."""
        if not enabled():
            return {"enabled": False, "local": True, "stt": {"ok": False, "motivo": "la voz está apagada (VOICE_ENABLED=0)"},
                    "tts": {"ok": False, "motivo": "la voz está apagada (VOICE_ENABLED=0)"}}
        if self._status is not None and not refresh:
            return self._status
        base = {"enabled": True, "local": True, "dispositivo": os.getenv("VOICE_STT_DEVICE", "cpu"),
                "modelo_stt": os.getenv("VOICE_STT_MODEL", "small")}
        try:
            res = await self._call({"op": "check"}, timeout=90)
            st = {**base, "stt": res["stt"], "tts": res["tts"]}
        except VoiceError as exc:
            st = {**base, "stt": {"ok": False, "motivo": str(exc)}, "tts": {"ok": False, "motivo": str(exc)}}
            return st  # no se cachea una falla: el próximo pedido reintenta
        self._status = st
        return st

    async def transcribe(self, data: bytes, suffix: str = ".webm") -> dict:
        """Audio (webm/ogg/wav/mp3…; faster-whisper lo decodifica) -> {'texto', 'idioma', 'segundos'}."""
        if not enabled():
            raise VoiceError("la voz está apagada (VOICE_ENABLED=0)")
        if not data:
            raise VoiceError("no llegó audio")
        if len(data) > MAX_AUDIO_BYTES:
            raise VoiceError("el audio es demasiado largo")
        fd, path = tempfile.mkstemp(suffix=suffix if re.fullmatch(r"\.[a-z0-9]{2,5}", suffix) else ".webm", prefix="voz-stt-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            return await self._call({"op": "stt", "path": path}, timeout=240)
        finally:
            _rm(path)

    async def speak(self, text: str) -> bytes:
        """Texto -> WAV (Piper, voz es-AR). El texto se limpia para que se pueda leer (sin markdown, ni código, ni URLs)."""
        if not enabled():
            raise VoiceError("la voz está apagada (VOICE_ENABLED=0)")
        limpio = limpiar_para_voz(text)
        if not limpio:
            raise VoiceError("no hay nada que leer")
        fd, path = tempfile.mkstemp(suffix=".wav", prefix="voz-tts-")
        os.close(fd)
        try:
            await self._call({"op": "tts", "text": limpio, "out": path}, timeout=120)
            return Path(path).read_bytes()
        finally:
            _rm(path)


def _rm(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


_ENGINE: VoiceEngine | None = None


def get_engine() -> VoiceEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = VoiceEngine()
    return _ENGINE
