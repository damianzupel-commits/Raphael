# Trading · pruebas
48 tests, sin red (velas sintéticas, broker simulado y transporte HTTP falso para OANDA).
- `test_contrato.py`: suite de contrato del harness, manifiestos idénticos, ningún import ajeno, acciones declaradas, nada con efecto sin su nivel.
- `test_motor.py`: motor, señales, riesgo, backtest, adaptadores de datos.
- `test_flujo.py`: escanear → señal → aviso → proponer → aprobación → orden; vencimiento, tope de riesgo, tope diario, pausa, nivel automático bloqueado, adaptadores de broker.
Correr: `python -m pytest -q` desde esta carpeta. Falta sumarla a `3-mando/b-herramientas/gate.py` (lo hace el coordinador).
