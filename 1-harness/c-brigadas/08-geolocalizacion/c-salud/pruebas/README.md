# Geolocalización · pruebas
88 tests, sin red: fuentes (parseo con transporte simulado, claves que faltan, transporte real con `urlopen` falso), validación, cocineros montados en el harness real, salud y puerta (contrato, imports, acciones declaradas, ninguna clave en el código).
- `pyproject.toml`: pytest arranca desde acá; ruff hereda la configuración de `../../b-codigo/pyproject.toml`.
- `conftest.py` pone `b-codigo/src` y el harness en el camino; `kit.py` arma el sistema de prueba (modo simulado).
Correr solo esta suite: `python -m pytest` desde esta carpeta (para la puerta: pendiente que el coordinador sume la suite `geolocalizacion` a `gate.py`).
