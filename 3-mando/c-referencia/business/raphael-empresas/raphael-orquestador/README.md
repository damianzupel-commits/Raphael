# raphael-orquestador — Orquestador

Decide qué brigada atiende cada mensaje.

Es una pieza de **Raphael**: se mantiene, versiona y testea sola, y se une a las demás en
[`raphael-harness`](../raphael-harness), que es el punto de reunión. No importa ninguna otra
brigada: se comunica solo a través del harness (eventos, consultas y acciones).

## Qué hace

1. Un reclamo o pedido de hablar con una persona va primero a **Atención**.
2. La brigada con una conversación abierta con ese contacto sigue.
3. Después, por interés declarado (0 a 1), de mayor a menor.
4. **Atención** queda siempre al final como red.

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
- Cada cambio: test que lo cubra + entrada en `CHANGELOG.md` + subir `__version__` en `src/raphael_orquestador/__init__.py`.
- Si cambia un evento que publica o escucha, avisar en el CHANGELOG: otras brigadas pueden depender de él.
