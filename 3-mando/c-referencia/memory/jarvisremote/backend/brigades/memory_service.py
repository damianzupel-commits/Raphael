"""Servicio de memoria del sistema — el puente WRITE-ONLY hacia Cerebro.

Paso 2 del plan de Cerebro (2026-11-03): que las brigadas lo ALIMENTEN. Cualquier
brigada que captura algo llama a `remember(...)` y eso entra a la **memoria unificada
del sistema** (el vault por default, el que lee Cerebro). Así Cerebro conoce lo que
capturó cada brigada, sin que las brigadas puedan LEER el vault personal.

Por qué write-only (defensa de privacidad): una brigada como Scout corre en la nube
(Groq). Si pudiera LEER el vault unificado, notas personales sensibles llegarían a un
modelo cloud. Entonces: las brigadas **escriben** su captura acá; **solo Cerebro
(local) lee** la memoria completa. El flujo es de una sola dirección.

`remember` fuerza el vault unificado aunque la brigada esté corriendo dentro de su
propio vault profile (entra con su propio `use_profile`), así la captura siempre cae
en la memoria de Cerebro y no en la del que la generó.
"""

from __future__ import annotations

import logging

from app.config import settings
from app.obsidian import profile as vault_profile
from app.obsidian import vault

logger = logging.getLogger("brigades.memory")


def remember(
    brigade_id: str,
    title: str,
    content: str,
    tags: list[str] | None = None,
    source: str | None = None,
) -> object | None:
    """Mete una captura de la brigada `brigade_id` en la memoria unificada (la de
    Cerebro). Best-effort: nunca debe romper el trabajo de la brigada que la llama.
    Devuelve la nota creada, o None si falló.

    La nota queda firmada 'jarvis', tagueada `brigada-<id>` + `capturado` (trazable
    a qué brigada la trajo), con la fuente en el frontmatter."""
    try:
        unified = vault_profile.VaultProfile(
            vault_path=settings.obsidian_vault_path,
            embeddings_path=settings.obsidian_embeddings_path,
        )
        all_tags = [f"brigada-{brigade_id}", "capturado", *(tags or [])]
        extra = {"brigada": brigade_id}
        if source:
            extra["fuente"] = source
        with vault_profile.use_profile(unified):
            return vault.save_note(
                title=title,
                content=content,
                author="jarvis",
                tags=all_tags,
                category=brigade_id,
                extra=extra,
            )
    except Exception:  # noqa: BLE001 — alimentar a Cerebro es un extra, no debe romper nada
        logger.warning("no se pudo alimentar a Cerebro desde '%s'", brigade_id, exc_info=True)
        return None
