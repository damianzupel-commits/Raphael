# raphael-harness — el punto de reunión de Raphael

Raphael es un asistente con IA para pymes que automatiza la atención, los pedidos, los cobros,
la agenda y los avisos, dejando las decisiones importantes a una persona.

Cada pieza vive en su propio repo y se mantiene por separado. Este repo es donde se juntan:

```
                 raphael-harness  (este repo: el punto de reunión)
   contrato · perfil de empresa · Policy Engine · capa de modelos · bus de eventos
          almacén por brigada · registro de uso · supervisión · panel · CLI
                                    │
   ┌──────────────┬────────────┬────┴───────┬────────────┬────────────┐
raphael-      raphael-     raphael-     raphael-     raphael-     raphael-
orquestador   atencion     encargos     cobros       agenda       avisos

Alrededor, para venderlo:
  raphael-servidor  → corre en el mini PC del cliente (panel de la dueña, WhatsApp/Instagram, licencia, backups, instalador)
  raphael-relay     → en la nube: recibe los webhooks de Meta y los encola por cliente
  raphael-central   → tuyo: licencias y panel de soporte
```

## Qué pone el harness

| Pieza | Archivo | Para qué |
|---|---|---|
| Contrato | `contrato.py` | Lo que cumple toda brigada y el orquestador (`CONTRATO = 1`) |
| Perfil de empresa | `perfil.py` | Lo único distinto entre clientes (`ejemplos/perfil-ropa-medida.yaml`) |
| Policy Engine | `politicas.py` | Automático / aprobación / siempre humano; el perfil solo endurece |
| Capa de modelos | `modelos.py`, `modelos.yaml` | IA por rol y por plan; sin modelo o con falla → reglas |
| Registro de uso | `uso.py` | Mensajes, tokens y costo por mes; tope por plan |
| Bus de eventos | `eventos.py` | Las brigadas se enteran de lo que hacen otras sin conocerse |
| Almacén | `almacen.py` | SQLite con un espacio por brigada |
| Cargador | `cargador.py` | Encuentra piezas instaladas (entry points) o repos vecinos (`--dev`) |
| Harness | `harness.py` | Recibe mensajes, ordena con el orquestador, pendientes, aprobar/rechazar/resolver, supervisión |
| CLI | `cli.py` | `piezas`, `validar`, `chat`, `estado` |
| Pruebas | `testing.py` | Para que cada brigada se pruebe sola |

## Empezar (desarrollo, todos los repos lado a lado)

```bash
cd raphael-harness
python -m raphael_harness piezas --dev ..                     # qué piezas encuentra
python -m raphael_harness validar ejemplos/perfil-ropa-medida.yaml
python -m raphael_harness chat --perfil ejemplos/perfil-ropa-medida.yaml --dev ..
python -m pytest -q                                            # incluye la prueba de punta a punta
```

(Sin instalar: `PYTHONPATH=src`. Instalado: `pip install -e .` y el comando `raphael`.)

En el chat, cada línea es un mensaje del cliente; `/pendientes`, `/aprobar N {"precio": 180000}`,
`/rechazar N`, `/resolver N respuesta`, `/cmd encargos estado {"num":1,"estado":"listo"}`, `/tick`, `/estado`.

## Documentos

- [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) — cómo encajan las piezas y por qué.
- [`docs/CONTRATO-BRIGADAS.md`](docs/CONTRATO-BRIGADAS.md) — cómo crear o mantener una brigada.
- [`docs/RAPHAEL-PYMES-CONTEXTO.md`](docs/RAPHAEL-PYMES-CONTEXTO.md) — contexto completo del producto, decisiones, hoja de ruta y checklist de lanzamiento.
- [`scripts/`](scripts) — correr los tests de todos los repos e instalar todo en modo desarrollo.
