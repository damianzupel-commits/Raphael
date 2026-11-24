# SPEC — Raphael por voz (operación manos-libres)

> Documento de diseño. Creado el 2026-09-25. Objetivo: que Damian pueda **operar
> todas las capacidades de Raphael solo hablando** — manos-libres, en formato de
> charla, con ventanas interactivas que se arman según la tarea, confirmaciones
> habladas para lo irreversible, y resúmenes por voz dejando lo pesado en archivos
> ordenados.
>
> Alinea con: `CLAUDE.md` (arquitectura, gates), `voice_listener.py` (entrada de voz
> ya existente), `HACIA-RAPHAEL.md` (visión "Gran Sabio"). Regla del doc: donde algo
> no existe, se dice **FALTA** sin maquillar.
>
> **Encuadre:** esto es capacidad de **asistente personal** (el "lab"), no el producto
> Raphael Auditor. Es la parte más "Jarvis" del proyecto.

---

## 1. La visión (lo que pidió Damian)

1. **Todas las capacidades por voz**, en formato de charla (no solo dictar: darle
   órdenes de acción — auditar, correr la brigada, controlar la PC, etc.).
2. **Manos-libres**: "hey jarvis" → hablás → responde hablando → seguís sin tocar nada.
3. **Mira la pantalla** + quiere que Raphael **cree ventanas interactivas** según lo
   que estén haciendo.
4. **Confirmación hablada** antes de algo importante/irreversible.
5. **Resumen por voz**, dejando lo pesado en un **archivo bien ordenado**.

## 2. Qué ya existe (el cimiento)

- **Entrada de voz (`tray-app/voice_listener.py`):** pipeline 100% local
  mic → openWakeWord "hey jarvis" → Silero VAD → faster-whisper (`small`, es) →
  `POST /api/chat`. Ya funciona y ya puede disparar CUALQUIER tool (el endpoint es
  el agente completo). **→ "todo por voz" ya es casi posible; falta la voz de vuelta.**
- **Gates de seguridad:** dry-run→confirm, `authorized_targets.yaml`, `proposal_id`,
  `preview_token`. Base para las confirmaciones habladas (Fase 2).
- **Tools de archivo** (`fs_write_file`, etc.) y la convención de carpetas ordenadas
  que ya usamos. Base para el "detalle a archivo" (Fase 3).
- **QtWebEngine** ya embebido (`ui/graph_view.py`, `web_assets/`). Base técnica para
  las ventanas interactivas HTML (Fase 4).

## 3. Decisiones de diseño

- **TTS: Piper (local, offline, gratis).** Fiel a la filosofía 100% local del resto.
  Alternativa evaluada: edge-tts (mejor voz, pero necesita internet). Elegido Piper;
  edge-tts queda como opción configurable a futuro.
- **Voz:** español, neutra. Modelo Piper a elegir escuchando (afinado con Damian).
- **La especialización es por I/O, no por cerebro:** el mismo agente (DeepSeek/local)
  maneja todo; la voz es solo la capa de entrada/salida.

---

## 4. Fases (una a la vez — regla "un ladrillo por vez")

### Fase 1 — Voz de salida + loop manos-libres  *(≈60% de la visión)*
- **TTS con Piper:** sintetizar la respuesta del agente y reproducirla (la tray-app
  ya tiene el stack de audio: sounddevice/numpy).
- **Cerrar el loop:** después de hablar, **re-armar la escucha** automáticamente para
  seguir la charla sin tocar nada. (Opcional: modo "conversación" que no exige repetir
  el wake word por N segundos tras responder.)
- **Barge-in (deseable):** poder interrumpir a Raphael hablándole encima. FALTA,
  puede quedar para una iteración posterior.
- **Resultado:** ya operás cualquier capacidad hablando y te contesta por voz.

### Fase 2 — Confirmaciones habladas
- Antes de una acción irreversible/peligrosa (shell destructivo, control de PC,
  pentest, submit de formularios), Raphael **dice en voz alta qué va a hacer y espera
  un "sí" hablado** antes de ejecutar.
- Se apoya en los gates existentes (dry-run→confirm, `proposal_id`, `preview_token`):
  el flujo de confirmación ya existe a nivel código; esto lo enruta por voz.
- **Regla de seguridad:** ante duda o transcripción ambigua, NO ejecuta. El default
  siempre es no actuar.

### Fase 3 — Resumen hablado + detalle a archivo
- Para resultados largos (informe de auditoría, listados), Raphael **lee un resumen
  corto** y **guarda el detalle en una carpeta ordenada** (misma convención mise en
  place que ya usamos), diciendo dónde lo dejó.
- Es sobre todo prompt/convención + las tools de archivo que ya están.

### Fase 4 — Ventanas interactivas dinámicas  *(la ambiciosa, R&D)*
- Raphael **genera un panel según la tarea** y lo muestra en un **webview** de la
  tray-app (HTML generado, como los mockups/artefactos). Ej.: mientras audita, un
  panel con las estaciones en vivo; mientras charla de un tema, una tarjeta con lo
  relevante.
- Arquitectura probable: el agente devuelve, además del texto, un **bloque HTML** que
  la tray-app renderiza en un panel WebEngine adaptativo.
- **FALTA** casi todo; es investigación. Va al final, después de que 1–3 funcionen.

---

## 5. Riesgos y honestidades

- **Se codea "a ciegas":** desde el entorno de asistencia no se oye el audio ni se ve
  el render de Qt. Cada fase se afina con Damian escuchando/mirando y reportando.
- **Multi-sesión:** no sale en una tarde. Se avanza fase por fase.
- **Seguridad por voz:** la voz hace más fácil disparar acciones por error (mala
  transcripción). Por eso la Fase 2 (confirmaciones) es innegociable antes de exponer
  acciones irreversibles al flujo de voz. Mientras tanto, el modo voz puede limitarse
  a capacidades no destructivas.
- **Latencia:** Whisper + agente + TTS suma tiempo. Aceptable para charla; medir y
  ajustar (modelo Piper liviano, streaming del TTS si hace falta).

## 6. Estado
- Fase 1: **FUNCIONANDO en vivo (2026-09-25).** Raphael habla sus respuestas y se
  opera por voz manos-libres, a gusto de Damian.
  - `tray-app/tts.py` (motor Piper, voz `es_ES-davefx-medium`, robusto a que falte
    el modelo; soporta API vieja y nueva de piper 1.x).
  - `tray-app/download_tts_voice.py` (baja voces en español).
  - `tray-app/voice_listener.py`: habla la respuesta + **medio-duplex** (el mic se
    apaga mientras habla → no se escucha a sí mismo) + modo conversación.
  - VAD afinado a la forma de hablar de Damian: `SILENCE_SECONDS_TO_STOP=2.5`,
    `VAD_SPEECH_THRESHOLD=0.25`, `MAX_COMMAND_SECONDS=20`.
  - `piper-tts` instalado en el venv de la tray-app. Voz en `models/tts/`.
  - Aprendizajes: whisper `medium` tarda ~20s en cargar (esperar antes de hablar);
    el botón 🎙 escucha directo (sin "hey jarvis"); con parlantes puede haber algo de
    eco (auriculares = 0 eco). Diagnóstico: `tray-app/test_voice.py`.
  - Pendiente menor: retoques estéticos (a pedido de Damian).
- Fases 2–4: diseñadas, pendientes.

## 7. Próximo paso
Arrancar **Fase 1**: integrar Piper (TTS) + reproducción + re-armado de la escucha en
`voice_listener.py` / la tray-app. Afinar la voz con Damian escuchando.
