# 04-cuentas-y-apis · Cuentas y APIs

Pieza 4 del proyecto Raphael. Una sola lista de todas las cuentas y APIs externas (qué hace falta, dónde se saca, dónde se pega, qué se prueba), con un chequeo de lo cargado y una verificación en vivo de solo lectura. **No abre cuentas y nunca recibe claves**: las pegás vos en `raphael.env` (o en la pantalla `/config`).

## Uso (desde la carpeta `raphael`)
```
2-entrega\c-despliegue\cuentas-y-apis\cuentas.bat chequear --env .data\empresas\raphael.env
2-entrega\c-despliegue\cuentas-y-apis\cuentas.bat probar --env .data\empresas\raphael.env          # pedidos de solo lectura
2-entrega\c-despliegue\cuentas-y-apis\cuentas.bat probar --simulado                                 # sin red
```
- `chequear`: por cuenta, lista / parcial / falta, mostrando solo "cargada" y los últimos 4 de lo secreto. Código 2 si hay un error de formato; con `--estricto`, también si falta algo requerido. `--edicion personal|empresas` filtra.
- `probar [ids]`: un GET de solo lectura por cuenta (nunca manda mensajes, cobra ni cambia nada). Con `--simulado` usa el adaptador simulado y no sale a la red.
- `plantilla` / `lienzo`: imprimen `cuentas.env.plantilla` y `ENTRADAS-LIENZO.md`, generados desde el catálogo (un test avisa si se desfasan).

## Carpetas
- `codigo/src/raphael_cuentas/`: `catalogo.py` (la lista), `entorno.py` (lectura y chequeo), `adaptadores.py` (real y simulado), `plantilla.py`, `lienzo.py`, CLI. Solo biblioteca estándar; no importa ninguna otra pieza (un test lo verifica).
- `tests/`: 22 tests, todos con el adaptador simulado o un abridor falso: no usan red ni claves.
- `cuentas.env.plantilla`: todas las variables, vacías, para copiar. `ENTRADAS-LIENZO.md`: la tabla que el coordinador suma a `LIENZO-DAMIAN.md`.
- `SPEC.md`, `log.md`.

## Cuentas cubiertas
OpenRouter (Empresas) · NVIDIA (personal, no sensible) · modelo local Ollama/LM Studio (personal, sensible) · Meta webhook, WhatsApp e Instagram · Mercado Pago (real + simulado) · transferencia (datos de la cuenta) · Tailscale Funnel · DuckDNS · Hetzner (cuando haya pago) · tienda de la clienta · broker de Trading (pendiente, sin elegir).

## Reglas
- Sin claves en el repo ni en el chat. Sin clave, Raphael cae a reglas o a mock y lo avisa.
- Los endpoints de verificación son supuestos hasta probarlos con cuentas reales (están marcados en el catálogo).
- El conector real de Mercado Pago y el escalón `local` de modelos.yaml son de las piezas 15 y 1/2; acá solo se guardan y prueban las credenciales.
