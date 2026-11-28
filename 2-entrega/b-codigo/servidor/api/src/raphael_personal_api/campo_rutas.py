"""Los endpoints de la captura de campo (`/api/v1/campo/*`). La lógica está en `campo.py`; acá solo se traduce a HTTP.

Todo pide sesión, igual que el resto de la API. El audio y las fotos entran como cuerpo crudo (el celular los manda tal cual
salen de la cámara o del micrófono) y los datos van en la URL. Sin carpeta de captura, todo responde 503 diciendo por qué.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field

from . import campo as c


class NegocioIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)


class NotaIn(BaseModel):
    negocio: str
    texto: str = Field(min_length=1, max_length=c.MAX_TEXTO)
    tema: str = "auto"


class CierreIn(BaseModel):
    negocio: str
    cosas: list[str] = Field(min_length=1, max_length=3)
    dia: str | None = None


class CambioIn(BaseModel):
    negocio: str
    texto: str | None = Field(None, max_length=c.MAX_TEXTO)
    tema: str | None = None


class PreguntaIn(BaseModel):
    negocio: str
    pregunta: str = Field(min_length=2, max_length=500)


def router(campo: c.Campo | None, session: Callable[..., dict],
           voz: Callable[[], Awaitable[Any]] | None, ask: Callable[[list[dict]], str | None]) -> APIRouter:
    r = APIRouter(prefix="/api/v1/campo", dependencies=[Depends(session)])

    def store() -> c.Campo:
        if campo is None:
            raise HTTPException(503, "la captura de campo no tiene carpeta donde guardar (falta el archivo de datos)")
        return campo

    def ok(fn: Callable[[], Any]) -> Any:
        try:
            return fn()
        except c.CampoError as exc:
            raise HTTPException(422, str(exc)) from None

    async def preguntar_ia(msgs: list[dict]) -> str | None:
        return await asyncio.to_thread(ask, msgs)

    @r.get("")
    async def estado() -> dict:
        s = store()
        return {"temas": c.TEMAS, "negocios": s.negocios(), "voz": voz is not None}

    @r.post("/negocios")
    async def crear(b: NegocioIn) -> dict:
        return ok(lambda: store().crear_negocio(b.nombre))

    @r.post("/nota")
    async def nota(b: NotaIn) -> dict:
        return ok(lambda: store().agregar(b.negocio, texto=b.texto, tema=b.tema))

    @r.post("/foto")
    async def foto(request: Request, negocio: str, tema: str = "auto", texto: str = "") -> dict:
        data = await request.body()
        mime = request.headers.get("content-type", "")
        return ok(lambda: store().agregar(negocio, texto=texto, tema=tema, fuente="foto", media=data, mime=mime))

    @r.post("/voz")
    async def nota_voz(request: Request, negocio: str, tema: str = "auto") -> dict:
        """Guarda el audio y, si hay voz instalada, lo transcribe ya; si no, queda `sin_transcribir` y se reintenta."""
        data = await request.body()
        mime = request.headers.get("content-type", "")
        n = ok(lambda: store().agregar(negocio, fuente="voz", media=data, mime=mime, tema=tema, estado="sin_transcribir"))
        return await _transcribir(n, negocio, data, n["archivo"][n["archivo"].rfind("."):], tema)

    async def _transcribir(n: dict, negocio: str, data: bytes, suffix: str, tema: str) -> dict:
        if voz is None:
            return {**n, "aviso": "audio guardado; la voz no está instalada, se transcribe cuando esté"}
        try:
            texto = ((await (await voz()).transcribe(data, suffix)).get("texto") or "").strip()
        except Exception as exc:  # noqa: BLE001 - SpeechError y fallas del subproceso: el audio ya está a salvo
            return {**n, "aviso": "audio guardado; no se pudo transcribir: " + str(exc)[:200]}
        if not texto:
            return {**n, "aviso": "audio guardado; no se entendió nada"}
        cambios: dict[str, Any] = {"texto": texto, "estado": "ok"}
        if tema == "auto":
            cambios["tema"] = c.elegir_tema(texto)
        n = ok(lambda: store().actualizar(negocio, n["id"], **cambios))
        if tema == "auto":
            n["tema_elegido"] = False
        return n

    @r.post("/transcribir/{nid}")
    async def retranscribir(nid: str, negocio: str) -> dict:
        s = store()
        n = next((x for x in ok(lambda: s.notas(negocio)) if x["id"] == nid), None)
        if n is None or n["fuente"] != "voz":
            raise HTTPException(404, "esa nota de voz no existe")
        p, _ = ok(lambda: s.media(negocio, n["archivo"]))
        return await _transcribir(n, negocio, p.read_bytes(), p.suffix, "auto" if not n["tema_elegido"] else n["tema"])

    @r.post("/cierre")
    async def cierre(b: CierreIn) -> dict:
        return {"notas": ok(lambda: store().cierre(b.negocio, b.cosas, b.dia))}

    @r.patch("/nota/{nid}")
    async def cambiar(nid: str, b: CambioIn) -> dict:
        return ok(lambda: store().actualizar(b.negocio, nid, texto=b.texto, tema=b.tema))

    @r.get("/notas")
    async def notas(negocio: str, dia: str | None = None, tema: str | None = None, q: str | None = None) -> dict:
        s = store()
        if q:
            return ok(lambda: s.buscar(negocio, q))
        ns = ok(lambda: s.notas(negocio, dia=dia, tema=tema))
        return {"total": len(ns), "notas": ns}

    @r.get("/media/{archivo}")
    async def media(archivo: str, negocio: str) -> FileResponse:
        p, mime = ok(lambda: store().media(negocio, archivo))
        return FileResponse(p, media_type=mime, headers={"Cache-Control": "private, no-store"})

    @r.get("/resumen")
    async def resumen(negocio: str, dia: str | None = None, ia: bool = False) -> dict:
        s = store()
        if not ia:
            return ok(lambda: s.resumen(negocio, dia, ask=None))
        msgs: list[list[dict]] = []
        ok(lambda: s.resumen(negocio, dia, ask=lambda m: msgs.append(m), guardar=False))     # junta el pedido
        txt = await preguntar_ia(msgs[0]) if msgs else None
        return ok(lambda: s.resumen(negocio, dia, ask=lambda m: txt))

    @r.post("/preguntar")
    async def preguntar(b: PreguntaIn) -> dict:
        s = store()
        msgs: list[list[dict]] = []
        ok(lambda: s.preguntar(b.negocio, b.pregunta, ask=lambda m: msgs.append(m)))
        txt = await preguntar_ia(msgs[0]) if msgs else None
        return ok(lambda: s.preguntar(b.negocio, b.pregunta, ask=lambda m: txt))

    @r.get("/expediente", response_class=PlainTextResponse)
    async def expediente(negocio: str) -> PlainTextResponse:
        return PlainTextResponse(ok(lambda: store().expediente(negocio)), media_type="text/markdown; charset=utf-8",
                                 headers={"Cache-Control": "no-store"})

    return r
