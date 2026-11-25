# Operaciones · monitoreo
- **Healthcheck** (`health.py`, al montar y cada 5 min): da mal solo por config inválida o un interruptor real prendido sin su librería. En modo simulado da bien y lo dice ("no toca la PC ni el celular").
- **Estado:** comando `estado` del cocinero `supervisor` (modo, adaptadores, interruptores, celular conectado, carpetas, supervisor, si hay IA para el jefe).
- **Registro:** comando `registro` (últimas acciones: herramienta, si salió bien, argumentos sin secretos ni texto tipeado). Queda en el espacio `operaciones`, colección `registro`, tope 500.
- **Alertas:** si el jefe cae (5 errores seguidos) o la salud da mal 3 veces, el harness lo avisa al orquestador.
