"""Instagram: publicar un Reel (adaptador real con la Graph API, simulado y "sin clave").

El real usa la carga resumible de Meta en 3 pasos: crear el contenedor, subir los bytes y publicarlo. Credenciales SOLO del
entorno: `IG_USER_ID` e `IG_ACCESS_TOKEN` (cuenta profesional); versión de la API en `IG_GRAPH_VERSION`.
Estado: los pasos están probados con un cliente simulado (portado de JarvisRemote); FALTA una prueba real con la cuenta de Damián.
"""

from __future__ import annotations

import time
import urllib.parse
from collections.abc import Callable
from pathlib import Path

from .http import Http, ServicioError, mask
from .http import http as real_http


class InstagramGraph:
    mode = "real"

    def __init__(self, user_id: str, token: str, version: str = "v21.0", *, http: Http = real_http,
                 sleep: Callable[[float], None] = time.sleep, wait: float = 5.0, tries: int = 60) -> None:
        self.user_id, self.token = user_id, token
        self.base = f"https://graph.facebook.com/{version or 'v21.0'}"
        self._http, self._sleep, self._wait, self._tries = http, sleep, wait, tries

    def check(self) -> str:
        """Lectura inocua para el healthcheck y la pantalla de claves: ¿el token sirve? Devuelve el usuario."""
        r = self._http("GET", f"{self.base}/{self.user_id}?fields=username&access_token={urllib.parse.quote(self.token)}")
        return str(r.get("username") or r.get("id") or "")

    def publish_reel(self, path: Path, caption: str) -> dict:
        try:
            c = self._http("POST", f"{self.base}/{self.user_id}/media",
                           data={"media_type": "REELS", "upload_type": "resumable", "caption": caption, "access_token": self.token})
            cid, uri = c.get("id"), c.get("uri")
            if not cid or not uri:
                raise ServicioError(f"Instagram no devolvió el contenedor de carga: {str(c)[:200]}")
            self._http("POST", uri, headers={"Authorization": f"OAuth {self.token}", "offset": "0", "file_size": str(path.stat().st_size)},
                       body=path.read_bytes(), timeout=600)
            state = ""
            for _ in range(max(1, self._tries)):
                state = str(self._http("GET", f"{self.base}/{cid}?fields=status_code&access_token={urllib.parse.quote(self.token)}")
                            .get("status_code", ""))
                if state in ("FINISHED", "ERROR", "EXPIRED"):
                    break
                self._sleep(self._wait)
            if state != "FINISHED":
                raise ServicioError(f"Instagram no terminó de procesar el video (estado: {state or 'sin respuesta'}).")
            pub = self._http("POST", f"{self.base}/{self.user_id}/media_publish", data={"creation_id": cid, "access_token": self.token})
            if not pub.get("id"):
                raise ServicioError(f"Instagram no confirmó la publicación: {str(pub)[:200]}")
        except ServicioError as exc:
            raise ServicioError(mask(str(exc), self.token)) from None
        return {"media_id": pub["id"], "simulado": False}


class InstagramMock:
    """Instagram de mentira: no sale nada a ningún lado. Anota lo que le pidieron."""

    mode = "mock"

    def __init__(self, fail_with: str | None = None) -> None:
        self.published: list[dict] = []
        self.fail_with = fail_with

    def check(self) -> str:
        return "cuenta_simulada"

    def publish_reel(self, path: Path, caption: str) -> dict:
        if self.fail_with:
            raise ServicioError(self.fail_with)
        self.published.append({"path": str(path), "caption": caption})
        return {"media_id": f"sim-{len(self.published)}", "simulado": True}


class InstagramSinClave:
    """Sin `IG_USER_ID` / `IG_ACCESS_TOKEN`: todo lo demás de la brigada anda, publicar avisa qué falta y la publicación sigue pendiente."""

    mode = "sin_clave"

    def check(self) -> str:
        raise ServicioError("Faltan IG_USER_ID e IG_ACCESS_TOKEN (cuenta profesional de Instagram).")

    def publish_reel(self, path: Path, caption: str) -> dict:
        self.check()
        raise AssertionError("inalcanzable")
