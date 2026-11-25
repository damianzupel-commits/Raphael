"""Qué toma la brigada de la config de la instalación y del entorno (las claves y rutas nunca van al repo)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ENV_VARS = ("SEGURIDAD_ADVISORIES", "SEGURIDAD_REPOS", "SEGURIDAD_TARGETS_FILE", "SEGURIDAD_PENTEST_ADAPTER", "SEGURIDAD_WATCH_ADAPTER",
            "NMAP_PATH", "SQLMAP_PATH", "ZAP_URL", "ZAP_API_KEY")


@dataclass
class Settings:
    repos: list[str] = field(default_factory=list)       # solo estos repos se pueden auditar (los autoriza Damián)
    targets_file: str | None = None
    watch: dict = field(default_factory=dict)
    env: dict = field(default_factory=dict)

    @staticmethod
    def build(config: dict | None, env: dict | None = None) -> Settings:
        cfg, env = config or {}, dict(os.environ if env is None else env)
        return Settings(repos=[str(r) for r in cfg.get("repos") or [r for r in env.get("SEGURIDAD_REPOS", "").split(os.pathsep) if r]],
                        targets_file=cfg.get("targets_file") or env.get("SEGURIDAD_TARGETS_FILE") or None,
                        watch=dict(cfg.get("watch") or {}), env={k: env[k] for k in ENV_VARS if k in env})

    def allowed_repo(self, repo: str) -> Path:
        """Devuelve la ruta solo si está en la lista de Damián. Nada de rutas libres: el modelo no elige qué leer."""
        want = Path(repo).resolve()
        for r in self.repos:
            if Path(r).resolve() == want:
                return want
        raise PermissionError(f"el repo {repo!r} no está en la lista de repos autorizados de la config")


def validate_config(config: dict) -> str | None:
    for key, kind in (("repos", list), ("watch", dict)):
        if key in config and not isinstance(config[key], kind):
            return f"'{key}' tiene que ser {'una lista' if kind is list else 'un objeto'}"
    if "targets_file" in config and not isinstance(config["targets_file"], str):
        return "'targets_file' tiene que ser texto (ruta)"
    return None
