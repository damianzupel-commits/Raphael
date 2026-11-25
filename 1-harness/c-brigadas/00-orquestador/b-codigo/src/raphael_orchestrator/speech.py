"""Voz hablada del orquestador (oír y hablar), enchufable: un adaptador real (local) y uno simulado (mock).

No confundir con `voice.py`, que es el ROL `voz` (arma el mensaje de texto con la persona de Raphael). Esto es el audio:
voz -> texto (STT) y texto -> voz (TTS). Portado de JarvisRemote (`voice/engine.py`), sin rutas de Damián.

Tres adaptadores con la misma interfaz (`Speech`):
  - `LocalSpeech`: faster-whisper + Piper en un subproceso (`speech_worker.py`), todo en la PC, sin red ni claves.
    Necesita instalar los paquetes y bajar una vez los modelos (ver `.env.plantilla` y LIENZO).
  - `MockSpeech`: no oye ni habla; devuelve lo que se le configure. Es el que usan los tests.
  - `NoSpeech`: apagado (o sin lo necesario); dice el motivo exacto y nunca lanza al consultar el estado.

Qué se elige: `speech.mode` de la config (`auto`, `local`, `mock`, `off`) o la variable `RAPHAEL_VOZ_MODO`. En `auto`: local
si están los paquetes y el modelo, si no queda apagado y lo AVISA (`status()` trae el motivo; el chequeo de salud lo muestra).
Nada de esto toca la nube: el audio y los textos no salen de la PC.
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
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

WORKER = Path(__file__).resolve().parent / "speech_worker.py"
VOICE_NAME = "es_AR-daniela-high"
MAX_AUDIO_BYTES = 20 * 1024 * 1024
MAX_SPEAK_CHARS = 1200
INSTALAR = ("pip install faster-whisper piper-tts, bajar el modelo Whisper y la voz es-AR de Piper "
            "(ver orquestador.env.plantilla) o apuntar VOICE_PYTHON a un Python que los tenga")
MODES = ("auto", "local", "mock", "off")


class SpeechError(RuntimeError):
    """Error de voz con un mensaje claro para mostrar."""


def clean_for_speech(text: str, max_chars: int = MAX_SPEAK_CHARS) -> str:
    """Saca el markdown y lo que no se lee bien (código, tablas, URLs, wikilinks) y recorta en un límite de oración."""
    t = text or ""
    t = re.sub(r"```.*?```", " ", t, flags=re.S)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), t)
    t = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"https?://\S+", "un enlace", t)
    t = re.sub(r"^\s*#{1,6}\s*", "", t, flags=re.M)
    t = re.sub(r"^\s*[-*+]\s+", "", t, flags=re.M)
    t = re.sub(r"^\s*\d+[.)]\s+", "", t, flags=re.M)
    t = re.sub(r"^\s*\|?[\s:|-]{3,}\|?\s*$", " ", t, flags=re.M)
    t = t.replace("|", ", ")
    t = re.sub(r"[*_~>]+", "", t)
    t = re.sub(r"\s*\n\s*", ". ", t)
    t = re.sub(r"\.\s*\.", ".", t)
    t = re.sub(r"\s{2,}", " ", t).strip(" .")
    if len(t) > max_chars:
        cut = t[:max_chars]
        k = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
        t = (cut[: k + 1] if k > max_chars // 3 else cut).strip() + " Cortado por largo."
    return t


class Speech(Protocol):
    """Lo que el resto del sistema usa de la voz hablada."""

    kind: str

    async def status(self, refresh: bool = False) -> dict: ...
    async def transcribe(self, data: bytes, suffix: str = ".webm") -> dict: ...
    async def speak(self, text: str) -> bytes: ...
    async def close(self) -> None: ...


class NoSpeech:
    """Voz apagada o sin lo necesario. `reason` dice por qué y qué hacer."""

    kind = "off"

    def __init__(self, reason: str = "la voz está apagada") -> None:
        self.reason = reason

    async def status(self, refresh: bool = False) -> dict:
        return {"kind": self.kind, "enabled": False, "local": True, "stt": {"ok": False, "motivo": self.reason},
                "tts": {"ok": False, "motivo": self.reason}}

    async def transcribe(self, data: bytes, suffix: str = ".webm") -> dict:
        raise SpeechError(self.reason)

    async def speak(self, text: str) -> bytes:
        raise SpeechError(self.reason)

    async def close(self) -> None:
        return None


class MockSpeech:
    """Voz simulada: `transcribe` devuelve `heard` y `speak` devuelve bytes que empiezan con RIFF. Guarda lo que le pasaron."""

    kind = "mock"

    def __init__(self, heard: str = "hola raphael") -> None:
        self.heard = heard
        self.spoken: list[str] = []
        self.heard_bytes: list[int] = []

    async def status(self, refresh: bool = False) -> dict:
        return {"kind": self.kind, "enabled": True, "local": True, "stt": {"ok": True, "mock": True},
                "tts": {"ok": True, "mock": True, "voz": "mock"}}

    async def transcribe(self, data: bytes, suffix: str = ".webm") -> dict:
        _check_audio(data)
        self.heard_bytes.append(len(data))
        return {"texto": self.heard, "idioma": "es", "segundos": 0.0}

    async def speak(self, text: str) -> bytes:
        clean = clean_for_speech(text)
        if not clean:
            raise SpeechError("no hay nada que leer")
        self.spoken.append(clean)
        return b"RIFF" + clean.encode("utf-8")

    async def close(self) -> None:
        return None


def _check_audio(data: bytes) -> None:
    if not data:
        raise SpeechError("no llegó audio")
    if len(data) > MAX_AUDIO_BYTES:
        raise SpeechError("el audio es demasiado largo")


def _rm(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


class LocalSpeech:
    """faster-whisper + Piper en un subproceso persistente. Un pedido a la vez; si muere, se relanza en el próximo.

    `python` = intérprete que tiene las librerías (por defecto `VOICE_PYTHON` o el actual); `voice_file` = el .onnx de Piper;
    `cmd` reemplaza el comando completo (los tests usan un worker falso)."""

    kind = "local"

    def __init__(self, *, python: str | None = None, voice_file: str | None = None, cmd: list[str] | None = None,
                 env: Mapping[str, str] | None = None, max_chars: int = MAX_SPEAK_CHARS) -> None:
        self._python = python
        self._voice = voice_file
        self._cmd = cmd
        self._env_extra = dict(env or {})
        self._max_chars = max_chars
        self._proc: asyncio.subprocess.Process | None = None
        self._lock = asyncio.Lock()
        self._ids = itertools.count(1)
        self._status: dict | None = None

    def _command(self) -> list[str]:
        if self._cmd:
            return self._cmd
        py = self._python or pick_python()
        if not py:
            raise SpeechError("no hay un Python con faster-whisper y piper-tts. Instalá: " + INSTALAR)
        return [py, str(WORKER)]

    def _env(self) -> dict[str, str]:
        env = dict(os.environ)
        voice = self._voice or pick_voice()
        if voice:
            env.setdefault("VOICE_PIPER_VOICE", voice)
        env.update({"HF_HUB_OFFLINE": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
        env.update(self._env_extra)
        return env

    async def _ensure(self) -> asyncio.subprocess.Process:
        if self._proc is not None and self._proc.returncode is None:
            return self._proc
        self._proc = await asyncio.create_subprocess_exec(
            *self._command(), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, env=self._env())
        return self._proc

    async def _call(self, req: dict, timeout: float) -> dict:
        async with self._lock:
            try:
                proc = await self._ensure()
            except OSError as exc:
                raise SpeechError(f"no se pudo lanzar el motor de voz ({type(exc).__name__}). Instalá: {INSTALAR}") from None
            req = {**req, "id": next(self._ids)}
            try:
                proc.stdin.write((json.dumps(req, ensure_ascii=False) + "\n").encode("utf-8"))
                await proc.stdin.drain()
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=timeout)
            except (TimeoutError, BrokenPipeError, ConnectionResetError):
                await self._kill()
                raise SpeechError("el motor de voz no respondió a tiempo; se reinicia en el próximo pedido") from None
            if not line:
                await self._kill()
                raise SpeechError("el motor de voz se cerró inesperadamente; se reinicia en el próximo pedido")
            res = json.loads(line.decode("utf-8"))
            if not res.get("ok"):
                raise SpeechError(res.get("error") or "falló el motor de voz")
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

    async def status(self, refresh: bool = False) -> dict:
        """Qué hay disponible, sin cargar modelos. Nunca lanza: si falta algo, lo explica (y no cachea la falla)."""
        if self._status is not None and not refresh:
            return self._status
        base = {"kind": self.kind, "enabled": True, "local": True, "dispositivo": os.getenv("VOICE_STT_DEVICE", "cpu"),
                "modelo_stt": os.getenv("VOICE_STT_MODEL", "small")}
        try:
            res = await self._call({"op": "check"}, timeout=90)
        except SpeechError as exc:
            return {**base, "stt": {"ok": False, "motivo": str(exc)}, "tts": {"ok": False, "motivo": str(exc)}}
        self._status = {**base, "stt": res["stt"], "tts": res["tts"]}
        return self._status

    async def transcribe(self, data: bytes, suffix: str = ".webm") -> dict:
        """Audio (webm/ogg/wav/mp3…) -> {'texto', 'idioma', 'segundos'}."""
        _check_audio(data)
        ext = suffix if re.fullmatch(r"\.[a-z0-9]{2,5}", suffix) else ".webm"
        fd, path = tempfile.mkstemp(suffix=ext, prefix="voz-stt-")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            return await self._call({"op": "stt", "path": path}, timeout=240)
        finally:
            _rm(path)

    async def speak(self, text: str) -> bytes:
        """Texto -> WAV (Piper, voz es-AR). Antes se limpia para que se pueda leer (sin markdown, código ni URLs)."""
        clean = clean_for_speech(text, self._max_chars)
        if not clean:
            raise SpeechError("no hay nada que leer")
        fd, path = tempfile.mkstemp(suffix=".wav", prefix="voz-tts-")
        os.close(fd)
        try:
            await self._call({"op": "tts", "text": clean, "out": path}, timeout=120)
            return Path(path).read_bytes()
        finally:
            _rm(path)


def pick_python(env: Mapping[str, str] | None = None) -> str | None:
    """Intérprete que tiene las librerías de voz: `VOICE_PYTHON` (si existe) o el actual si ya las tiene. None si ninguno."""
    env = os.environ if env is None else env
    chosen = (env.get("VOICE_PYTHON") or "").strip()
    if chosen:
        return chosen if Path(chosen).is_file() else None
    if all(importlib.util.find_spec(m) for m in ("faster_whisper", "piper")):
        return sys.executable
    return None


def pick_voice(env: Mapping[str, str] | None = None) -> str | None:
    """Ruta del .onnx de Piper es-AR: solo `VOICE_PIPER_VOICE` (la carga Damián; no se busca en carpetas ajenas)."""
    env = os.environ if env is None else env
    chosen = (env.get("VOICE_PIPER_VOICE") or "").strip()
    return chosen if chosen and Path(chosen).is_file() else None


def speech_enabled(env: Mapping[str, str] | None = None) -> bool:
    env = os.environ if env is None else env
    return (env.get("VOICE_ENABLED") or "1").strip().lower() not in ("0", "false", "no", "off")


def speech_from(mode: str = "auto", env: Mapping[str, str] | None = None) -> Speech:
    """El adaptador de voz que corresponde. `RAPHAEL_VOZ_MODO` gana a `mode`. Un modo desconocido es un error (no se adivina).
    En `auto`, sin lo necesario devuelve `NoSpeech` con el motivo (el sistema sigue por texto y lo dice)."""
    env = os.environ if env is None else env
    chosen = ((env.get("RAPHAEL_VOZ_MODO") or "").strip().lower() or mode)
    if chosen not in MODES:
        raise ValueError(f"modo de voz desconocido: {chosen!r} (esperaba uno de {', '.join(MODES)})")
    if chosen == "off" or not speech_enabled(env):
        return NoSpeech("la voz está apagada (modo off o VOICE_ENABLED=0)")
    if chosen == "mock":
        return MockSpeech()
    if chosen == "auto" and not pick_python(env):
        return NoSpeech("no hay un Python con faster-whisper y piper-tts: sigo por texto. Instalá: " + INSTALAR)
    if chosen == "auto" and not pick_voice(env):
        return NoSpeech("falta la voz es-AR de Piper (VOICE_PIPER_VOICE): sigo por texto. Instalá: " + INSTALAR)
    return LocalSpeech(python=pick_python(env), voice_file=pick_voice(env))


def describe(status: Mapping[str, Any]) -> str:
    """Una línea en castellano con el estado (para el chequeo de salud y el feed)."""
    def side(name: str, d: Mapping[str, Any]) -> str:
        return f"{name} {'andando' if d.get('ok') else 'no disponible (' + str(d.get('motivo', 'sin detalle')) + ')'}"

    return f"Voz hablada [{status.get('kind', '?')}]: " + "; ".join((side("oír", status.get("stt") or {}),
                                                                     side("hablar", status.get("tts") or {})))
