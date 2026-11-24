"""Ingesta de información directa de internet hacia el vault: fetch -> chunk ->
embeber -> indexar (ver docs/SPEC-estructura-informacional-cerebro.md y
docs/SPEC-RAPHAEL-INTEL.md).

Es la "biblioteca para IA a escala personal" que pidió Damian (2026-10-04): le das
una URL y Raphael la trae, la parte en pedazos, embebe cada pedazo con el modelo de
embeddings local (nomic :1234) y lo guarda en el vault como notas enlazadas. A
partir de ahí el pedazo es recuperable por búsqueda semántica Y por spreading
activation (porque queda cableado al grafo).

A DIFERENCIA de `ingestion/base.py` (que resume con el LLM de chat), acá NO se llama
a ningún modelo de chat: solo fetch (web_get, que ya escala solo) + embeddings. Es
tier 0 + embeddings: barato, rápido, sin gastar el presupuesto del modelo caro. El
texto crudo se guarda tal cual (provenance §3.3 del spec): la fuente queda como
ancla verificable, la reconstrucción flexible la hace después el LLM al recuperar.

El chunker (`chunk_text`) es una función pura, testeable sin red ni vault.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone

from . import embeddings, vault

# Tamaño de chunk en caracteres. ~1500 es un punto medio razonable para embeddings:
# suficiente contexto por vector, sin diluir el significado en bloques enormes.
_CHUNK_SIZE = 1500
_CHUNK_OVERLAP = 200  # solape para no cortar una idea justo en el borde
_MAX_TOTAL_CHARS = 200_000  # tope duro por página (evita reventar con un PDF/HTML gigante)
_PARA_SPLIT = re.compile(r"\n\s*\n")  # separa por párrafos (doble salto de línea)


def _norm(text: str) -> str:
    """Normaliza whitespace sin perder los saltos de párrafo (para chunkear por ellos)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> list[str]:
    """Parte el texto en chunks de ~`size` caracteres respetando párrafos cuando se
    puede, con `overlap` de solape entre chunks consecutivos. Función PURA.

    Acumula párrafos hasta pasar `size`; un párrafo más largo que `size` se corta
    duro por caracteres. Nunca devuelve chunks vacíos."""
    text = _norm(text)[:_MAX_TOTAL_CHARS]
    if not text:
        return []
    paras = [p.strip() for p in _PARA_SPLIT.split(text) if p.strip()]

    chunks: list[str] = []
    buf = ""
    for p in paras:
        if len(p) > size:
            # párrafo gigante: vacío el buffer y lo corto duro con solape
            if buf:
                chunks.append(buf)
                buf = ""
            for i in range(0, len(p), size - overlap):
                chunks.append(p[i : i + size])
            continue
        if buf and len(buf) + 1 + len(p) > size:
            chunks.append(buf)
            # arranco el próximo con el solape final del anterior
            buf = (buf[-overlap:] + "\n\n" + p) if overlap else p
        else:
            buf = f"{buf}\n\n{p}" if buf else p
    if buf:
        chunks.append(buf)
    return [c.strip() for c in chunks if c.strip()]


def _ingest_id(url: str) -> str:
    """ID estable de la página (para dedup y para marcar los chunks)."""
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def _page_title(text: str, url: str) -> str:
    """Título de la página: primera línea con sustancia, o el path de la URL."""
    for line in text.splitlines():
        line = line.strip()
        if len(line) >= 12:
            return line[:90]
    from urllib.parse import urlparse

    p = urlparse(url)
    return f"{p.netloc}{p.path}".strip("/")[:90] or url[:90]


def _domain(url: str) -> str:
    from urllib.parse import urlparse

    return urlparse(url).netloc.replace("www.", "")


def _existing_ingest_ids() -> set[str]:
    """IDs de páginas ya ingeridas (marcadas en el cuerpo de las notas jarvis).
    Hace idempotente la ingesta: re-ingerir la misma URL no duplica."""
    ids: set[str] = set()
    rx = re.compile(r"web-ingest-id:\s*([0-9a-f]{12})")
    for note in vault.list_notes(author="jarvis"):
        for m in rx.finditer(note.content):
            ids.add(m.group(1))
    return ids


def _chunk_note_content(chunk: str, idx: int, total: int, url: str, ing_id: str, titulo: str, fetched: str) -> str:
    """Markdown de la nota-chunk: el texto CRUDO + provenance (fuente verificable)."""
    return "\n".join([
        chunk,
        "",
        "## Fuente",
        f"- origen: web (ingesta directa)",
        f"- url: {url}",
        f"- traído: {fetched}",
        f"- fragmento: {idx + 1}/{total}",
        f"- web-ingest-id: {ing_id}",
        "",
        "## Notas relacionadas",
        f"- [[Web: {titulo}]]",
    ])


def ingest_url(
    url: str,
    *,
    fresh: bool = False,
    categoria: str = "web",
    web_get_fn=None,
    save_note=None,
    embed=None,
) -> dict:
    """Trae `url`, la parte en chunks, embebe cada uno y lo guarda en el vault.

    Todo lo externo (web_get, save_note, embed) es inyectable para testear sin red,
    vault ni LM Studio. Idempotente: si la URL ya se ingirió, no la duplica.
    Devuelve un resumen con qué se creó y cuántos chunks quedaron embebidos."""
    from ..tools.web_get import web_get as _web_get

    web_get_fn = web_get_fn or _web_get
    save_note = save_note or vault.save_note
    embed = embed or embeddings.update_note_embedding

    ing_id = _ingest_id(url)
    if ing_id in _existing_ingest_ids() and not fresh:
        return {"url": url, "status": "ya_ingerido", "web_ingest_id": ing_id, "chunks_creados": 0}

    page = web_get_fn(url, fresh=fresh, max_chars=_MAX_TOTAL_CHARS)
    if not isinstance(page, dict) or page.get("error"):
        return {"url": url, "status": "error_fetch", "error": (page or {}).get("error", "sin texto")}
    text = page.get("text") or ""
    if not text.strip():
        return {"url": url, "status": "sin_texto", "error": "la página no devolvió texto"}

    chunks = chunk_text(text)
    if not chunks:
        return {"url": url, "status": "sin_chunks"}

    titulo = _page_title(text, url)
    dominio = _domain(url)
    fetched = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    creados, embebidos, errores = [], 0, []

    for idx, chunk in enumerate(chunks):
        try:
            content = _chunk_note_content(chunk, idx, len(chunks), url, ing_id, titulo, fetched)
            note = save_note(
                title=f"{titulo} [{idx + 1}/{len(chunks)}]",
                content=content,
                author="jarvis",
                tags=["web", "ingesta", dominio, categoria],
                category=categoria,
                extra={"origen": "web", "url": url, "web_ingest_id": ing_id, "fragmento": idx + 1},
            )
            nid = getattr(note, "id", None)
            # embeber el CHUNK crudo (no la provenance) para que el vector sea del contenido
            try:
                embed(nid, chunk)
                embebidos += 1
            except Exception as exc:  # noqa: BLE001 -- sin LM Studio la nota igual queda, se reindexará
                errores.append({"fragmento": idx + 1, "error": f"embed: {type(exc).__name__}: {exc}"})
            creados.append({"note_id": nid, "fragmento": idx + 1})
        except Exception as exc:  # noqa: BLE001
            errores.append({"fragmento": idx + 1, "error": f"{type(exc).__name__}: {exc}"})

    # Centro de Mando (2026-10-13): registra la fuente web ingerida para la brigada Ingesta
    # ("ingerido recientemente"). Solo si de verdad se creó algo nuevo. Best-effort.
    if creados:
        try:
            from ..ingestion import sources

            sources.log_ingested(titulo, url, "web")
        except Exception:  # noqa: BLE001
            pass

    return {
        "url": url,
        "status": "ok",
        "titulo": titulo,
        "web_ingest_id": ing_id,
        "chunks_creados": len(creados),
        "chunks_embebidos": embebidos,
        "errores": errores,
        "nota": (
            "Chunks embebidos con el modelo local (nomic). Recuperables por "
            "obsidian_search_notes y por obsidian_buscar_asociativo (spreading)."
            if embebidos
            else "OJO: 0 chunks embebidos -- ¿está LM Studio (:1234) con el modelo cargado? "
            "Las notas quedaron guardadas; corré un reindex cuando vuelva."
        ),
    }
