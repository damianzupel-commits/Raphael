# raphael-cobros — Brigada Cobros

El circuito de la seña: el bot nunca da un pago por recibido.

Es una pieza de **Raphael**: se mantiene, versiona y testea sola, y se une a las demás en
[`raphael-harness`](../raphael-harness), que es el punto de reunión. No importa ninguna otra
brigada: se comunica solo a través del harness (eventos, consultas y acciones).

## Qué hace

- Anota las señas esperadas cuando sale un presupuesto.
- "Ya transferí" o comprobante → agradece y deja `confirmar_pago` en **aprobación** ("Me llegó").
- Si la dueña rechaza, vuelve a esperar.
- Comandos: `esperando`, `avisados`.

## Eventos

| Publica | Escucha |
|---|---|
| `pago.confirmado` | `encargo.presupuesto_enviado`, `pendiente.rechazado` |

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
- Cada cambio: test que lo cubra + entrada en `CHANGELOG.md` + subir `__version__` en `src/raphael_cobros/__init__.py`.
- Si cambia un evento que publica o escucha, avisar en el CHANGELOG: otras brigadas pueden depender de él.
