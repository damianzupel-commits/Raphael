# Seguridad · pruebas
62 tests: `test_gate` (suite de contrato en personal y nube, imports, acciones con nivel, pentest fuera de la nube), `test_audit`, `test_guardrail`, `test_pentest`, `test_defensive` y `test_cooks`. Corren sin red, sin claves y con adaptadores simulados.
`python -m pytest -q` desde esta carpeta (el `conftest.py` arma las rutas al core).
