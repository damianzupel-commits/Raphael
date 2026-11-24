# raphael-atencion — Brigada Atención

Responde solo con la información del perfil, anota lo que no sabe y deriva reclamos.

Es una pieza de **Raphael**: se mantiene, versiona y testea sola, y se une a las demás en
[`raphael-harness`](../raphael-harness), que es el punto de reunión. No importa ninguna otra
brigada: se comunica solo a través del harness (eventos, consultas y acciones).

## Qué hace

- Pregunta con respuesta cargada (horarios, envíos, medios de pago, ubicación, `informacion.faq`) → responde.
- Pregunta sin respuesta → "te lo confirma {dueña}" + pendiente **humano** `responder_duda`.
- Reclamo → se retira, avisa y crea `derivar_humano` (**humano**); publica `conversacion.derivada`.

## Eventos

| Publica | Escucha |
|---|---|
| `conversacion.derivada` | — |

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
- Cada cambio: test que lo cubra + entrada en `CHANGELOG.md` + subir `__version__` en `src/raphael_atencion/__init__.py`.
- Si cambia un evento que publica o escucha, avisar en el CHANGELOG: otras brigadas pueden depender de él.
