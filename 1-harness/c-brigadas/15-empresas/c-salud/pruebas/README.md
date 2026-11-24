# Raphael Empresas · pruebas
Los 124 tests de la brigada (atención, agenda, cobros, encargos, avisos, tienda, secretaria, ruteo, instalación, puerta y suite de contrato).
- `pyproject.toml`: pytest arranca desde acá; ruff hereda la configuración de `../../b-codigo/pyproject.toml`.
- `conftest.py` pone en el camino `b-codigo/src`, el harness (`1-harness/b-codigo/src`) y el orquestador; `kit.py` arma un sistema de prueba completo.
Correr solo esta suite: `3-mando\b-herramientas\gate.bat --solo business`.
