"""Tools de control de la memoria episódica (§9 del spec).

Le dan a Damian (vía Raphael) el control sobre lo que la memoria recuerda:
recordar, listar, corregir y olvidar. La CAPTURA es automática (app/memory/
capture.py, hookeada en agent.py); estas tools son para consultar y gobernar.

ADITIVO y defensivo: si el módulo de memoria no está disponible, devuelven un
error claro sin romper el backend.
"""

from __future__ import annotations

from . import register_tool


@register_tool(
    name="memoria_recordar",
    description=(
        "Trae recuerdos (episodios) de la memoria episódica de Raphael sobre un tema. Si pasás "
        "`tema`, busca por palabras clave en lo que se hizo, se decidió y las lecciones. Si lo "
        "dejás vacío, trae los recuerdos recientes (últimas horas) + los más importantes. Devuelve "
        "resúmenes compactos con su id. Usalo cuando necesites contexto de qué pasó antes."
    ),
    parameters={
        "type": "object",
        "properties": {
            "tema": {"type": "string", "description": "Tema a recordar (opcional). Vacío = recientes + salientes."},
            "max": {"type": "integer", "description": "Cuántos traer (default 8)."},
        },
        "required": [],
    },
)
def memoria_recordar(tema: str = "", max: int = 8) -> dict:
    try:
        from ..memory import recall
    except Exception as exc:  # noqa: BLE001
        return {"error": f"memoria no disponible: {exc!r}"}
    eps = recall.recall_query(tema, max_items=max) if tema.strip() else recall.recall_auto(max_items=max)
    return {"tema": tema, "count": len(eps), "recuerdos": [e.summary_line() + f" · id:{e.id}" for e in eps]}


@register_tool(
    name="memoria_listar",
    description=(
        "Lista los episodios guardados en la memoria (más nuevo primero), con dominio, resultado, "
        "sensibilidad e id — para que Damian vea qué recuerda Raphael y decida corregir o borrar algo."
    ),
    parameters={
        "type": "object",
        "properties": {
            "max": {"type": "integer", "description": "Máximo a listar (default 20)."},
        },
        "required": [],
    },
)
def memoria_listar(max: int = 20) -> dict:
    try:
        from ..memory import store
    except Exception as exc:  # noqa: BLE001
        return {"error": f"memoria no disponible: {exc!r}"}
    eps = store.list_episodes()[:max]
    return {
        "count": len(eps),
        "episodios": [
            {"id": e.id, "inicio": e.timestamp_inicio, "dominio": e.dominio,
             "resultado": e.resultado, "sensibilidad": e.sensibilidad,
             "salience": e.salience, "trigger": e.trigger[:120]}
            for e in eps
        ],
    }


@register_tool(
    name="memoria_corregir",
    description=(
        "Corrige un episodio mal recordado. NO edita el original (la memoria es append-only y "
        "tamper-evident): crea un episodio NUEVO que corrige al anterior, referenciándolo. Pasá el "
        "`id` del episodio a corregir y la corrección en `porque` (la lección/qué pasó realmente)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "id": {"type": "string", "description": "Id del episodio a corregir."},
            "porque": {"type": "string", "description": "La corrección: qué pasó realmente / la lección correcta."},
        },
        "required": ["id", "porque"],
    },
)
def memoria_corregir(id: str, porque: str) -> dict:
    try:
        from ..memory import store
        from ..memory.schema import Episode, now_iso
    except Exception as exc:  # noqa: BLE001
        return {"error": f"memoria no disponible: {exc!r}"}
    original = store.get_episode(id)
    if original is None:
        return {"error": f"no existe el episodio {id}"}
    corr = Episode(
        level=original.level, conv_id=original.conv_id,
        timestamp_inicio=now_iso(), timestamp_fin=now_iso(),
        trigger=original.trigger, dominio=original.dominio,
        acciones=original.acciones, resultado=original.resultado,
        porque=porque, sensibilidad=original.sensibilidad,
        links=[id], corrects=id, distilled_by="correccion_damian",
        salience=max(original.salience, 0.6),
    )
    store.save_episode(corr)
    return {"corregido": id, "nuevo_id": corr.id, "porque": porque}


@register_tool(
    name="memoria_olvidar",
    description=(
        "Borra un episodio de la memoria. Es el ÚNICO borrado real que existe (el sistema jamás "
        "borra solo). Queda registrado en el log firmado QUE se borró (no qué decía). Usalo solo "
        "cuando Damian lo pida explícitamente."
    ),
    parameters={
        "type": "object",
        "properties": {"id": {"type": "string", "description": "Id del episodio a olvidar."}},
        "required": ["id"],
    },
)
def memoria_olvidar(id: str) -> dict:
    try:
        from ..memory import store
    except Exception as exc:  # noqa: BLE001
        return {"error": f"memoria no disponible: {exc!r}"}
    existed = store.forget_episode(id)
    return {"olvidado": id, "existía": existed}


@register_tool(
    name="memoria_verificar",
    description=(
        "Verifica la integridad del log firmado de la memoria episódica (hash-chain + Ed25519): "
        "confirma que nadie manipuló la autobiografía de Raphael. Devuelve ok/roto y dónde."
    ),
    parameters={"type": "object", "properties": {}, "required": []},
)
def memoria_verificar() -> dict:
    try:
        from ..memory import store
    except Exception as exc:  # noqa: BLE001
        return {"error": f"memoria no disponible: {exc!r}"}
    return store.verify_integrity()
