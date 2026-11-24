"""Escucha continua de voz para hablarle a Jarvis desde la PC sin tocar nada.

Pipeline 100% local (misma filosofía que el resto del proyecto):

    mic (16kHz mono) -> openWakeWord "hey jarvis" -> beep de confirmación
        -> grabación del comando hasta silencio (Silero VAD, el .onnx que ya
           trae empaquetado openwakeword) -> transcripción con faster-whisper
        -> POST /api/chat (el mismo endpoint que usan la app Android y la
           ventana de chat de la tray)

Correcciones de diseño contra los 4 síntomas reportados de la implementación
de voz anterior (que no era de este repo, pero sirven de checklist):
  1. "no arranca a grabar": acá no hay botón — el stream del mic queda abierto
     todo el tiempo que el toggle esté prendido, y el wake word es lo único que
     dispara la grabación. El beep confirma la detección al instante.
  2. "no deja de grabar": el fin de la grabación lo decide un VAD real (Silero)
     con un umbral de silencio configurable, más un tope duro de duración.
  3. "el audio se corta": un único InputStream continuo con buffer generoso;
     el mismo stream alimenta wake word y grabación (no se cierra/reabre entre
     fases, que es donde suelen perderse frames).
  4. "transcribe mal": faster-whisper `small` con language='es' fijo (nada de
     autodetección que a veces traduce en vez de transcribir).
"""

import logging
import queue
import threading
import time
import wave
from datetime import datetime
from pathlib import Path

import numpy as np
import requests
import sounddevice as sd

import config

try:
    import tts  # voz de salida (Fase 1 de SPEC-RAPHAEL-VOZ). Opcional: si falla, Raphael no habla pero escucha igual.
except Exception:  # noqa: BLE001
    tts = None

logger = logging.getLogger("jarvis.voice")

SAMPLE_RATE = 16000
FRAME_SAMPLES = 1280  # 80 ms, el tamaño de frame que espera openwakeword

# Modelo custom (models/hey_jarvis.onnx, entrenado con TTS en 22 voces/acentos de
# español) reemplazó al preentrenado en inglés que dejaba la voz real de Damian en
# 0.006-0.365 -- demasiado inconsistente para cualquier umbral fijo. Vuelto al 0.5
# estándar porque el modelo custom ya está calibrado para esta frase en español;
# validado offline (recall 0.999, fp_rate 0.08% sobre ~70 oraciones negativas
# distintas) pero la voz real de Damian con este modelo nuevo TODAVÍA NO se probó
# en vivo -- ajustar si hace falta tras esa prueba.
WAKE_THRESHOLD = 0.5
# El VAD se evalúa por frame de 80ms; el comando termina tras este silencio.
# Subido a 2.5 (2026-09-25): 1.2 y 1.7 cortaban a Damian en las pausas naturales
# de su forma de hablar. 2.5 le da aire para pensar/respirar sin que corte. Costo:
# espera 2.5s de silencio antes de dar por terminado el comando y responder.
SILENCE_SECONDS_TO_STOP = 2.5
MAX_COMMAND_SECONDS = 20
# Bajado de 0.3 a 0.25 (2026-09-25): 0.3 se comía arranques/palabras dichas más
# bajo. Más sensible = agarra mejor la frase entera, a costa de algún frame de
# ruido de más (que el silencio de arriba igual descarta).
VAD_SPEECH_THRESHOLD = 0.25
# Colchón que se guarda ANTES del momento del wake word, para no perder el
# arranque del comando si el usuario habla pegado a "hey jarvis".
PRE_ROLL_SECONDS = 0.4

# --- Modo conversación (Fase 1 de SPEC-RAPHAEL-VOZ) ---------------------------
# Tras responder (y hablar), Raphael queda escuchando una respuesta de seguimiento
# SIN exigir de nuevo "hey jarvis", para que sea una charla manos-libres. Si en
# FOLLOWUP_WAIT_SECONDS no escucha que empieces a hablar, corta la seguidilla y
# vuelve a esperar el wake word (evita quedar escuchando para siempre).
CONVERSATION_FOLLOWUP = True
FOLLOWUP_WAIT_SECONDS = 6.0

# Frases que Whisper suele "alucinar" cuando el audio es ruido o silencio (vienen
# de subtítulos de YouTube en sus datos de entrenamiento). Si la transcripción es
# corta y contiene una de estas, es casi seguro ruido inventado -> se descarta,
# para que Raphael no "escuche" cosas que nunca dijiste.
_HALLUCINATION_HINTS = (
    "gracias por ver",
    "subtitulos",
    "subtítulos",
    "suscrib",
    "suscríb",
    "campanita",
    "amara.org",
    "no olvides suscribirte",
    "nos vemos en el próximo",
    "muchas gracias por ver",
)


def _looks_like_hallucination(text: str) -> bool:
    """True si el texto parece una frase inventada por Whisper sobre ruido. Solo
    descarta frases CORTAS (<=60 chars) que matcheen, para no tirar un comando
    real largo que casualmente mencione alguna de estas palabras."""
    t = text.lower().strip(" .,!¡?¿-\"'")
    if len(t) < 2:
        return True
    return len(t) <= 60 and any(h in t for h in _HALLUCINATION_HINTS)


class VoiceListener:
    """Hilo de escucha continua. start()/stop() son idempotentes.

    `on_event(kind, text)` se llama (desde el hilo de escucha) con:
      kind="wake"        detectó la wake word, empieza a grabar
      kind="transcript"  texto transcripto que se manda al backend
      kind="reply"       respuesta de Jarvis
      kind="error"       cualquier error no fatal (el loop sigue vivo)
    """

    def __init__(self, on_event=None, require_wake_word: bool = True):
        self._on_event = on_event or (lambda kind, text: None)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        # False para el botón de la barra lateral de la ventana de PC: ya es un
        # gesto activo del usuario (click), pedirle además "hey jarvis" es
        # redundante. True sigue siendo el default para una futura escucha
        # pasiva/en background, donde sí hace falta un gatillo antes de grabar.
        self._require_wake_word = require_wake_word
        # Referencia al stream de audio en vivo -- ver stop(): sin esto, apagar
        # el toggle mientras el hilo está trabado transcribiendo o esperando al
        # backend (hasta 600s) dejaba el micrófono físicamente abierto todo ese
        # tiempo, aunque el botón ya mostrara "apagado". Bug real reportado por
        # Damian el 26/07.
        self._stream: sd.InputStream | None = None
        # Mientras Raphael HABLA (TTS), esto se pone en True y el callback de
        # audio descarta los frames -- así el micrófono no captura su propia voz
        # por los parlantes y no la transcribe como un comando (eco / medio-duplex).
        self._speaking = False
        # Carga perezosa: los modelos tardan segundos y no queremos pagar eso
        # al abrir la tray si el usuario nunca prende la escucha.
        self._oww = None
        self._vad = None
        self._whisper = None

    # ---------------------------------------------------------------- público

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        with self._lock:
            if self.is_running():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._stop.set()
            thread = self._thread
            stream = self._stream
        # Corta el audio YA -- no hay que esperar a que el hilo de escucha
        # vuelva a chequear `_stop` (eso puede tardar minutos si está bloqueado
        # en `_whisper.transcribe()` o en el POST al backend). abort() termina
        # el stream al instante sin importar en qué esté trabado el resto del
        # hilo, así el mic se libera apenas el usuario apaga el toggle.
        if stream is not None:
            try:
                stream.abort(ignore_errors=True)
            except Exception:
                logger.exception("no se pudo abortar el stream de audio")
        if thread is not None:
            thread.join(timeout=5)

    # ----------------------------------------------------------------- interno

    def _load_models(self) -> None:
        if self._require_wake_word and self._oww is None:
            from openwakeword.model import Model

            # Modelo custom entrenado para el acento rioplatense de Damian (ver
            # scratchpad de la sesión que lo generó) -- reemplaza al "hey_jarvis"
            # preentrenado en inglés que traía openwakeword, que dejaba su voz real
            # en el rango 0.006-0.365 de score (demasiado inconsistente para un
            # umbral fijo). openwakeword deriva el nombre de la clave del score del
            # nombre de archivo, así que "models/hey_jarvis.onnx" sigue resolviendo
            # a la misma clave "hey_jarvis" usada más abajo en este archivo.
            custom_model_path = str(Path(__file__).parent / "models" / "hey_jarvis.onnx")
            self._oww = Model(wakeword_models=[custom_model_path], inference_framework="onnx")
        if self._vad is None:
            from openwakeword.vad import VAD

            self._vad = VAD()
        if self._whisper is None:
            from faster_whisper import WhisperModel

            # "medium" en vez de "small": el small alucinaba/degradaba al final de
            # frases con audio no ideal (mic de escritorio, sin cancelación de
            # ruido) -- confirmado con transcripciones reales el 26/07 ("busca algo
            # sobre si ves seguridad" como continuación inventada de un comando
            # real). Más lento en CPU, pero para un comando corto es aceptable.
            self._whisper = WhisperModel("medium", device="cpu", compute_type="int8")

    def _run(self) -> None:
        try:
            self._load_models()
        except Exception as exc:
            logger.exception("no se pudieron cargar los modelos de voz")
            self._on_event("error", f"No se pudieron cargar los modelos de voz: {exc}")
            return

        audio_q: queue.Queue[np.ndarray] = queue.Queue(maxsize=200)

        def _callback(indata, frames, time_info, status):
            # Medio-duplex: mientras Raphael habla, ignoramos el mic (no capturamos
            # su propia voz por los parlantes). También evita el "input overflow"
            # que se dispara cuando el loop está bloqueado reproduciendo el TTS.
            if self._speaking:
                return
            if status:
                logger.warning("estado del stream de audio: %s", status)
            try:
                audio_q.put_nowait(indata[:, 0].copy())
            except queue.Full:
                # Preferimos tirar un frame viejo a bloquear el callback de audio.
                try:
                    audio_q.get_nowait()
                    audio_q.put_nowait(indata[:, 0].copy())
                except queue.Empty:
                    pass

        pre_roll_frames = max(1, int(PRE_ROLL_SECONDS * SAMPLE_RATE / FRAME_SAMPLES))
        recent_frames: list[np.ndarray] = []

        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=FRAME_SAMPLES,
            callback=_callback,
        )
        self._stream = stream
        try:
            with stream:
                if self._require_wake_word:
                    self._oww.reset()
                while not self._stop.is_set():
                    if self._require_wake_word:
                        try:
                            frame = audio_q.get(timeout=0.5)
                        except queue.Empty:
                            continue

                        recent_frames.append(frame)
                        if len(recent_frames) > pre_roll_frames:
                            recent_frames.pop(0)

                        score = self._oww.predict(frame)["hey_jarvis"]
                        if score < WAKE_THRESHOLD:
                            continue
                        logger.info("wake word detectada (score=%.2f)", score)
                        self._on_event("wake", f"score={score:.2f}")
                        self._beep()
                        command_audio = self._record_command(audio_q, list(recent_frames))
                        recent_frames.clear()
                        # Resetear el buffer interno de openwakeword para que el
                        # audio del comando no re-dispare la wake word.
                        self._oww.reset()
                    else:
                        # Sin wake word: el toggle ya es la señal de "escuchame".
                        # Se espera directo al habla (VAD) y se repite en loop
                        # mientras el toggle siga prendido -- cada silencio sin
                        # habla simplemente reinicia la espera, sin avisar nada
                        # (es la ausencia esperada de comando, no un error).
                        command_audio = self._record_command(audio_q, [], silent_ok=True)
                    if command_audio is not None:
                        spoke = self._transcribe_and_send(command_audio)
                        # Sacar cualquier resto de la propia voz de Raphael que haya
                        # entrado a la cola, para no re-transcribirla (refuerza el
                        # medio-duplex del callback).
                        self._drain_queue(audio_q)
                        # Modo conversación (solo en el modo con wake word): tras
                        # responder, seguir la charla sin exigir "hey jarvis" otra vez.
                        if spoke and CONVERSATION_FOLLOWUP and self._require_wake_word:
                            self._conversation_followups(audio_q)
                            self._oww.reset()
        except Exception as exc:
            logger.exception("loop de voz caído")
            self._on_event("error", f"Escucha de voz caída: {exc}")
        finally:
            self._stream = None

    def _record_command(
        self,
        audio_q: queue.Queue,
        pre_roll: list[np.ndarray],
        silent_ok: bool = False,
        initial_wait_seconds: float | None = None,
    ):
        """Acumula audio hasta detectar SILENCE_SECONDS_TO_STOP de silencio
        (Silero VAD) o llegar al tope duro. Devuelve float32 mono o None si no
        se grabó nada con voz.

        `initial_wait_seconds`: si se pasa y no se escucha que empiece a hablar en
        ese tiempo, devuelve None (para el modo conversación: no quedarse esperando
        un seguimiento que no llega)."""
        self._vad.reset_states()
        frames: list[np.ndarray] = list(pre_roll)
        silence_frames_needed = int(SILENCE_SECONDS_TO_STOP * SAMPLE_RATE / FRAME_SAMPLES)
        max_frames = int(MAX_COMMAND_SECONDS * SAMPLE_RATE / FRAME_SAMPLES)
        silent_streak = 0
        heard_speech = False
        started = time.monotonic()
        deadline = started + MAX_COMMAND_SECONDS + 3

        while not self._stop.is_set() and time.monotonic() < deadline:
            try:
                frame = audio_q.get(timeout=0.5)
            except queue.Empty:
                if (
                    not heard_speech
                    and initial_wait_seconds is not None
                    and (time.monotonic() - started) > initial_wait_seconds
                ):
                    return None
                continue
            if (
                not heard_speech
                and initial_wait_seconds is not None
                and (time.monotonic() - started) > initial_wait_seconds
            ):
                return None
            frames.append(frame)
            if len(frames) >= max_frames:
                break

            speech_prob = float(self._vad.predict(frame))
            if speech_prob >= VAD_SPEECH_THRESHOLD:
                heard_speech = True
                silent_streak = 0
            else:
                silent_streak += 1
                if heard_speech and silent_streak >= silence_frames_needed:
                    break

        if not heard_speech:
            if not silent_ok:
                self._on_event("error", "Te escuché llamarme pero no escuché ningún comando.")
            return None
        audio = np.concatenate(frames).astype(np.float32) / 32768.0
        peak = float(np.abs(audio).max())
        # Piso de energía: si el pico es muy bajo, fue ruido/respiración, no un
        # comando. NO transcribir -- si no, al amplificarlo (abajo) Whisper alucina
        # una frase inventada sobre el ruido (el clásico "gracias por ver el video").
        if peak < 0.02:
            if not silent_ok:
                self._on_event("error", "No escuché nada claro (solo ruido).")
            return None
        # Normalización de pico para grabaciones débiles (mic lejos, voz baja):
        # Whisper degrada fuerte con señal por debajo de ~10% de escala. Solo se
        # amplifica si el pico es bajo -- audio ya fuerte queda como está.
        if peak < 0.3:
            audio = audio * (0.9 / peak)
        return audio

    def _transcribe_and_send(self, audio: np.ndarray) -> bool:
        """Transcribe, manda al backend, avisa la respuesta y la HABLA (si el TTS
        está disponible). Devuelve True si hubo una respuesta hablada/enviada."""
        self._save_debug_wav(audio)
        try:
            segments, info = self._whisper.transcribe(
                audio,
                language="es",
                task="transcribe",
                beam_size=5,
                # Anti-alucinación (2026-09-25): sin condicionar en texto previo
                # (corta los bucles de frases inventadas) y con umbral de "no-speech"
                # explícito para marcar los segmentos que en realidad son ruido.
                condition_on_previous_text=False,
                no_speech_threshold=0.6,
                # Desactivado: este es el VAD INTERNO de Whisper, distinto del
                # nuestro (Silero, en _record_command) que ya decide cuándo dejar
                # de grabar. Confirmado con datos reales el 26/07: en un caso
                # descartó el 61% de un audio de 11.6s como "silencio" y cortó la
                # transcripción a mitad de frase. El nuestro ya cubre el corte por
                # silencio; este solo sumaba un segundo recorte, más agresivo y
                # sin control nuestro, sobre audio que ya viene filtrado.
                vad_filter=False,
            )
            segments = list(segments)
            # Descartar segmentos que Whisper marca como probable NO-habla o con
            # confianza muy baja: son los que alucinan frases sobre ruido.
            kept = [
                s for s in segments
                if getattr(s, "no_speech_prob", 0.0) < 0.6
                and getattr(s, "avg_logprob", 0.0) > -1.0
            ]
            text = " ".join(seg.text.strip() for seg in kept).strip()
            logger.info(
                "transcripción: idioma=%s (prob=%.2f) segmentos=%d/%d texto=%r",
                info.language, info.language_probability, len(kept), len(segments), text,
            )
        except Exception as exc:
            logger.exception("transcripción falló")
            self._on_event("error", f"No pude transcribir el audio: {exc}")
            return False

        if not text:
            # Con silent_ok esto es lo normal (ruido filtrado); no lo tratamos como error.
            return False

        # Descartar las alucinaciones típicas de Whisper sobre ruido/silencio
        # ("gracias por ver el video", "suscríbete", subtítulos de amara, etc.).
        if _looks_like_hallucination(text):
            logger.info("transcripción descartada como alucinación de ruido: %r", text)
            return False

        self._on_event("transcript", text)
        try:
            resp = requests.post(
                config.CHAT_URL,
                json={"message": text, "conversation_id": "voice-pc"},
                headers={"Authorization": f"Bearer {config.API_KEY}"},
                timeout=config.CHAT_REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            reply = resp.json().get("reply", "")
            self._on_event("reply", reply)
            # Voz de salida: Raphael habla su respuesta (bloqueante mientras suena).
            # Best-effort: si el TTS no está listo, no pasa nada, sigue en texto.
            if tts is not None and reply:
                self._speaking = True  # medio-duplex: el mic se ignora mientras habla
                try:
                    tts.speak(reply)
                except Exception:  # noqa: BLE001
                    logger.exception("el TTS falló al hablar la respuesta")
                finally:
                    # Colita: esperar un toque a que se apague el eco de los
                    # parlantes antes de volver a escuchar.
                    time.sleep(0.25)
                    self._speaking = False
            return True
        except requests.RequestException as exc:
            logger.exception("el backend no respondió al comando de voz")
            self._on_event("error", f"El backend no respondió: {exc}")
            return False

    def _conversation_followups(self, audio_q: queue.Queue) -> None:
        """Modo charla manos-libres: después de que Raphael respondió (y habló),
        queda escuchando un seguimiento SIN pedir "hey jarvis". Sigue mientras
        vos sigas hablando; si te quedás callado FOLLOWUP_WAIT_SECONDS, corta y
        se vuelve a esperar el wake word."""
        while not self._stop.is_set():
            # Sacar de la cola el audio que entró mientras Raphael HABLABA (su
            # propia voz por los parlantes), así no se transcribe a sí mismo.
            self._drain_queue(audio_q)
            follow = self._record_command(
                audio_q, [], silent_ok=True, initial_wait_seconds=FOLLOWUP_WAIT_SECONDS
            )
            if follow is None:
                return  # silencio: fin de la seguidilla, volver a esperar wake word
            self._on_event("wake", "seguimiento")
            spoke = self._transcribe_and_send(follow)
            if not spoke:
                return

    @staticmethod
    def _drain_queue(audio_q: queue.Queue) -> None:
        """Vacía la cola de audio (descarta lo capturado mientras Raphael hablaba,
        para no re-transcribir su propia voz -- mitigación simple de eco)."""
        try:
            while True:
                audio_q.get_nowait()
        except queue.Empty:
            pass

    @staticmethod
    def _save_debug_wav(audio: np.ndarray) -> None:
        """Guarda el audio que se le manda a Whisper -- para poder diagnosticar
        transcripciones raras (corte prematuro, idioma, calidad) reproduciendo
        offline contra el mismo audio, sin depender de que el usuario repita el
        intento. Se pisa solo cuando el disco se llena manualmente; no hay
        limpieza automática todavía (herramienta de diagnóstico, no una feature)."""
        try:
            debug_dir = Path(__file__).parent / "voice_debug"
            debug_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = debug_dir / f"command_{timestamp}.wav"
            pcm16 = np.clip(audio * 32768.0, -32768, 32767).astype(np.int16)
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(SAMPLE_RATE)
                w.writeframes(pcm16.tobytes())
        except Exception:
            logger.exception("no se pudo guardar el wav de debug")

    @staticmethod
    def _beep() -> None:
        try:
            import winsound

            winsound.Beep(880, 150)
        except Exception:
            pass  # sin beep no se corta el flujo; es solo feedback
