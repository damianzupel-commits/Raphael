# Ingesta · pruebas
73 tests, sin red, sin claves y sin modelo real (corren con los adaptadores simulados y transportes falsos). Se corren desde esta carpeta con `python -m pytest`.

- `test_gate.py`: suite de contrato del harness (personal y cloud), manifiestos idénticos, imports permitidos (ninguna brigada importa a otra), acciones declaradas ↔ usadas, y que nada no automático se ejecuta sin OK.
- `test_ingesta.py`: la brigada de punta a punta (pedido → nota con origen → sin duplicar; con y sin modelo; listas y cola; reintentos; vigilar; borrar; web, arXiv; comandos; desmontar).
- `test_unidades.py`: URLs públicas (SSRF), texto, resumen, vault, y los adaptadores reales con transportes falsos (arXiv, web con redirecciones, yt-dlp con 429).
- `kit.py` arma la instalación; `conftest.py` pone `src/` y el núcleo en el path.

**No cubierto:** los adaptadores reales contra la red de verdad (la nube no tiene salida) y un modelo real: eso lo prueba `../mantenimiento/probar_real.py` en la PC de Damián.
La suite falta sumarla a `3-mando/b-herramientas/gate.py` (lo hace el coordinador): `"ingesta": ROOT / "1-harness" / "c-brigadas" / "10-ingesta" / "c-salud" / "pruebas"`.
