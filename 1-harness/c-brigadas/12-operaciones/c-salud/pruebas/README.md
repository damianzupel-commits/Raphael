# Operaciones · pruebas
96 tests, todos con adaptadores simulados y sin red (el shell real corre procesos locales y el web real un servidor en 127.0.0.1).
- `test_contrato.py`: la suite de contrato del harness v2 y el montaje.
- `test_config_guardarrailes.py`: config, patrones destructivos, sandbox, modos y anti auto-escalada.
- `test_adaptadores.py`: shell real (mata lo colgado), enlace del celular, web (guarda de red, deny-list, caché, redirecciones), credenciales, simulados.
- `test_brigada.py`: la brigada montada: tools por la compuerta (pendiente → aprobar → ejecuta), modelo solo local, reglas solo para Damián, comandos, supervisor, interruptores del modo real, imports.
Correr: `python -m pytest` desde esta carpeta (usa el `src/` sin instalar). Está sumada a la puerta como `operaciones`.
