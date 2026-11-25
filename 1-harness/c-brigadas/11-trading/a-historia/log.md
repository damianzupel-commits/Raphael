# Registro · 11-trading · Trading

Una entrada por sesión: fecha y "Resumen de cierre" de 3 a 6 líneas (qué se hizo, qué quedó, qué se decidió).

## 25 nov 2026 · Resumen de cierre (hilo "Construir pieza 11 Trading")
- Se portó la brigada al harness v2: motor/señales/backtest de JarvisRemote, tres cocineros (`signals`, `backtest`, `engine-watch`), `manifest.yaml`, config validada, health y `.env.plantilla`. 48 tests y ruff en verde; suite de contrato en verde (personal; en la nube no monta, a propósito).
- Todo corre contra adaptadores simulados (datos y broker). Hay adaptador real de OANDA (probado con transporte falso, no contra OANDA real). Sin clave cae al simulado y avisa.
- Nada se ejecuta sin aprobación de Damián, ni en demo: `ejecutar_orden` y `cerrar_posicion` son `aprobacion`+`spend`+`irreversible`; `execute` revalida y se niega si alguien las pone en automático.
- Brokers: propuesta en `a-historia/brokers.md`. OANDA parece NO aceptar Argentina (su página oficial); IBKR sí figura. Decide Damián; falta escribir el adaptador del elegido.
- Pendiente para el harness: exponer el nivel vigente en `Context` (hoy `engine-watch` lee `ctx._rt.policy`). Pendiente para el coordinador: sumar la suite `trading` a `gate.py`, ESTADO y `LIENZO-DAMIAN.md`.

## 25 nov 2026 · Resumen de cierre (IBKR)
- Damián eligió Interactive Brokers. Se escribió `ibkr.py` + `IbkrBroker` (orden a mercado con stop y objetivo colgados, posiciones, cierre) y lectura de velas, contra TWS/IB Gateway con `ib_async` (opcional). Se niega si la sesión trae una cuenta que no es paper (`DU`); la real exige `TRADING_ALLOW_LIVE=1`.
- 59 tests y ruff en verde, con un `ib_async` falso. **No probado contra un IB real** (no hay cuenta aún): pasos y puntos a mirar en `ibkr-pasos.md`.
- Sin `ib_async` o sin TWS abierto, datos y broker caen al simulado y lo avisan; una orden sin conexión da error claro, nunca cae a simulado en silencio.

## 2026-11-25 · hilo "Dar jefe a las 9 brigadas restantes"
**Resumen de cierre.** Trading ahora tiene jefe con dos efímeros (Analista, Cartera), así que el orquestador le puede derivar pedidos. Seis tools nuevas (`trading_*`, registradas en `validate`), todas de solo lectura o análisis. La regla de Damián se mantiene: ejecutar una orden y cerrar una posición NO son tools ni se pueden pedir desde el jefe; siguen siendo las acciones con aprobación (`spend`, `irreversible`, también en demo) que pide el cocinero `engine-watch` con `proponer` o `cerrar`. Un test lo verifica (ninguna tool con nombre de operar, todas en automático porque solo leen, y un efímero que intenta `ejecutar_orden` choca con su caja y no queda ni una orden). Límite: la lista de instrumentos vigilados que se agrega a mano vive en el espacio propio de `engine-watch` y una tool no la ve (se ven los de la config). Datos de mercado y análisis: no son privados. 65 tests, ruff limpio.
