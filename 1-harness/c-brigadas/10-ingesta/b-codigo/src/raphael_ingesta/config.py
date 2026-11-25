"""Configuración de la brigada (la valida el harness con `config_schema` y acá se lee con valores por defecto)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

SOURCES = ("youtube", "web", "arxiv")

DEFAULT_TOPICS = (
    "ciberseguridad ofensiva y defensiva",
    "hacking",
    "IA y agentes",
    "métodos de aprendizaje",
    "robótica y exoesqueletos",
    "desarrollo del propio asistente",
)
DEFAULT_ARXIV_QUERY = "cat:cs.AI OR cat:cs.LG OR cat:cs.CR OR cat:q-bio.NC"


@dataclass(frozen=True)
class Settings:
    mode: str = "real"  # real | simulado
    modes: dict[str, str] = field(default_factory=dict)  # override por fuente
    vault_dir: str = ""  # carpeta del vault (Markdown); vacía = solo el almacén de la brigada
    per_tick: int = 2  # ítems de la cola que se procesan por pasada
    check_every_min: int = 60  # cada cuánto se revisan las listas y búsquedas vigiladas
    max_per_list: int = 10  # tope de ítems nuevos que una lista mete a la cola por revisión
    topics: tuple[str, ...] = DEFAULT_TOPICS  # temas contra los que se etiqueta la relevancia
    arxiv_query: str = DEFAULT_ARXIV_QUERY
    max_text_chars: int = 12000  # lo que se le manda al modelo

    def mode_of(self, source: str) -> str:
        return self.modes.get(source) or self.mode


def settings_of(config: dict | None) -> Settings:
    c = dict(config or {})
    vault = str(c.get("vault_dir") or os.environ.get("RAPHAEL_VAULT_DIR", "")).strip()
    return Settings(
        mode=c.get("modo", "real"),
        modes=dict(c.get("modos") or {}),
        vault_dir=vault,
        per_tick=int(c.get("por_pasada", 2)),
        check_every_min=int(c.get("revisar_cada_min", 60)),
        max_per_list=int(c.get("max_por_lista", 10)),
        topics=tuple(c.get("temas") or DEFAULT_TOPICS),
        arxiv_query=str(c.get("arxiv_busqueda") or DEFAULT_ARXIV_QUERY),
        max_text_chars=int(c.get("max_caracteres", 12000)),
    )
