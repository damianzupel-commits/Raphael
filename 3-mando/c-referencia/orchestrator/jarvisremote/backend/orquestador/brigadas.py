"""Gestión de brigadas CREADAS desde el orquestador (Etapa 2): comandos de chat + operaciones para la API/UI.

Capacidad «crear_brigada»: Damian describe una brigada (en lenguaje natural, o pasa el JSON del borrador) y el orquestador
genera un BORRADOR desde el molde declarativo. El borrador NO es operativo: la línea roja es que solo se activa con una
acción explícita de Damian sobre el hash exacto que revisó (ver brigades/draft_store.py).

Los comandos del chat los interpreta CÓDIGO determinístico, nunca un modelo, y solo si el mensaje EMPIEZA con el comando
(lo escribió Damian en la caja de texto de la UI). Un texto que un jefe devuelva, una nota o una página no pueden
activar nada: no pasan por acá.

  /crear-brigada <descripción>      el modelo local diseña un BORRADOR (no activo) y se muestra su revisión
  /revisar-brigada <id>             la revisión de un borrador (o de una activa): tools, modelos, ruteo, pasos, hash
  /activar-brigada <id> <hash>      ACTIVA (aprobación firmada sobre ese hash exacto)
  /desactivar-brigada <id>          la vuelve borrador (reversible)
  /descartar-brigada <id>           borra un borrador
  /brigadas                         lista activas y borradores
"""

from __future__ import annotations

import re

from brigades import designer, draft_store, factory
from brigades.ejemplos import EJEMPLO_DELEGA, EJEMPLO_UN_AYUDANTE

_CMD = re.compile(r"^\s*/(crear-brigada|revisar-brigada|activar-brigada|desactivar-brigada|descartar-brigada|brigadas)\b[ \t]*(.*)$",
                  re.DOTALL | re.IGNORECASE)
EJEMPLOS = {EJEMPLO_UN_AYUDANTE["id"]: EJEMPLO_UN_AYUDANTE, EJEMPLO_DELEGA["id"]: EJEMPLO_DELEGA}


def active_ids() -> set[str]:
    """Ids de las brigadas creadas que están ACTIVAS (aprobación firmada y vigente). Nunca incluye borradores."""
    try:
        return set(draft_store.active_ids())
    except Exception:  # noqa: BLE001
        return set()


def parse_command(message: str) -> tuple[str, str] | None:
    """(comando, argumentos) si el mensaje EMPIEZA con un comando de gestión de brigadas; si no, None."""
    m = _CMD.match(message or "")
    return (m.group(1).lower(), m.group(2).strip()) if m else None


# --- vistas para la API / UI ------------------------------------------------------------------------------------------
def _row(rec: dict) -> dict:
    d = rec["draft"]
    rv = factory.review(d)
    return {"id": d["id"], "nombre": d["nombre"], "proposito": d["proposito"], "estado": rec["estado"],
            "hash_corto": rv["hash_corto"], "origen": rec.get("origen"), "creado": rec.get("creado"),
            "activada": (rec.get("aprobacion") or {}).get("ts"), "n_tools_sensibles": rv["n_tools_sensibles"],
            "delega": bool(d["ayudantes"]), "aprobacion_invalida": bool(rec.get("aprobacion_invalida"))}


def listing() -> dict:
    recs = draft_store.list_records()
    return {"activas": [_row(r) for r in recs if r["estado"] == "activa"],
            "borradores": [_row(r) for r in recs if r["estado"] != "activa"],
            "ejemplos": sorted(EJEMPLOS)}


def listing_text() -> str:
    d = listing()
    L = ["BRIGADAS CREADAS", ""]
    L.append("Activas: " + (", ".join(f"/{r['id']}" for r in d["activas"]) or "(ninguna)"))
    L.append("Borradores (NO operativos): " + (", ".join(f"{r['id']} [{r['hash_corto']}]" for r in d["borradores"]) or "(ninguno)"))
    L += ["", "Crear: /crear-brigada <descripción> · Revisar: /revisar-brigada <id> · Activar: /activar-brigada <id> <hash>"]
    return "\n".join(L)


# --- comandos ---------------------------------------------------------------------------------------------------------
async def run_command(cmd: str, arg: str, llm: designer.LLM | None = None) -> str:
    """Ejecuta el comando y devuelve el texto de respuesta. Los errores esperables son texto, no excepciones."""
    try:
        if cmd == "brigadas":
            return listing_text()
        if cmd == "crear-brigada":
            rec = await designer.design_from_description(arg, llm)
            return factory.review_text(draft_store.review_for(rec["draft"]["id"]))
        bid, _, rest = arg.partition(" ")
        bid = bid.strip()
        if not bid:
            return f"Falta el id de la brigada: /{cmd} <id>" + (" <hash>" if cmd == "activar-brigada" else "")
        if cmd == "revisar-brigada":
            rv = draft_store.review_for(bid)
            return factory.review_text(rv) if rv["estado"] != "activa" else f"La brigada '{bid}' está ACTIVA (hash {rv['hash_corto']}).\n\n" + factory.review_text(rv)
        if cmd == "activar-brigada":
            ref = rest.strip().split(" ")[0] if rest.strip() else ""
            if not ref:
                return f"Falta el hash que revisaste: /activar-brigada {bid} <hash>  (el hash se ve en /revisar-brigada {bid})"
            rec = draft_store.activate(bid, ref)
            return (f"✓ Brigada '{bid}' ACTIVADA con tu aprobación (hash {rec['hash'][:12]}, firmada). Ya podés usarla con /{bid} <pedido> "
                    f"o desde su pestaña. Validación: python -m validation.todas {bid}. Para apagarla: /desactivar-brigada {bid}.")
        if cmd == "desactivar-brigada":
            draft_store.deactivate(bid)
            return f"Brigada '{bid}' DESACTIVADA: volvió a borrador y ya no es operativa. Podés revisarla y activarla de nuevo."
        if cmd == "descartar-brigada":
            draft_store.discard(bid)
            return f"Borrador '{bid}' descartado."
    except draft_store.DraftInvalid as exc:
        return "No se pudo armar un borrador válido:\n- " + "\n- ".join(exc.errors[:12]) + "\n\nNo se guardó nada. Ajustá la descripción y probá de nuevo."
    except draft_store.DraftError as exc:
        return str(exc)
    except Exception as exc:  # noqa: BLE001 — p. ej. el modelo local apagado al diseñar
        return f"No se pudo completar el comando: {exc}" + (" — ¿Está corriendo Ollama? El diseñador usa el modelo local." if "onnection" in str(exc) else "")
    return f"Comando desconocido: /{cmd}"
