# Voz LOCAL del orquestador

Hablarle a Raphael y que responda hablando, **todo en esta PC** (sin nube, sin mandar audio ni texto a ningún lado).

- **STT (entrada):** botón 🎙 junto al input de cada pestaña → graba tu voz → `POST /api/voz/transcribir` → **faster-whisper** local →
  el texto entra en el input (lo revisás y apretás Enviar).
- **TTS (salida):** chip **«🔊 Leer respuestas: ON/OFF»** en la cabecera → cuando está activo, cada respuesta de una brigada se
  sintetiza con **Piper** (voz **es_AR-daniela-high**) vía `POST /api/voz/hablar` y se reproduce en la ventana. La preferencia se
  guarda en el navegador.

## Qué se reutilizó del prototipo viejo (`cerebro-fenix/_Jarvis-Local`)

| Pieza | De dónde |
|---|---|
| Voz Piper es-AR | `_Jarvis-Local/voices/es_AR-daniela-high.onnx` (+ `.onnx.json`, 114 MB). **Copiada** a `backend/data/voices/` (gitignoreada) para no depender del prototipo |
| Librerías `faster-whisper 1.2.1` y `piper-tts 1.5.0` | el venv del prototipo (Python 3.12, el mismo que el backend). El orquestador lo usa **si el venv del backend no las tiene** |
| Modelos Whisper `small` y `medium` | caché de Hugging Face del usuario (`~/.cache/huggingface/hub/models--Systran--faster-whisper-*`), usados **offline** |
| Patrón de síntesis (`SynthesisConfig(length_scale)`, WAV en memoria) | `tts.py` del prototipo |

No se reutilizó el VAD ni el push-to-talk del prototipo (usaban `sounddevice`/`keyboard` en el escritorio): acá el micrófono lo maneja el
navegador (`MediaRecorder`), así que no hace falta nada de eso.

## Cómo está armado

```
ventana (ui.html) ── /api/voz, /api/voz/transcribir, /api/voz/hablar ──> orquestador/server.py
                                                                          └─ voice/engine.py ──(JSON por stdin/stdout)──> voice/worker.py
                                                                                                                        ├─ faster-whisper (STT)
                                                                                                                        └─ Piper (TTS)
```

- `voice/worker.py` corre como **subproceso persistente** (los modelos quedan calientes) con el intérprete que tenga las librerías, **sin red**
  (`HF_HUB_OFFLINE=1`, `local_files_only`). Así el orquestador liviano no carga ctranslate2/onnxruntime (hay un test que lo garantiza).
- **No usa la GPU por default** (`VOICE_STT_DEVICE=cpu`, `int8`): Whisper `small` transcribe unos segundos de audio en ~2 s en CPU.
- Antes de sintetizar, el texto se **limpia para que se pueda leer** (sin markdown, código, tablas, URLs ni `[[wikilinks]]`) y se corta en ~1200
  caracteres en un límite de oración.
- Si algo falta, `GET /api/voz` lo dice con el motivo exacto y la UI deshabilita el botón / el chip (con un tooltip); el resto del orquestador
  no se entera. Un fallo del motor devuelve 503 con un mensaje claro y el worker se relanza en el pedido siguiente.

## Qué intérprete usa el worker (en orden)

1. `VOICE_PYTHON` (si apunta a un archivo que existe).
2. El Python del backend, si ya tiene `faster_whisper` y `piper`.
3. El venv del prototipo: `~/cerebro-fenix/_Jarvis-Local/venv/Scripts/python.exe`.

**Camino limpio (recomendado)** para no depender del prototipo: `pip install -r backend/requirements-voice.txt` en el venv del backend.

## Configuración (`backend/.env`, todo opcional; ver `.env.example`)

`VOICE_ENABLED` (1; `0` apaga todo) · `VOICE_PYTHON` · `VOICE_STT_MODEL` (`small` | `medium`) · `VOICE_STT_DEVICE` (`cpu` | `cuda`) ·
`VOICE_STT_COMPUTE` · `VOICE_STT_LANG` (`es`) · `VOICE_PIPER_VOICE` (ruta al `.onnx`) · `VOICE_TTS_SPEED`.

## Qué falta instalar si lo movés a otra PC

- `pip install -r backend/requirements-voice.txt` (faster-whisper 1.2.1 + piper-tts 1.5.0).
- El modelo Whisper una vez (con internet): Hugging Face `Systran/faster-whisper-small` (o `-medium`).
- La voz es-AR: Hugging Face `rhasspy/piper-voices` → `es/es_AR/daniela/high/` (`es_AR-daniela-high.onnx` y `.onnx.json`) en `backend/data/voices/`.

## Límites

- Dictado: Whisper `small` se equivoca en detalles (en una prueba "tengo" salió "tembo"); `VOICE_STT_MODEL=medium` mejora la precisión y es ~3x más lento en CPU.
- El micrófono lo pide el navegador: la primera vez hay que darle permiso a la ventana (el panel de navegador de Claude lo bloquea; la ventana app de Edge no).
- La lectura es por respuesta completa (no en streaming): una respuesta larga tarda unos segundos en empezar a sonar.
- No hay "manos libres" (VAD / palabra de activación): el dictado es con el botón.
