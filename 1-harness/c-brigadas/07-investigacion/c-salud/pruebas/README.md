# Investigación · pruebas
68 tests con la brigada montada de verdad (cargador, manifiesto, runtime del harness), sin red ni claves. Correr: `python -m pytest -q` desde acá.
- `test_contrato.py`: suite de contrato (personal y nube) y manifiestos iguales.
- `test_forense.py`: casos, ingesta (WhatsApp, Telegram, CSV, logs, texto), entidades, fusiones, retractar, registro, informe.
- `test_busqueda.py`: Brave y SearXNG con transporte simulado, cadena, citas, verificación, lectura segura de páginas.
- `test_tendencias.py`, `test_ideas.py`: vigilancia, puntaje, spec, sandbox.
- `test_brigada.py`: comandos, acciones con su nivel, aprobación, tick, nube, modelo local y jefe.
