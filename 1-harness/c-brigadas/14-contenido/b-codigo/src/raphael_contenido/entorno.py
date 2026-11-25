"""Variables de entorno de la brigada y armado de los adaptadores.

`VARIABLES` es la lista única de lo que la brigada lee del entorno: de ahí sale `.env.plantilla` (un test verifica que estén
todas) y la lista de `3-mando/a-conocimiento/LIENZO-DAMIAN.md`. Las claves se leen acá y en ningún otro lado; nunca se
imprimen ni se guardan (los errores las tachan).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from . import adapters as ad
from .adapters.http import Http
from .adapters.http import http as real_http
from .config import ContenidoConfig

#: nombre -> (para qué, es clave/dato personal)
VARIABLES: dict[str, tuple[str, bool]] = {
    "CONTENIDO_MODO": ("`mock` fuerza todo simulado (demo y pruebas); vacío = real si están las claves", False),
    "IG_USER_ID": ("id numérico de la cuenta profesional de Instagram", True),
    "IG_ACCESS_TOKEN": ("token de acceso de Meta con permiso de publicar y leer métricas", True),
    "IG_GRAPH_VERSION": ("versión de la Graph API (por defecto v21.0)", False),
    "META_ADS_ACCOUNT_ID": ("id de la cuenta publicitaria (act_...)", True),
    "META_ADS_ACCESS_TOKEN": ("token con permiso de ads_management", True),
    "COMFYUI_URL": ("dirección de ComfyUI en esta PC (por defecto http://127.0.0.1:8188)", False),
    "COMFYUI_OUTPUT_DIR": ("carpeta `output` de ComfyUI, de donde se leen las imágenes y videos generados", False),
    "VIDEO_EDIT_DIR": ("carpeta fija de trabajo de video (entrada/ y salida/); por defecto Documentos/Videos-Raphael", False),
    "VIDEO_FFMPEG_PATH": ("ruta de ffmpeg si no está en el PATH", False),
    "VIDEO_FFMPEG_THREADS": ("hilos de ffmpeg (por defecto la mitad de los núcleos, hasta 4)", False),
    "VIDEO_FFMPEG_TIMEOUT_SECONDS": ("tope de cada trabajo de ffmpeg (por defecto 1800)", False),
    "VIDEO_WHISPER_MODEL": ("modelo de faster-whisper para transcribir (por defecto small)", False),
    "VIDEO_WHISPER_PYTHON": ("intérprete con faster-whisper, si no es el actual", False),
    "VIDEO_GRABACION_MAX_SECONDS": ("tope de una grabación de pantalla (por defecto 300)", False),
}


@dataclass
class Adaptadores:
    instagram: object
    comfyui: object
    metricas: object
    anuncios: object
    ffmpeg: object

    def modos(self) -> dict[str, str]:
        return {"instagram": self.instagram.mode, "comfyui": self.comfyui.mode, "metricas": self.metricas.mode,
                "anuncios": self.anuncios.mode, "ffmpeg": "mock" if not self.ffmpeg.real else "real"}


def mock_mode(cfg: ContenidoConfig, env: Mapping[str, str]) -> bool:
    return cfg.mode == "mock" or env.get("CONTENIDO_MODO", "").strip().lower() == "mock"


def build(cfg: ContenidoConfig, env: Mapping[str, str] | None = None, *, http: Http = real_http, mock_dir: str | Path | None = None,
          ) -> Adaptadores:
    """Los adaptadores de esta instalación. `mock_dir` = dónde deja ComfyMock sus archivos."""
    from .video.runner import RealRunner, SimulatedRunner

    env = os.environ if env is None else env
    g = lambda k: (env.get(k) or "").strip()  # noqa: E731
    version = g("IG_GRAPH_VERSION") or "v21.0"
    if mock_mode(cfg, env):
        out = Path(mock_dir) if mock_dir else Path(g("VIDEO_EDIT_DIR") or Path.home() / "Documents" / "Videos-Raphael") / "generadas"
        return Adaptadores(ad.InstagramMock(), ad.ComfyMock(out), ad.MetricasMock(), ad.AnunciosMock(), SimulatedRunner())
    ig = (ad.InstagramGraph(g("IG_USER_ID"), g("IG_ACCESS_TOKEN"), version, http=http)
          if g("IG_USER_ID") and g("IG_ACCESS_TOKEN") else ad.InstagramSinClave())
    met = (ad.MetricasGraph(g("IG_USER_ID"), g("IG_ACCESS_TOKEN"), version, http=http, insight_metrics=cfg.analytics.insight_metrics)
           if g("IG_USER_ID") and g("IG_ACCESS_TOKEN") else ad.MetricasSinClave())
    ads = (ad.AnunciosMeta(g("META_ADS_ACCOUNT_ID"), g("META_ADS_ACCESS_TOKEN"), version, http=http)
           if g("META_ADS_ACCOUNT_ID") and g("META_ADS_ACCESS_TOKEN") else ad.AnunciosSinClave())
    comfy = (ad.ComfyUI(g("COMFYUI_URL") or "http://127.0.0.1:8188", g("COMFYUI_OUTPUT_DIR"), http=http)
             if g("COMFYUI_OUTPUT_DIR") else ad.ComfySinServidor())
    return Adaptadores(ig, comfy, met, ads, RealRunner())


def missing_for_real(env: Mapping[str, str] | None = None) -> dict[str, list[str]]:
    """Qué falta por servicio (para el healthcheck y la pantalla de claves). Solo nombres de variables, nunca valores."""
    env = os.environ if env is None else env
    need = {"instagram y métricas": ["IG_USER_ID", "IG_ACCESS_TOKEN"], "anuncios": ["META_ADS_ACCOUNT_ID", "META_ADS_ACCESS_TOKEN"],
            "imagen y video generados": ["COMFYUI_OUTPUT_DIR"]}
    return {k: [n for n in v if not (env.get(n) or "").strip()] for k, v in need.items() if any(not (env.get(n) or "").strip() for n in v)}


def video_setup(cfg: ContenidoConfig, ad: Adaptadores) -> None:
    """Deja configurado el módulo de video (carpeta fija y quién corre ffmpeg). Lo primero que lo llama gana: los demás cocineros
    que necesitan la carpeta (Instagram, Imagen) lo llaman también y no pisan nada."""
    from .video import edicion

    if edicion._RUNNER is None:  # noqa: SLF001
        edicion.configure(base=cfg.video.dir or None, runner=ad.ffmpeg)
