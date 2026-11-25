# Interactive Brokers: lo que tiene que hacer Damián (y qué probar después)

1. Abrir la cuenta en Interactive Brokers (Argentina figura en su lista oficial). No hace falta fondearla para la demo.
2. Desde el portal de la cuenta, pedir la **cuenta paper** (demo); anotar su usuario paper y el número (empieza con `DU`).
3. Instalar **IB Gateway** (más liviano) o TWS, abrirlo con el usuario paper, y en *Configuración > API*: activar "Enable ActiveX and Socket Clients", dejar "Read-Only API" **desactivado** (si no, no se pueden mandar órdenes), puerto 4002 (Gateway) o 7497 (TWS), y permitir 127.0.0.1.
4. En la PC: `pip install ib_async`; en la config de la brigada `data.adapter: ibkr` y `broker.adapter: ibkr`; variables en `.env.plantilla`.
5. Probar en este orden: `estado` (debe decir broker ibkr, no simulado) → `analizar` (fuente ibkr) → `escanear` → `proponer` → aprobar UNA orden chica → mirar en TWS que el stop y el objetivo quedaron colgados → `cerrar`.

Qué NO está probado: todo el trato con IB real. Se verificó solo contra un `ib_async` falso. Puntos a mirar en la primera prueba: tamaño mínimo de orden de forex en IDEALPRO (puede exigir más de lo que da el riesgo del 1 %), datos con retraso hasta fondear la cuenta, y que las velas coincidan con las del gráfico de TWS. IB Gateway se desconecta solo una vez al día: Raphael reconecta en el próximo pedido.
