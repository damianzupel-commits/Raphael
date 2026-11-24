# raphael-empresas · Brigada Empresas (harness v2)

Lleva un negocio con la mínima necesidad de humanos, nunca cero: atiende clientes por WhatsApp e Instagram, toma encargos a medida, lleva señas, turnos y avisos, y contesta con el catálogo de la tienda. Lo que sale al mundo o no tiene vuelta atrás lo decide la dueña. Diseño y decisiones: `..\..\DISENO.md`.

Se monta en el harness v2 (`raphael-core`, contrato 2.1) por su `manifest.yaml`. Solo importa `raphael_core` y la stdlib (más pydantic, pyyaml y httpx, que ya trae el núcleo): ninguna otra brigada.

## Cocineros
| Id | Qué hace |
|---|---|
| `atencion` | Responde solo con la información cargada, anota las dudas (`responder_duda`, humano) y deriva reclamos (`derivar_humano`, humano). Es el cocinero de red de la instalación |
| `encargos` | Pedido a medida paso a paso, precio sugerido con la tabla de precios, `enviar_presupuesto` (aprobación, irreversible), estados del encargo (comando `estado`, solo la dueña) |
| `cobros` | Circuito de la seña: el cliente avisa y queda `confirmar_pago` (aprobación, irreversible) |
| `agenda` | Turnos (`confirmar_turno`, aprobación) y recordatorios (`enviar_recordatorio`, automático) |
| `avisos` | Le avisa al cliente cada cambio de estado (`avisar_estado`, automático) |
| `tareas` | Lo del negocio para la Secretaria del orquestador (`owner_tasks`): prioridades, motivos y opciones A/B/C |
| `tienda` | Catálogo de solo lectura (feed JSON o CSV por URL, Tiendanube, Shopify o WooCommerce): precio, stock y link; nunca inventa |

La Secretaria no es un cocinero: es el rol genérico del orquestador (pieza 02). Para la clienta habla con la dueña (modo `secretary`); en el personal la usa el maestro.

## Config del negocio
Va en `installation.brigades.empresas.config` (ver `src\raphael_empresas\config.py` y `..\instalacion\clienta.installation.yaml`). El `perfil.yaml` de Empresas 0.4 se convierte con `scripts\perfil_a_instalacion.py`.

## Probar
```
python -m pytest              # usa src\ y raphael-core / raphael-orchestrator del proyecto (o RAPHAEL_CORE_SRC / RAPHAEL_ORCH_SRC)
python scripts\puerta.py --min 74
python scripts\arrancar.py --instalacion ..\instalacion\clienta.installation.yaml --datos datos --probar --dev ..\..\..\..\nucleo\02-orquestador\codigo
```
La puerta corre pytest con cada Python que encuentre (3.12 y 3.13), ruff, la suite de contrato del harness en las dos ediciones y el chequeo de autonomía. Con `--min 74` falla si pasan menos de 74 tests. Si cambiás el manifiesto del paquete, corré `scripts\sync_manifest.py`: el de la raíz es la copia que encuentra el cargador en `brigadas\`.

## Tienda con plataformas
`store.source.kind`: `feed` (URL de un JSON o CSV), `tiendanube` (`store_id` y `contact`), `shopify` (`shop`: `tu-tienda.myshopify.com`, `api_version`) o `woocommerce` (`url` del sitio). Los tokens van en variables de entorno del servidor (`datos\tienda.env`): `TIENDANUBE_TOKEN`, `SHOPIFY_TOKEN`, `WOO_KEY` y `WOO_SECRET`, o los nombres que diga `token_env` / `secret_env`. En la instalación nunca va un token. No están probados contra tiendas reales.

## Estado (23 nov 2026)
124 tests en verde (Python 3.12 y 3.13): los 74 de Empresas 0.4 portados nativos (tabla en `..\..\tests\TRAZABILIDAD.md`) y 50 nuevos (puerta de autonomía, contrato, Tienda y sus plataformas, instalación). Ruff limpio. Probado en la nube; en la PC no se corrió pytest (la VM tiene Python 3.10).
