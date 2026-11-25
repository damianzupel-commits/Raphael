"""Anuncios (Meta Ads): crear la campaña en PAUSA, y activarla (esto último gasta plata y siempre lo aprueba una persona).

Adaptador real, simulado y sin clave. El real crea solo la CAMPAÑA (`POST act_<cuenta>/campaigns`, estado PAUSED): el conjunto
de anuncios (segmentación y presupuesto) y el anuncio se terminan de armar en el Administrador de anuncios con el borrador que
exporta el cocinero. NO probado contra Meta real; el modelo de objetivos de la API cambia: el objetivo va en la config.
"""

from __future__ import annotations

import urllib.parse

from .http import Http, ServicioError, mask
from .http import http as real_http


class AnunciosMeta:
    mode = "real"

    def __init__(self, account_id: str, token: str, version: str = "v21.0", *, http: Http = real_http) -> None:
        self.account_id = account_id.removeprefix("act_")
        self.token = token
        self.base = f"https://graph.facebook.com/{version or 'v21.0'}"
        self._http = http

    def _post(self, path: str, data: dict) -> dict:
        try:
            return self._http("POST", f"{self.base}/{path}", data={**data, "access_token": self.token})
        except ServicioError as exc:
            raise ServicioError(mask(str(exc), self.token)) from None

    def create_paused(self, name: str, objective: str) -> dict:
        r = self._post(f"act_{self.account_id}/campaigns", {"name": name, "objective": objective, "status": "PAUSED",
                                                             "special_ad_categories": "[]"})
        if not r.get("id"):
            raise ServicioError(f"Meta no devolvió el id de la campaña: {str(r)[:200]}")
        return {"campaign_id": r["id"], "status": "PAUSED", "simulado": False}

    def activate(self, campaign_id: str) -> dict:
        if not urllib.parse.quote(campaign_id).isalnum():
            raise ServicioError("Id de campaña inválido.")
        r = self._post(campaign_id, {"status": "ACTIVE"})
        if not r.get("success", True):
            raise ServicioError(f"Meta no activó la campaña: {str(r)[:200]}")
        return {"campaign_id": campaign_id, "status": "ACTIVE", "simulado": False}


class AnunciosMock:
    mode = "mock"

    def __init__(self) -> None:
        self.campaigns: dict[str, dict] = {}

    def create_paused(self, name: str, objective: str) -> dict:
        cid = f"sim-camp-{len(self.campaigns) + 1}"
        self.campaigns[cid] = {"name": name, "objective": objective, "status": "PAUSED"}
        return {"campaign_id": cid, "status": "PAUSED", "simulado": True}

    def activate(self, campaign_id: str) -> dict:
        if campaign_id not in self.campaigns:
            raise ServicioError("Esa campaña no existe.")
        self.campaigns[campaign_id]["status"] = "ACTIVE"
        return {"campaign_id": campaign_id, "status": "ACTIVE", "simulado": True}


class AnunciosSinClave:
    mode = "sin_clave"

    def create_paused(self, name: str, objective: str) -> dict:
        raise ServicioError("Faltan META_ADS_ACCOUNT_ID y META_ADS_ACCESS_TOKEN: el borrador queda guardado y se puede cargar a mano.")

    def activate(self, campaign_id: str) -> dict:
        return self.create_paused("", "")
