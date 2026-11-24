# 🎙 Voz de Raphael — cómo probar las dos opciones

> Guía rápida (2026-09-25). La Fase 1 (que Raphael hable + manos-libres) ya funciona.
> Acá quedan listas las DOS opciones de voz para que elijas la que más te guste.
> Todos los comandos se corren desde `tray-app`, con el python del venv.

## Antes que nada: aplicar los retoques nuevos
Los cambios de hoy (que NO lea emojis, y que la esfera lata con la voz) toman efecto
al **reiniciar la tray-app** (bandeja → Salir → reabrir). El latido se ve en el
**orbe flotante** (tocá su mic 🎙 y hablá; en la ventana grande el orbe está oculto).

---

## Opción A — Piper "high" (local, offline, gratis)
Voz local de más calidad que la actual (que es "medium").

1. Borrá la voz actual para que tome la nueva:
   ```powershell
   del models\tts\es_ES-davefx-medium.onnx
   del models\tts\es_ES-davefx-medium.onnx.json
   ```
2. Bajá la voz "high" (español latino):
   ```powershell
   .venv\Scripts\python.exe download_tts_voice.py es_MX-claude-high
   ```
3. Reiniciá la tray-app. Listo, Raphael habla con la voz nueva.

(Para ver todas las voces: `.venv\Scripts\python.exe download_tts_voice.py --list`)

---

## Opción B — edge-tts (la más natural, acento argentino, necesita internet)
Voces neuronales de Microsoft. Suenan mucho más humanas. Usa internet.

1. Instalá el motor (una sola vez):
   ```powershell
   .venv\Scripts\python.exe -m pip install edge-tts
   ```
2. Lanzá la tray-app CON edge activado (sin cambios permanentes; solo para esta corrida).
   Cerrá primero la tray desde la bandeja, después:
   ```powershell
   $env:TTS_ENGINE="edge"; .venv\Scripts\pythonw.exe tray.py
   ```
3. Hablale al orbe. Va a usar la voz **es-AR-TomasNeural** (rioplatense, masculina).

Otras voces AR para probar (cambiá el valor):
```powershell
$env:TTS_ENGINE="edge"; $env:TTS_EDGE_VOICE="es-AR-ElenaNeural"; .venv\Scripts\pythonw.exe tray.py
```
(Tomas = masculina, Elena = femenina.)

---

## Cómo volver a Piper (default)
Cerrá la tray y reabrila normal (con el acceso directo, sin setear `TTS_ENGINE`).
Vuelve solo a Piper con la voz que tengas en `models/tts/`.

## Notas
- Con **parlantes** puede haber algo de eco; con **auriculares**, cero.
- La primera vez que prendés el mic, esperá ~20s (carga el modelo de transcripción)
  antes de hablar.
