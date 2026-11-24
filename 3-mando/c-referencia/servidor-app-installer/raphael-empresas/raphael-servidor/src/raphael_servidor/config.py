"""Configuración del servidor de un cliente. Todo sale de variables de entorno (o de un archivo .env en la carpeta de datos).

Carpeta de datos (RAPHAEL_DIR):
    perfil.yaml        el perfil de la empresa
    raphael.sqlite     los datos (harness + brigadas)
    servidor.json      secretos locales (clave de la dueña hasheada, firma de sesiones, id de instalación)
    backups/           copias diarias de la base
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _leer_env(carpeta: Path) -> dict[str, str]:
    archivo = carpeta / ".env"
    out: dict[str, str] = {}
    if archivo.exists():
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                v = v.strip()
                if v[:1] not in "\"'":                   # RAPHAEL_MODO=mock   # comentario  →  mock
                    v = v.split(" #", 1)[0].strip()
                out[k.strip()] = v.strip('"').strip("'")
    return out


@dataclass
class Config:
    dir: Path
    modo: str = "mock"                     # mock: no manda nada afuera · real: WhatsApp/Instagram de verdad
    dev: str = ""                          # carpeta con los repos raphael-* (desarrollo)
    piezas: str = ""                       # carpeta donde viven las piezas instaladas (tienda de brigadas)
    fuente_repos: str = ""                 # de dónde se descargan, ej. https://github.com/damianzupel-commits
    fuente_local: str = ""                 # alternativa: carpeta con copias de los repos
    relay_url: str = ""
    relay_token: str = ""
    central_url: str = ""
    licencia: str = ""
    whatsapp_token: str = ""
    whatsapp_phone_id: str = ""
    instagram_token: str = ""
    meta_app_secret: str = ""
    meta_verify_token: str = ""
    meta_graph: str = "v21.0"
    clave_backup: str = ""                 # clave Fernet para cifrar backups (opcional)
    tareas: bool = True                    # hilos de fondo (tick, relay, licencia, latido, backup)
    extra: dict = field(default_factory=dict)

    @property
    def perfil(self) -> Path:
        return self.dir / "perfil.yaml"

    @property
    def base(self) -> Path:
        return self.dir / "raphael.sqlite"

    @property
    def secretos(self) -> Path:
        return self.dir / "servidor.json"

    @property
    def backups(self) -> Path:
        return self.dir / "backups"

    @classmethod
    def desde_entorno(cls, carpeta: str | Path | None = None, **sobre) -> "Config":
        d = Path(carpeta or os.environ.get("RAPHAEL_DIR", "datos")).resolve()
        env = {**_leer_env(d), **os.environ}
        g = lambda k, por=None: env.get(k, por if por is not None else "")  # noqa: E731
        c = cls(dir=d, modo=g("RAPHAEL_MODO", "mock"), dev=g("RAPHAEL_DEV"), piezas=g("RAPHAEL_PIEZAS"),
                fuente_repos=g("RAPHAEL_FUENTE_REPOS"), fuente_local=g("RAPHAEL_FUENTE_LOCAL"), relay_url=g("RAPHAEL_RELAY_URL"),
                relay_token=g("RAPHAEL_RELAY_TOKEN"), central_url=g("RAPHAEL_CENTRAL_URL"), licencia=g("RAPHAEL_LICENCIA"),
                whatsapp_token=g("WHATSAPP_TOKEN"), whatsapp_phone_id=g("WHATSAPP_PHONE_ID"),
                instagram_token=g("INSTAGRAM_TOKEN"), meta_app_secret=g("META_APP_SECRET"),
                meta_verify_token=g("META_VERIFY_TOKEN"), meta_graph=g("META_GRAPH_VERSION", "v21.0"),
                clave_backup=g("RAPHAEL_CLAVE_BACKUP"), tareas=g("RAPHAEL_TAREAS", "1") != "0")
        for k, v in sobre.items():
            setattr(c, k, v)
        return c
