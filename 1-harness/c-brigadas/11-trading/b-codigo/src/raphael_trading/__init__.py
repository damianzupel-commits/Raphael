"""Brigada Trading de Raphael personal (harness v2): señales, backtest y vigilancia de mercado.

Cocineros: señales (analiza y propone), backtest (prueba sobre histórico) y motor y vigilancia (watchlist, avisos y
ejecución). TODA ejecución, en demo o en real, la aprueba Damián: el cocinero la pide como acción `ejecutar_orden`
(nivel `aprobacion`, etiquetas `spend` e `irreversible`) y el broker solo se toca desde `execute`.
Todo lo que declara está en `manifest.yaml`. Solo importa `raphael_core` y la stdlib (más pydantic, httpx y yaml).
No es asesoramiento financiero.
"""

__version__ = "2.0.0"
