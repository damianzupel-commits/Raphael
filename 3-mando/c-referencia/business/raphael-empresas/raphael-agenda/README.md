# raphael-agenda — Brigada Agenda

Turnos de prueba, medidas y retiro, con recordatorios.

Es una pieza de **Raphael**: se mantiene, versiona y testea sola, y se une a las demás en
[`raphael-harness`](../raphael-harness), que es el punto de reunión. No importa ninguna otra
brigada: se comunica solo a través del harness (eventos, consultas y acciones).

## Qué hace

- Pide día (ofrece `agenda.franjas`); con día y hora deja `confirmar_turno` en **aprobación**.
- No permite dos turnos en el mismo día y hora; la dueña puede cambiar fecha u hora al confirmar.
- `tick`: recordatorio automático `agenda.recordatorio_dias_antes` días antes, una sola vez.
- Comandos: `turnos`, `calendario`.

## Eventos

| Publica | Escucha |
|---|---|
| `turno.confirmado` | `turno.pedido` |

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
- Cada cambio: test que lo cubra + entrada en `CHANGELOG.md` + subir `__version__` en `src/raphael_agenda/__init__.py`.
- Si cambia un evento que publica o escucha, avisar en el CHANGELOG: otras brigadas pueden depender de él.
