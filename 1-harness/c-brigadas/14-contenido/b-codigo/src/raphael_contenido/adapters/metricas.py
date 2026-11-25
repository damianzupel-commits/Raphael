"""Métricas de Instagram (solo lectura): publicaciones recientes con sus números. Adaptador real (Graph API), simulado y sin clave.

NO probado contra Meta real. Los nombres de las métricas de `insights` cambian entre versiones de la API: van en la config
(`analytics.insight_metrics`) y, si Meta rechaza alguna para una publicación, se anota y se sigue con las que sí dan.
"""

from __future__ import annotations

import urllib.parse

from .http import Http, ServicioError, mask
from .http import http as real_http

FIELDS = "id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count"


class MetricasGraph:
    mode = "real"

    def __init__(self, user_id: str, token: str, version: str = "v21.0", *, http: Http = real_http,
                 insight_metrics: tuple[str, ...] = ("reach", "saved", "shares")) -> None:
        self.user_id, self.token = user_id, token
        self.base = f"https://graph.facebook.com/{version or 'v21.0'}"
        self._http, self.insight_metrics = http, insight_metrics

    def _get(self, path: str, **params: str) -> dict:
        q = urllib.parse.urlencode({**params, "access_token": self.token})
        try:
            return self._http("GET", f"{self.base}/{path}?{q}")
        except ServicioError as exc:
            raise ServicioError(mask(str(exc), self.token)) from None

    def snapshot(self, limit: int = 25) -> dict:
        acct = self._get(self.user_id, fields="username,followers_count,media_count")
        media = self._get(f"{self.user_id}/media", fields=FIELDS, limit=str(limit)).get("data", [])
        posts, notes = [], []
        for m in media:
            row = {k: m.get(k) for k in ("id", "caption", "media_type", "media_product_type", "timestamp", "permalink",
                                          "like_count", "comments_count")}
            for metric in self.insight_metrics:
                try:
                    data = self._get(f"{m['id']}/insights", metric=metric).get("data", [])
                    row[metric] = data[0]["values"][0]["value"] if data else None
                except (ServicioError, KeyError, IndexError) as exc:
                    row[metric] = None
                    note = f"{metric}: {str(exc)[:120]}"
                    if note not in notes:
                        notes.append(note)
            posts.append(row)
        return {"cuenta": {k: acct.get(k) for k in ("username", "followers_count", "media_count")}, "publicaciones": posts,
                "avisos": notes, "simulado": False}


class MetricasMock:
    """Datos de ejemplo MARCADOS como simulados (nunca se confunden con los reales)."""

    mode = "mock"

    def __init__(self, posts: list[dict] | None = None) -> None:
        self.posts = posts if posts is not None else [
            {"id": "sim-1", "caption": "Detrás de escena del taller", "media_type": "VIDEO", "media_product_type": "REELS",
             "timestamp": "2026-11-20T15:00:00+0000", "permalink": "https://example.invalid/sim-1", "like_count": 120,
             "comments_count": 14, "reach": 2400, "saved": 30, "shares": 12},
            {"id": "sim-2", "caption": "Vestido de novia, prueba final", "media_type": "VIDEO", "media_product_type": "REELS",
             "timestamp": "2026-11-18T15:00:00+0000", "permalink": "https://example.invalid/sim-2", "like_count": 310,
             "comments_count": 41, "reach": 6100, "saved": 95, "shares": 40},
            {"id": "sim-3", "caption": "Telas nuevas", "media_type": "IMAGE", "media_product_type": "FEED",
             "timestamp": "2026-11-15T15:00:00+0000", "permalink": "https://example.invalid/sim-3", "like_count": 45,
             "comments_count": 3, "reach": 800, "saved": 4, "shares": 1},
        ]

    def snapshot(self, limit: int = 25) -> dict:
        return {"cuenta": {"username": "cuenta_simulada", "followers_count": 1234, "media_count": len(self.posts)},
                "publicaciones": self.posts[:limit], "avisos": [], "simulado": True}


class MetricasSinClave:
    mode = "sin_clave"

    def snapshot(self, limit: int = 25) -> dict:
        raise ServicioError("Faltan IG_USER_ID e IG_ACCESS_TOKEN: sin la cuenta conectada no hay métricas que leer.")
