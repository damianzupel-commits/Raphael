# raphael-encargos — Brigada Encargos

Toma pedidos a medida paso a paso, sugiere el presupuesto y lleva los estados.

Es una pieza de **Raphael**: se mantiene, versiona y testea sola, y se une a las demás en
[`raphael-harness`](../raphael-harness), que es el punto de reunión. No importa ninguna otra
brigada: se comunica solo a través del harness (eventos, consultas y acciones).

## Qué hace

- Pasos: prenda, ocasión, fecha (las fechas en números se confirman en palabras), detalles, referencias, medidas o turno, nombre (`encargos.datos_obligatorios`).
- Varios datos en un mismo mensaje; una pregunta en el medio se la pasa a Atención (vía harness) y retoma.
- Precio sugerido = base de la prenda más específica + recargos (`encargos.precios` / `recargos`).
- Deja `enviar_presupuesto` en **aprobación**; plazo menor a `urgente_si_dias_menor_a` → URGENTE, sin prometer.
- Comandos: `listar`, `ver`, `estado`.

## Eventos

| Publica | Escucha |
|---|---|
| `encargo.creado`, `encargo.presupuesto_enviado`, `encargo.estado_cambiado`, `turno.pedido` | `pago.confirmado`, `conversacion.derivada` |

## Probarla sola

```bash
# con raphael-harness al lado (../raphael-harness) o instalado
python -m pytest -q
```

## Instalarla

```bash
pip install -e ../raphael-harness -e .
```

El harness la encuentra por su entry point (`pyproject.toml`) y la carga si el perfil de la
empresa la incluye en `brigadas`.

## Mantenimiento

- Contrato con el harness: ver [`CONTRATO-BRIGADAS.md`](../raphael-harness/docs/CONTRATO-BRIGADAS.md).
- Cada cambio: test que lo cubra + entrada en `CHANGELOG.md` + subir `__version__` en `src/raphael_encargos/__init__.py`.
- Si cambia un evento que publica o escucha, avisar en el CHANGELOG: otras brigadas pueden depender de él.
