"""Adaptadores simulados: datos fijos, sin red ni claves. Con estos corren todos los tests.

Convenciones para probar los casos difíciles:
- YouTube: el id que empieza con `SINSUBTIT` no tiene subtítulos; `ERRORTECNI` falla con un error de red;
  una lista cualquiera trae 3 videos (`MOCKVID0001`, `MOCKVID0002`, `SINSUBTIT01`).
- Web: una URL con `vacia` en la dirección devuelve una página sin texto.
- arXiv: cualquier búsqueda trae 3 papers fijos."""

from __future__ import annotations

from ..model import Entry, Item, NoContent, SourceError
from ..safeurl import validate_public_url
from .web import web_id

TRANSCRIPT = (
    "Hoy vamos a ver cómo funciona un agente de inteligencia artificial que usa herramientas. "
    "Primero se define el objetivo y después el agente planifica los pasos. "
    "Cada paso puede llamar a una herramienta, como un buscador o una terminal. "
    "Lo importante es que las acciones peligrosas pidan aprobación de una persona. "
    "Al final repasamos los errores más comunes al diseñar agentes y cómo evitarlos."
)
PAGE = (
    "Guía práctica de seguridad para pequeños equipos. La seguridad empieza por conocer qué se tiene expuesto. "
    "Primero hay que inventariar los servicios, después cerrar lo que no se usa y por último vigilar los accesos. "
    "Las contraseñas deben ser largas y únicas, y conviene usar un gestor y doble factor. "
    "Los respaldos se prueban restaurándolos, no solo haciéndolos."
)
PAPERS = (
    (
        "2401.00001",
        "Agentes con memoria de largo plazo",
        "Se propone una memoria episódica para agentes de lenguaje. "
        "Los resultados mejoran en tareas largas. Se discuten límites y costos.",
    ),
    (
        "2401.00002",
        "Detección de intrusiones con aprendizaje federado",
        "Se entrena un detector sin centralizar los datos. La precisión se acerca a la del modelo centralizado.",
    ),
    (
        "2401.00003",
        "Conectómica a escala de cerebro entero",
        "Se presenta un método para reconstruir conexiones neuronales. Se validan los resultados con un conjunto manual.",
    ),
)


class MockYouTube:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def list_playlist(self, url: str) -> list[Entry]:
        self.calls.append(f"list:{url}")
        return [
            Entry(
                source_id=v,
                title=f"Video simulado {v}",
                url=f"https://www.youtube.com/watch?v={v}",
                channel="Canal simulado",
                duration="10:00",
            )
            for v in ("MOCKVID0001", "MOCKVID0002", "SINSUBTIT01")
        ]

    def fetch_video(self, video_id: str) -> Item:
        self.calls.append(f"video:{video_id}")
        if video_id.startswith("SINSUBTIT"):
            raise NoContent("el video no tiene subtítulos en español, inglés ni portugués")
        if video_id.startswith("ERRORTECNI"):
            raise SourceError("YouTube falló: error de red simulado", retriable=True)
        return Item(
            source="youtube",
            source_id=video_id,
            title=f"Video simulado {video_id}",
            url=f"https://www.youtube.com/watch?v={video_id}",
            text=TRANSCRIPT,
            authors=["Canal simulado"],
            published="2026-11-01",
            extra={"duration": "10:00", "lang": "es"},
        )


def _resolve(host, port, **_kw):
    """DNS simulado: los nombres de la red local resuelven a una IP privada, el resto a una pública."""
    private = host == "localhost" or host.endswith(".local") or host.startswith(("127.", "10.", "192.168.", "169.254."))
    return [(2, 1, 6, "", ("127.0.0.1" if private else "93.184.216.34", port))]


class MockWeb:
    """Valida la URL como la real (con DNS simulado) y devuelve una página fija."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch(self, url: str) -> Item:
        self.calls.append(url)
        validate_public_url(url, resolve=_resolve)
        if "vacia" in url:
            raise NoContent("la página casi no tiene texto (puede cargarse con JavaScript)")
        return Item(
            source="web", source_id=web_id(url), title="Guía de seguridad simulada", url=url, text=PAGE, published="2026-10-15"
        )


class MockArxiv:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def _item(self, i: int) -> Item:
        aid, title, abstract = PAPERS[i]
        return Item(
            source="arxiv",
            source_id=aid,
            title=title,
            url=f"https://arxiv.org/abs/{aid}",
            text=abstract,
            authors=["Autora Simulada", "Autor Simulado"],
            published="2026-11-02",
        )

    def search(self, query: str, limit: int) -> list[Entry]:
        self.calls.append(f"search:{query}")
        return [
            Entry(source_id=it.source_id, title=it.title, url=it.url, item=it)
            for it in (self._item(i) for i in range(min(limit, len(PAPERS))))
        ]

    def fetch(self, arxiv_id: str) -> Item:
        self.calls.append(f"fetch:{arxiv_id}")
        for i, p in enumerate(PAPERS):
            if p[0] == arxiv_id:
                return self._item(i)
        raise NoContent(f"arXiv no devolvió el paper {arxiv_id}")
