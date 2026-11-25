"""Credenciales de sitios web para `web_login`.

Las contraseñas NUNCA pasan por un chat, por el modelo ni por el repo: Damián las pone en variables de entorno (o en el
archivo de claves del servidor) y la brigada las lee al momento de iniciar sesión. El modelo nunca las ve: `web_login`
las inyecta directo en el navegador y el registro las tacha.

Para el sitio `tradingview.com` las variables son:
    OPERACIONES_CRED_TRADINGVIEW_COM_USUARIO
    OPERACIONES_CRED_TRADINGVIEW_COM_CLAVE
(el dominio en mayúsculas, con todo lo que no sea letra o número cambiado por `_`). Solo se usan los sitios que además
estén en `web_login_permitidos`.

Cambio respecto de JarvisRemote: se sacó `web_credential_save` (guardar una contraseña que el modelo recibía por el
chat y cifraba con DPAPI). Una contraseña que pasa por el modelo ya se filtró; acá se carga a mano, afuera de Raphael.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Protocol


def site_key(site: str) -> str:
    return re.sub(r"[^A-Z0-9]", "_", site.strip().lower().lstrip(".").upper())


class CredentialStore(Protocol):
    def sites(self, allowed: tuple[str, ...]) -> list[dict]: ...
    def get(self, site: str) -> dict | None: ...


class EnvCredentials:
    def __init__(self, env: Mapping[str, str]) -> None:
        self.env = env

    def get(self, site: str) -> dict | None:
        key = site_key(site)
        user = self.env.get(f"OPERACIONES_CRED_{key}_USUARIO")
        password = self.env.get(f"OPERACIONES_CRED_{key}_CLAVE")
        return {"site": site, "username": user, "password": password} if user and password else None

    def sites(self, allowed: tuple[str, ...]) -> list[dict]:
        """Los sitios permitidos que tienen credencial cargada (sitio y usuario; nunca la clave)."""
        out = []
        for site in allowed:
            cred = self.get(site)
            if cred:
                out.append({"site": site, "username": cred["username"]})
        return out


class MockCredentials:
    """Credenciales de mentira para los tests: `{sitio: (usuario, clave)}`."""

    def __init__(self, creds: dict[str, tuple[str, str]] | None = None) -> None:
        self.creds = dict(creds or {})

    def get(self, site: str) -> dict | None:
        c = self.creds.get(site)
        return {"site": site, "username": c[0], "password": c[1]} if c else None

    def sites(self, allowed: tuple[str, ...]) -> list[dict]:
        return [{"site": s, "username": self.creds[s][0]} for s in allowed if s in self.creds]
