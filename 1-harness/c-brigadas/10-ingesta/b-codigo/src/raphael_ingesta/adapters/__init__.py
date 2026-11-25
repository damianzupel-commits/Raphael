"""Adaptadores enchufables: cada fuente tiene uno real (toca la red) y uno simulado (para probar sin red ni claves).
Se elige por configuración (`modo: real | simulado`, global o por fuente). Los tests corren siempre con el simulado."""

from __future__ import annotations

from typing import Protocol

from ..model import Entry, Item


class YouTubeAdapter(Protocol):
    def list_playlist(self, url: str) -> list[Entry]: ...
    def fetch_video(self, video_id: str) -> Item: ...  # levanta NoContent si no tiene subtítulos


class WebAdapter(Protocol):
    def fetch(self, url: str) -> Item: ...


class ArxivAdapter(Protocol):
    def search(self, query: str, limit: int) -> list[Entry]: ...
    def fetch(self, arxiv_id: str) -> Item: ...


def make(source: str, mode: str):
    """El adaptador de una fuente en el modo pedido. Los reales importan sus librerías recién al usarse."""
    if mode == "simulado":
        from . import mock

        return {"youtube": mock.MockYouTube, "web": mock.MockWeb, "arxiv": mock.MockArxiv}[source]()
    if source == "youtube":
        from .youtube import RealYouTube

        return RealYouTube()
    if source == "web":
        from .web import RealWeb

        return RealWeb()
    from .arxiv import RealArxiv

    return RealArxiv()
