"""Recuperador: trae del vault la EVIDENCIA de una consulta (asociativo + palabra clave): notas fuente con su extracto
textual. No concluye ni resume: copia. Solo lectura. Si ninguna nota responde, lo dice («NO ENCONTRADO»).

Solo le responde a la persona dueña: un mensaje de un tercero (cliente, página, archivo) NUNCA lee el vault personal.
"""

from __future__ import annotations

import re

from raphael_core import ActionError, Cook, Health, Message, Reply, Trust

from ..brain import Brain
from ..textutil import norm

ASK = re.compile(r"\b(que sabes|que sabemos|recorda\w*|acordate|busca\w* en (mis )?notas|segun mis notas|en el vault|"
                 r"en mis notas|mi memoria|que dice mi nota|nota sobre)\b")


def render(ev: dict) -> str:
    if not ev["encontrado"]:
        return ev["no_encontrado"] + (f" ({ev['aviso']})" if ev.get("aviso") else "")
    lines = [f"Esto es lo que hay en tus notas sobre «{ev['query']}»:"]
    for f in ev["fuentes"]:
        lines.append(f"• «{f['titulo']}» ({f['id']}): {f['extracto']}")
    if ev.get("aviso"):
        lines.append(f"(Busqué por palabra clave: {ev['aviso']})")
    return "\n".join(lines)


class Retriever(Cook):
    name = "recuperador"
    version = "2.0.0"
    description = "Trae del vault la evidencia de una consulta, con su fuente. Solo lectura."
    commands = {"recordar": "Evidencia de una consulta {'query', 'limit'}", "buscar": "Búsqueda híbrida de notas {'query'}",
                "leer_nota": "Una nota por id {'id'}", "notas": "Notas del vault {'author', 'tag'}",
                "estado": "Estado del Cerebro: vault, embeddings, modelo", "rastro": "Último rastro de activación"}

    def interest(self, msg: Message, ctx) -> float:
        return 0.85 if msg.trust is Trust.TRUSTED and ASK.search(norm(msg.text)) else 0.0

    def handle(self, msg: Message, ctx) -> Reply | None:
        if msg.trust is not Trust.TRUSTED or not ASK.search(norm(msg.text)):
            return None
        query = re.sub(ASK, " ", norm(msg.text)).strip(" ?¿!¡.,:") or msg.text
        return Reply(render(Brain.from_ctx(ctx).evidence(query)))

    def command(self, name: str, data: dict, ctx):
        brain = Brain.from_ctx(ctx)
        if name == "recordar":
            q = str(data.get("query") or "").strip()
            if not q:
                raise ActionError("falta 'query'")
            return brain.evidence(q, limit=int(data.get("limit", 5)), sin_sensibles=bool(data.get("sin_sensibles")))
        if name == "buscar":
            q = str(data.get("query") or "").strip()
            if not q:
                raise ActionError("falta 'query'")
            ranked, diag = brain.search(q, author=data.get("author"), limit=int(data.get("limit", 10)))
            return {**diag, "resultados": [{**n.summary(), "score": s} for n, s in ranked]}
        if name == "leer_nota":
            try:
                return brain.vault.read(str(data.get("id") or "")).to_dict()
            except (FileNotFoundError, ValueError) as exc:
                raise ActionError(str(exc)) from None
        if name == "notas":
            return [n.summary() for n in brain.vault.list_notes(author=data.get("author"), tag=data.get("tag"))]
        if name == "estado":
            return brain.status()
        if name == "rastro":
            return brain.last_trace()
        return super().command(name, data, ctx)

    def health(self, ctx) -> Health:
        return Health(True)
