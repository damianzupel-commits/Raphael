"""Configuración de la brigada (`brigades.memoria.config` de la instalación) y su resolución con variables de entorno.

Nada de claves acá: los embeddings corren en la PC (LM Studio u Ollama) y no necesitan. Si algún día se usa una API de
embeddings, la clave se lee de la variable que nombre `api_key_env`, nunca del archivo.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field

LOOPBACK = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VaultConfig(_Base):
    path: str = ""                                   # "" = MEMORIA_VAULT_PATH o <datos>/memoria/vault
    sensitive_dirs: list[str] = Field(default_factory=list)   # carpetas cuyo contenido nunca sale de la PC (ni a un `:free`)
    excluded_dirs: list[str] = Field(default_factory=list)    # carpetas que no se leen (además de las que empiezan con . o _)


class EmbeddingsConfig(_Base):
    provider: str = "auto"                            # auto | local | mock | off
    base_url: str = ""                                # "" = MEMORIA_EMBEDDINGS_BASE_URL o LM Studio (localhost:1234)
    model: str = ""                                   # "" = MEMORIA_EMBEDDINGS_MODEL o nomic-embed-text
    api_key_env: str = ""                             # solo si se usa una API remota
    allow_remote: bool = False                        # sin esto, una base_url que no sea de esta PC se rechaza
    timeout_seconds: float = Field(10.0, gt=0)
    min_semantic_score: float = Field(0.4, ge=0, le=1)   # coseno mínimo para que una nota cuente como relacionada


class ConsolidationConfig(_Base):
    threshold: float = Field(0.85, ge=0, le=1)        # endurecido el 12 nov: 0.6 mezclaba temas (ver test de regresión)
    gap: float | None = Field(0.08, ge=0)
    min_size: int = Field(2, ge=2)
    max_size: int = Field(6, ge=2)
    lookback_days: int = Field(14, ge=1)
    max_clusters_per_run: int = Field(3, ge=1)


class ProactiveConfig(_Base):
    enabled: bool = False                             # apagado por default: escribe notas por su cuenta
    every_minutes: int = Field(180, ge=5)


class EpisodesConfig(_Base):
    enabled: bool = True
    recall_window_hours: int = Field(24, ge=1)


class MemoriaConfig(_Base):
    vault: VaultConfig = VaultConfig()
    embeddings: EmbeddingsConfig = EmbeddingsConfig()
    consolidation: ConsolidationConfig = ConsolidationConfig()
    proactive: ProactiveConfig = ProactiveConfig()
    episodes: EpisodesConfig = EpisodesConfig()


def memoria_config(raw: Mapping | None) -> MemoriaConfig:
    return MemoriaConfig.model_validate(dict(raw or {}))


def is_local_url(url: str) -> bool:
    return (urlparse(url).hostname or "") in LOOPBACK


def vault_path(cfg: MemoriaConfig, env: Mapping[str, str] | None = None) -> Path:
    env = os.environ if env is None else env
    if cfg.vault.path:
        return Path(cfg.vault.path).expanduser()
    # el vault de Ingesta (RAPHAEL_VAULT_DIR) es también el de Memoria salvo que se diga otra cosa
    for var in ("MEMORIA_VAULT_PATH", "RAPHAEL_VAULT_DIR"):
        if env.get(var):
            return Path(env[var]).expanduser()
    return Path(env.get("RAPHAEL_DATA_DIR") or ".data") / "memoria" / "vault"


def embeddings_target(cfg: MemoriaConfig, env: Mapping[str, str] | None = None) -> tuple[str, str]:
    env = os.environ if env is None else env
    e = cfg.embeddings
    return (e.base_url or env.get("MEMORIA_EMBEDDINGS_BASE_URL") or "http://localhost:1234/v1",
            e.model or env.get("MEMORIA_EMBEDDINGS_MODEL") or "text-embedding-nomic-embed-text-v1.5")
