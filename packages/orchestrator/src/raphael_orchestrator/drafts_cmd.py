"""Comandos de brigadas CREADAS por borrador, desde el chat de la persona.

Portado de JarvisRemote `orquestador/brigadas.py` sobre `raphael_core.drafts` (firma y hash del harness). Los comandos
los interpreta CÓDIGO, nunca un modelo, y solo si el mensaje EMPIEZA con el comando (lo escribió la persona). Un texto
que devuelva un jefe, una nota o una página no puede activar nada: no pasa por acá. El almacén de borradores solo
existe en el `OwnerContext` (H-15).

  /brigadas                         lista lo montado, lo activo por borrador y los borradores
  /crear-brigada {json}             guarda un BORRADOR (no operativo) y muestra su revisión con el hash
  /revisar-brigada <id>             la revisión: tools, modelos, ruteo, validación y hash
  /activar-brigada <id> <hash>      ACTIVA con la aprobación firmada sobre ese hash exacto
  /desactivar-brigada <id>          la vuelve borrador (reversible)
  /descartar-brigada <id>           borra un borrador

Activar no la monta: queda disponible en "Agregar brigadas" de la app (montar cambia la instalación; eso es de la app).
El diseñador por descripción en lenguaje natural (JR `brigades/designer.py`) no está portado: por ahora el borrador se
pasa en JSON.
"""

from __future__ import annotations

import json
import re
from typing import Any

_CMD = re.compile(r"^\s*/(crear-brigada|revisar-brigada|activar-brigada|desactivar-brigada|descartar-brigada|brigadas)\b"
                  r"[ \t]*(.*)$", re.DOTALL | re.IGNORECASE)


def parse(text: str) -> tuple[str, str] | None:
    """(comando, argumentos) si el mensaje EMPIEZA con un comando de borradores; si no, None."""
    m = _CMD.match(text or "")
    return (m.group(1).lower(), m.group(2).strip()) if m else None


def _listing(ctx: Any, store: Any) -> str:
    mounted = [b for b in ctx.catalog() if b.get("mounted")]
    lines = ["Montadas: " + (", ".join(f"{b['name']} (/{b['id']})" + (" — caída" if b.get("down") else "")
                                       for b in mounted) or "ninguna") + "."]
    if store is not None:
        recs = store.list()
        active = [r["draft"]["id"] for r in recs if store.verified_active(r)]
        drafts = [r["draft"]["id"] for r in recs if not store.verified_active(r)]
        lines.append("Activas por borrador: " + (", ".join(active) or "ninguna") + ".")
        lines.append("Borradores: " + (", ".join(drafts) or "ninguno") + ".")
    return "\n".join(lines)


async def run(ctx: Any, cmd: str, arg: str, *, enabled: bool) -> str:
    """Ejecuta el comando y devuelve el texto (sale literal). Los errores esperables son texto, no excepciones."""
    from raphael_core.drafts import factory
    from raphael_core.drafts.store import DraftError, DraftInvalid

    store = getattr(ctx, "drafts", None)
    if cmd == "brigadas":
        return _listing(ctx, store if enabled else None)
    if not enabled:
        return "Las brigadas por borrador no están habilitadas en esta instalación."
    if store is None:
        return "Esta instalación no tiene almacén de borradores: no puedo crear ni activar brigadas desde acá."
    try:
        if cmd == "crear-brigada":
            try:
                raw = json.loads(arg)
            except ValueError:
                return ("Pasame el borrador en JSON: /crear-brigada {\"id\": …}. El diseño a partir de una descripción "
                        "todavía no está en esta versión.")
            rec = store.create(raw, origin="json")
            return factory.review_text(store.review(rec["draft"]["id"]))
        bid, _, rest = arg.partition(" ")
        bid = bid.strip()
        if not bid:
            return f"Falta el id de la brigada: /{cmd} <id>" + (" <hash>" if cmd == "activar-brigada" else "")
        if cmd == "revisar-brigada":
            return factory.review_text(store.review(bid))
        if cmd == "activar-brigada":
            ref = rest.strip().split(" ")[0] if rest.strip() else ""
            if not ref:
                return f"Falta el hash que revisaste: /activar-brigada {bid} <hash> (se ve en /revisar-brigada {bid})."
            who = getattr(ctx, "who", "") or "persona"
            rec = store.activate(bid, ref, by=who)
            ctx.record("borrador_activado", brigada=bid, hash=rec["hash"][:12], quien=who)
            return (f"Brigada '{bid}' ACTIVADA con tu aprobación (hash {rec['hash'][:12]}, firmada). Para que empiece a "
                    f"trabajar, montala desde «Agregar brigadas». Para apagarla: /desactivar-brigada {bid}.")
        if cmd == "desactivar-brigada":
            store.deactivate(bid)
            ctx.record("borrador_desactivado", brigada=bid)
            return f"Brigada '{bid}' DESACTIVADA: volvió a borrador y ya no es operativa."
        if cmd == "descartar-brigada":
            store.discard(bid)
            ctx.record("borrador_descartado", brigada=bid)
            return f"Borrador '{bid}' descartado."
    except DraftInvalid as exc:
        return ("No se pudo armar un borrador válido:\n- " + "\n- ".join(exc.errors[:12])
                + "\n\nNo se guardó nada. Ajustalo y probá de nuevo.")
    except DraftError as exc:
        return str(exc)
    return f"Comando desconocido: /{cmd}"
