"""Tools de la brigada: lo que usan los efímeros del jefe. Las arma `validate` (el `setup` del manifiesto).

Leer no cambia nada. Guardar una nota es aditivo (siempre firmada `jarvis`). Olvidar y exportar piden la aprobación de la
persona en cada uso. Comparten el código de las acciones de los cocineros (`actions.run`): mismas validaciones, mismos topes.
Sin modelo en estas tools: consolidar y destilar episodios usan el modelo local y siguen siendo de sus cocineros.
"""

from __future__ import annotations

from datetime import datetime

from raphael_core import Action, Origin

from . import actions
from .brain import Brain
from .episodes import recall_auto, recall_query, render


class _ToolCtx:
    """Lo mínimo que `Brain.from_ctx` necesita del contexto, sin modelo: las tools no sintetizan ni destilan."""

    def __init__(self, setup_ctx) -> None:
        self.config, self.shared = setup_ctx.config, setup_ctx.shared

    @staticmethod
    def now() -> datetime:
        return datetime.now()

    @staticmethod
    def ai(*_a, **_k):
        return None

    @staticmethod
    def has_ai(*_a, **_k) -> bool:
        return False


def make_tools(ctx) -> dict:
    tc = _ToolCtx(ctx)

    def _brain() -> Brain:
        return Brain.from_ctx(tc)

    def _hacer(tipo: str, data: dict, resumen: str) -> dict:
        res = actions.run(_brain(), Action(tipo, data, resumen, origin=Origin.SYSTEM))
        tc.shared.put("resultados", tipo, res)
        actions.log_activity(tc, tipo, resumen, res)
        return res

    def memoria_recordar(query: str, limit: int = 5, sin_sensibles: bool = False) -> dict:
        """Trae de las notas la evidencia de una consulta: cada nota fuente con su extracto textual. Si no hay, lo dice."""
        return _brain().evidence(str(query).strip(), limit=min(max(int(limit), 1), 20), sin_sensibles=bool(sin_sensibles))

    def memoria_buscar(query: str, limit: int = 10, author: str = "") -> dict:
        """Búsqueda híbrida de notas (semántica si hay embeddings, si no por palabra clave)."""
        brain = _brain()
        ranked, diag = brain.search(str(query).strip(), author=author or None, limit=min(max(int(limit), 1), 30))
        return {**diag, "resultados": [{**n.summary(), "score": s, "sensible": brain.is_sensitive(n.id)} for n, s in ranked]}

    def memoria_leer_nota(id: str) -> dict:
        """Una nota entera por su id."""
        try:
            brain = _brain()
            return {**brain.vault.read(str(id)).to_dict(), "sensible": brain.is_sensitive(str(id))}
        except (FileNotFoundError, ValueError) as exc:
            return {"ok": False, "motivo": str(exc)}

    def memoria_notas(author: str = "", tag: str = "") -> list[dict]:
        """Las notas del vault (resumen de cada una), filtradas por autor (human o jarvis) o etiqueta."""
        return [n.summary() for n in _brain().vault.list_notes(author=author or None, tag=tag or None)][:200]

    def memoria_estado() -> dict:
        """Estado del Cerebro: cuántas notas, cuántas con vector y si busca por significado o por palabra clave."""
        return {k: v for k, v in _brain().status().items() if k != "modelo_local"}

    def memoria_asociar(query: str, limit: int = 10, anticipar: bool = False, diversificar: bool = False) -> dict:
        """Recuperación asociativa: activa las notas que matchean y propaga por los wikilinks."""
        return _brain().spread(str(query).strip(), limit=min(max(int(limit), 1), 30), anticipar=bool(anticipar),
                               diversificar=bool(diversificar))

    def memoria_analogias(nota: str, limit: int = 8) -> dict:
        """Análogos estructurales de una nota en otros dominios."""
        return _brain().analogies(str(nota), limit=min(max(int(limit), 1), 20))

    def memoria_componer(conceptos: list, limit: int = 10) -> dict:
        """Notas que están en la intersección de varios conceptos."""
        return _brain().compose([str(c) for c in conceptos or []], limit=min(max(int(limit), 1), 30))

    def memoria_curiosidad(limit: int = 10) -> dict:
        """Huecos del vault: notas citadas que no existen y notas huérfanas."""
        return _brain().curiosity(limit=min(max(int(limit), 1), 30))

    def memoria_episodios(tema: str = "", limit: int = 8) -> dict:
        """Episodios recientes, o los que se parecen a un tema."""
        brain = _brain()
        eps = brain.episodes.list()
        n = min(int(limit) if int(limit) > 0 else 8, 30)
        chosen = (recall_query(eps, str(tema), n) if tema
                  else recall_auto(eps, tc.now(), hours=brain.cfg.episodes.recall_window_hours, max_items=n))
        return {"texto": render(chosen), "episodios": [e.to_dict() for e in chosen]}

    def memoria_verificar_registro() -> dict:
        """Verifica que la cadena de hashes del registro de memoria no se haya tocado."""
        return _brain().episodes.verify()

    def memoria_actividad(limit: int = 20) -> list[dict]:
        """Lo que Cerebro hizo solo, lo más nuevo primero."""
        return (tc.shared.get("estado", "actividad") or {}).get("items", [])[: min(max(int(limit), 1), 100)]

    def memoria_guardar(title: str, content: str, tags: list | None = None, category: str = "") -> dict:
        """Guarda una nota nueva en el vault, firmada jarvis. No modifica las que ya existen."""
        return _hacer("guardar_nota", {"title": title, "content": content, "tags": tags or [], "category": category},
                      f"Guardar la nota «{str(title)[:80]}»")

    def memoria_olvidar(kind: str, id: str) -> dict:
        """Borra un episodio ('episodio') o una nota ('nota') del vault. Cada uso pide la aprobación de la persona."""
        return _hacer("olvidar", {"kind": kind, "id": id}, f"Olvidar {kind} {id}")

    def memoria_exportar(destino: str) -> dict:
        """Copia el vault entero a un .zip en la ruta indicada. Cada uso pide la aprobación de la persona."""
        return _hacer("exportar_vault", {"destino": destino}, "Exportar el vault a un .zip")

    return {f.__name__: f for f in (
        memoria_recordar, memoria_buscar, memoria_leer_nota, memoria_notas, memoria_estado, memoria_asociar, memoria_analogias,
        memoria_componer, memoria_curiosidad, memoria_episodios, memoria_verificar_registro, memoria_actividad, memoria_guardar,
        memoria_olvidar, memoria_exportar)}
