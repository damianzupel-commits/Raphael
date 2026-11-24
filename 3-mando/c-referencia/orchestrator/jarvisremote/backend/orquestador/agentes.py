"""Quiénes trabajan en cada brigada, para la vista del orquestador (terminología de Damian):

  - COCINEROS = agentes PERMANENTES de una brigada: el jefe (persistente, recuerda; con LLM PROPIO para planificar y
                sintetizar) y cualquier ayudante que sea persistente.
  - EFÍMEROS  = ayudantes que se crean por tarea y mueren: acá solo se listan los que la brigada PUEDE crear (los que están
                corriendo ahora salen de `brigades/live.py`).

Todo sale del spec de la brigada (no hay una lista aparte que se pueda desactualizar) y el modelo es el EFECTIVO + proveedor
(resuelto de la config real, sin tocar claves).
"""

from __future__ import annotations

from typing import Any


def _persistente(a: Any) -> bool:
    try:
        return bool(a.config().persistent)
    except Exception:  # noqa: BLE001 — sin poder armarlo, se lo trata como efímero (lo normal en este molde)
        return False


def cocineros(spec: Any) -> dict:
    """{'nombre', 'cocineros': [...], 'efimeros': [...]} de una brigada, desde su `BrigadeSpec`."""
    from brigades.config import effective_label

    cooks: list[dict] = []
    if spec.persistent:
        # Todo jefe tiene su PROPIO LLM (intercambiable por config): coordina, sintetiza y reporta; nunca responde directo.
        modelo = effective_label(spec.load_client_model)
        detalle = f"coordina {len(spec.ayudantes)} ayudante(s) efímero(s): planifica, sintetiza y le reporta al orquestador"
        try:
            n_tools = len(spec.tool_names())
        except Exception:  # noqa: BLE001
            n_tools = 0
        cooks.append({"id": spec.id, "nombre": spec.name, "rol": "jefe", "detalle": detalle, "modelo": modelo,
                      "memoria": True, "tools": n_tools})
    efimeros: list[dict] = []
    for a in spec.ayudantes:
        item = {"id": a.id, "modo": a.modo, "descripcion": a.descripcion, "modelo": effective_label(a.resolve_client_model)}
        if _persistente(a):
            cooks.append({"id": a.id, "nombre": a.id, "rol": f"ayudante «{a.modo}»", "detalle": a.descripcion,
                          "modelo": item["modelo"], "memoria": True, "tools": len(a.tool_names())})
        else:
            efimeros.append(item)
    return {"nombre": spec.name, "cocineros": cooks, "efimeros": efimeros}


def todas(ids: list[str]) -> dict[str, dict]:
    """Cocineros de varias brigadas (las que no se pueden resolver, como un borrador o una legacy sin spec, se omiten)."""
    from brigades.registry import get_spec

    out: dict[str, dict] = {}
    for bid in ids:
        try:
            out[bid] = cocineros(get_spec(bid))
        except Exception:  # noqa: BLE001 — una brigada que no resuelve no tumba la vista de las demás
            continue
    return out


# --- auditoría de datos por rol (O-11) --------------------------------------------------------------------------------------
_VE = {
    "orquestador": "hasta 1500 caracteres de un pedido que las reglas no resuelven (para clasificarlo); la descripción de una brigada al diseñarla",
    "voz": "el pedido, el reporte interno del jefe (resumen, hallazgos, títulos de las fuentes, propuestas, fallos) y la conversación previa resumida",
    "mando": "en el trabajo conjunto: el pedido (para repartirlo) y los reportes de las brigadas (resumen, hallazgos, títulos de las fuentes) para concluir",
    "jefe": "el pedido, lo que devolvieron sus ayudantes (texto y extractos de las fuentes) y un resumen de sus turnos anteriores; en una cadena (DAG), además el reporte de las brigadas de las que depende",
    "ayudante": "su sub-tarea, el contexto previo de la brigada y todo lo que devuelven sus tools; en una cadena (DAG), además el reporte de las brigadas de las que depende la suya",
}


def privacidad(ids: list[str]) -> dict:
    """Por rol: modelo efectivo, proveedor, si corre en esta PC (`local`) y qué datos le llegan. Lista aparte los proveedores
    de nube que hoy reciben algo, para verlo de un vistazo."""
    from brigades.config import describe_role_model
    from brigades.registry import get_spec

    def fila(rol: str, ident: str, d: dict, extra: str = "") -> dict:
        return {"rol": rol, "id": ident, "modelo": d.get("label", ""), "proveedor": d.get("provider", "?"), "local": bool(d.get("local")),
                "resuelto": bool(d.get("ok", True)), "ve": _VE[rol] + extra}

    roles = [fila("orquestador", "orquestador", describe_role_model("orquestador")), fila("voz", "orquestador", describe_role_model("voz")),
             fila("mando", "orquestador", describe_role_model("mando"))]
    for bid in ids:
        try:
            spec = get_spec(bid)
        except Exception:  # noqa: BLE001 — una brigada que no resuelve no tumba la auditoría de las demás
            continue
        roles.append(fila("jefe", spec.id, describe_role_model("jefe", spec.id, tipo=spec.client, declarado=spec.client_model)))
        for a in spec.ayudantes:
            try:
                tools = sorted(a.tool_names())
            except Exception:  # noqa: BLE001
                tools = []
            lee_vault = any(t.startswith("obsidian_") for t in tools)
            roles.append(fila("ayudante", a.id, describe_role_model("ayudante", helper_id=a.id, declarado=a.client_model),
                              " (lee el vault: notas personales)" if lee_vault else ""))
    nube = sorted({r["proveedor"] for r in roles if not r["local"] and r["resuelto"]})
    return {"roles": roles, "proveedores_en_la_nube": nube, "todo_local": not nube}


# --- autoconocimiento: qué brigadas tiene Raphael, armado por CÓDIGO desde el registro ----------------------------------------
def reporte_del_sistema(operativas: list[str], construidas_sin_pestana: list[str] | None = None, borradores: list[str] | None = None):
    """Un `ReporteInterno` con lo que Raphael ES hoy: brigadas operativas (nombre, para qué, ayudantes, modelo del jefe), las
    construidas que todavía no se usan desde el orquestador y los borradores sin activar. Ningún modelo interviene: sale del
    registro, así que la voz lo comunica con el mismo control de fidelidad que cualquier otro reporte."""
    from brigades import contracts
    from brigades.config import describe_role_model
    from brigades.identidad import personalizar
    from brigades.registry import get_spec

    hallazgos, nombres = [], []
    for bid in operativas:
        try:
            spec = get_spec(bid)
        except Exception:  # noqa: BLE001 — una brigada que no resuelve no tumba la respuesta
            continue
        try:
            modelo = describe_role_model("jefe", spec.id, tipo=spec.client, declarado=spec.client_model).get("label", "")
        except Exception:  # noqa: BLE001
            modelo = ""
        ayudantes = ", ".join(f"{a.modo} ({contracts.recortar(a.descripcion, 110)})" for a in spec.ayudantes)
        nombres.append(spec.name)
        hallazgos.append({"texto": contracts.recortar(f"{spec.name} (se usa con /{spec.id} o desde su pestaña): {spec.purpose} Ayudantes: {ayudantes}."
                                                      + (f" Modelo del jefe: {modelo}." if modelo else ""), contracts.MAX_HALLAZGO),
                          "ayudante": "orquestador", "fuentes": []})
    for bid in construidas_sin_pestana or []:
        try:
            spec = get_spec(bid)
        except Exception:  # noqa: BLE001
            continue
        hallazgos.append({"texto": contracts.recortar(f"{spec.name}: construida, pero todavía no se usa desde el orquestador. {spec.purpose}", contracts.MAX_HALLAZGO),
                          "ayudante": "orquestador", "fuentes": []})
    resumen = ("Las brigadas operativas de Raphael son: " + ", ".join(nombres) + "." if nombres else "Raphael no tiene brigadas operativas en este momento.")
    resumen += " El orquestador reparte cada pedido, puede poner a varias a trabajar juntas y es el único que le habla a Damian."
    if borradores:
        resumen += " Borradores sin activar: " + ", ".join(borradores[:10]) + "."
    return contracts.ReporteInterno.validar({
        "version": contracts.VERSION, "brigada": "orquestador", "resumen": contracts.recortar(personalizar(resumen), contracts.MAX_RESUMEN),
        "hallazgos": [{**h, "texto": personalizar(h["texto"])} for h in hallazgos[:contracts.MAX_HALLAZGOS]], "confianza": "alta",
        "avisos": [personalizar("Para crear una brigada nueva: /crear-brigada <descripción> (queda como borrador hasta que Damian la activa).")],
    })
