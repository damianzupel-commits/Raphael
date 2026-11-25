Copia del 24 nov 2026 desde `nucleo/02-orquestador/codigo/raphael-orchestrator`. Hasta que se haga el traspaso (ver `raphael/README.md`), los chats siguen trabajando en el original.

## 25 nov 2026 · Portado del motor de voz hablada
`voice/engine.py` y `voice/worker.py` de JarvisRemote -> `speech.py` y `speech_worker.py`. Cambios: interfaz `Speech` con adaptador simulado y apagado; se sacó la ruta al prototipo viejo (`cerebro-fenix`) y la búsqueda de carpetas ajenas (la voz la indica `VOICE_PIPER_VOICE`); sin endpoints HTTP (eso es de la pieza 3). No portado: mission_control, ui.html, server.py y launcher (son de la pieza 3 o de la app).
