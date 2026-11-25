# Trading · b-codigo
Brigada Trading para el harness v2 (paquete `raphael_trading`, `src/`). `manifest.yaml` (y su copia dentro del paquete, que un test obliga a mantener idéntica) es la única fuente de verdad de acciones y niveles.

## Qué tiene
- `engine.py`, `signals.py`, `backtest.py`: el método Smart Money (IFVG) portado de JarvisRemote, sin dependencias.
- `data.py`: adaptadores de datos: `simulado` (por defecto), `csv`, `ibkr` (el elegido) y `oanda` (solo lectura, descartado).
- `ibkr.py`: conexión a TWS/IB Gateway con `ib_async` (opcional) en un hilo propio; solo cuenta paper salvo `TRADING_ALLOW_LIVE=1`.
- `broker.py`: `SimulatedBroker` (por defecto), `IbkrBroker` (mercado + stop + objetivo colgados) y `OandaBroker` (v20, cuenta `practice`; la `live` pide además `TRADING_ALLOW_LIVE=1`). Para sumar otro broker: una clase con `place/positions/close` y su rama en `make_broker`.
- `cooks/`: `signals` (analiza), `backtest` (prueba), `engine-watch` (vigila, avisa y ejecuta SOLO lo aprobado).
- `config.py`: config validada (riesgo, datos, broker, vigilancia). `health.py`: salud y validación al montar.

## Reglas de código
- `ejecutar_orden` y `cerrar_posicion` son `aprobacion` + `spend` + `irreversible`. El broker solo se toca desde `execute`, que además revalida señal vigente, tope de riesgo (aunque Damián edite el tamaño al aprobar), tope diario, pausa y que el nivel no esté en automático.
- Sin clave cada adaptador real cae al simulado y lo dice (`estado`, salud, y marca `simulated` en señales y órdenes). Nunca inventa datos de mercado.
- Las claves salen de variables de entorno (`.env.plantilla`); nunca van al repo ni a un log.
- Solo edición personal (corre en la PC de Damián). En la nube no monta.

## Probar
`cd ../c-salud/pruebas && python -m pytest -q` y `ruff check . ../../b-codigo/src/raphael_trading`.
