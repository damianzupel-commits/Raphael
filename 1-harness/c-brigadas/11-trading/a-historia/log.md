# Registro · 11-trading · Trading

Una entrada por sesión: fecha y "Resumen de cierre" de 3 a 6 líneas (qué se hizo, qué quedó, qué se decidió).

## 25 nov 2026 · Resumen de cierre (hilo "Construir pieza 11 Trading")
- Se portó la brigada al harness v2: motor/señales/backtest de JarvisRemote, tres cocineros (`signals`, `backtest`, `engine-watch`), `manifest.yaml`, config validada, health y `.env.plantilla`. 48 tests y ruff en verde; suite de contrato en verde (personal; en la nube no monta, a propósito).
- Todo corre contra adaptadores simulados (datos y broker). Hay adaptador real de OANDA (probado con transporte falso, no contra OANDA real). Sin clave cae al simulado y avisa.
- Nada se ejecuta sin aprobación de Damián, ni en demo: `ejecutar_orden` y `cerrar_posicion` son `aprobacion`+`spend`+`irreversible`; `execute` revalida y se niega si alguien las pone en automático.
- Brokers: propuesta en `a-historia/brokers.md`. OANDA parece NO aceptar Argentina (su página oficial); IBKR sí figura. Decide Damián; falta escribir el adaptador del elegido.
- Pendiente para el harness: exponer el nivel vigente en `Context` (hoy `engine-watch` lee `ctx._rt.policy`). Pendiente para el coordinador: sumar la suite `trading` a `gate.py`, ESTADO y `LIENZO-DAMIAN.md`.
