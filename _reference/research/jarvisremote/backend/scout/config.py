"""Config de Raphael Scout — BYOM ("bring your own model", SPEC decisión #3).

Scout tiene su PROPIA config de modelo, independiente del Raphael grande: podés
apuntar Scout a un endpoint/modelo distinto (ej. Groq free) sin tocar el modelo
del monolito. Lee variables `SCOUT_LLM_*` del entorno y, si no están, cae a la
config del núcleo (app.config.settings) — así "funciona sin configurar nada" y
a la vez se puede separar cuando hace falta.

Variables (todas opcionales):
  SCOUT_LLM_BASE_URL     endpoint OpenAI-compatible  (fallback: LMSTUDIO_BASE_URL)
  SCOUT_LLM_API_KEY      api key                     (fallback: LLM_API_KEY)
  SCOUT_LLM_MODEL        nombre del modelo           (fallback: LMSTUDIO_MODEL)
  SCOUT_CAPTURE_DIR      carpeta de archivos fs_*    (fallback: RESEARCH_WORKING_DIR)
  SCOUT_VAULT_PATH       vault de Obsidian de Scout  (fallback: RESEARCH_VAULT_PATH)
  SCOUT_EMBEDDINGS_PATH  embeddings de ese vault     (fallback: RESEARCH_EMBEDDINGS_PATH)
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from openai import AsyncOpenAI

from app.config import settings


@dataclass(frozen=True)
class ScoutConfig:
    base_url: str
    api_key: str
    model: str
    capture_dir: str
    vault_path: str
    embeddings_path: str
    timeout_seconds: float


def load_scout_config() -> ScoutConfig:
    return ScoutConfig(
        base_url=os.getenv("SCOUT_LLM_BASE_URL", settings.lmstudio_base_url),
        api_key=os.getenv("SCOUT_LLM_API_KEY", settings.llm_api_key),
        model=os.getenv("SCOUT_LLM_MODEL", settings.lmstudio_model),
        capture_dir=os.getenv("SCOUT_CAPTURE_DIR", settings.research_working_dir),
        vault_path=os.getenv("SCOUT_VAULT_PATH", settings.research_vault_path),
        embeddings_path=os.getenv("SCOUT_EMBEDDINGS_PATH", settings.research_embeddings_path),
        timeout_seconds=settings.llm_request_timeout_seconds,
    )


def build_client(cfg: ScoutConfig) -> AsyncOpenAI:
    """Cliente async OpenAI-compatible de Scout. max_retries=2 (a diferencia del
    cliente del núcleo, que es local y usa 0): Scout suele hablar con una API en
    la nube donde un 429/503 transitorio sí vale la pena reintentarlo."""
    return AsyncOpenAI(
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        timeout=cfg.timeout_seconds,
        max_retries=2,
    )
