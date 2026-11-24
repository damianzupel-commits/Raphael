"""Test directo del VoiceListener (diagnóstico de la entrada de voz).

Corre el MISMO listener que usa la app, en modo sin wake word (hablás directo),
por 30 segundos, e imprime cada evento en la consola. Sirve para ver si el
problema es el listener en sí o la integración con la ventana.

Uso (desde tray-app, con el python del venv):
    .venv\\Scripts\\python.exe test_voice.py

Después de que diga "LISTO, HABLÁ AHORA", decí algo tipo "hola, probando el
microfono". Debería imprimir [transcript] con tu texto (y [reply] si el backend
está levantado).
"""

import logging
import sys
import time

# Mostrar TODO en consola, para ver errores de carga de modelos / stream.
logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from voice_listener import VoiceListener  # noqa: E402


def on_event(kind, text):
    print(f">>> EVENTO [{kind}]: {text}", flush=True)


def main():
    print("Cargando modelos (whisper 'medium' tarda; esperá el 'LISTO')...", flush=True)
    vl = VoiceListener(on_event=on_event, require_wake_word=False)
    vl.start()
    # Dar tiempo a que carguen los modelos antes de avisar.
    time.sleep(20)
    print("\n=== LISTO, HABLÁ AHORA (tenés ~30 segundos) ===\n", flush=True)
    time.sleep(30)
    print("\n=== Fin. Apagando. ===", flush=True)
    vl.stop()


if __name__ == "__main__":
    main()
