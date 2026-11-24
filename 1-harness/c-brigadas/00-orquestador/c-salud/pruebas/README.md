# Orquestador · pruebas
Los 266 tests del orquestador (O1 a O5: voz, ruteo, turno, watchdog, plan y DAG, trabajo conjunto, Secretaria).
- `pyproject.toml`: pytest arranca desde acá; ruff hereda la configuración de `../../b-codigo/pyproject.toml`.
- `conftest.py` pone en el camino `b-codigo/src` y el harness (`1-harness/b-codigo/src`); `kit.py` arma un runtime de prueba.
Correr solo esta suite: `3-mando\b-herramientas\gate.bat --solo orchestrator`.
