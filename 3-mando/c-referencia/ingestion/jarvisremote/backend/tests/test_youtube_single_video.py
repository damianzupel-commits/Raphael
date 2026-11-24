"""Tests del ingester de UN video suelto (app/ingestion/youtube_playlist.py::ingest_video).

Mockean las funciones de red/LLM/vault a nivel módulo, así se prueba la orquestación
de `ingest_video` (parseo de URL, dedup, delegación al pipeline compartido) sin tocar
YouTube, el LLM ni el vault reales. El procesamiento por-video (`_process_entry`) ya
está cubierto indirectamente por los tests de playlist."""

import asyncio

from app.ingestion import youtube_playlist as yt


def test_ingest_video_url_invalida(monkeypatch):
    # fetch_video_entry no pudo sacar un video_id -> se reporta como error, no rompe
    monkeypatch.setattr(yt, "fetch_video_entry", lambda u: None)
    res = asyncio.run(yt.ingest_video("no-es-una-url"))
    assert res.created == []
    assert res.transcript_errors and "video_id" in res.transcript_errors[0]["error"]


def test_ingest_video_ya_presente_no_reprocesa(monkeypatch):
    monkeypatch.setattr(yt, "fetch_video_entry", lambda u: yt.VideoEntry("abc12345678", "Un video"))
    monkeypatch.setattr(yt, "existing_video_ids", lambda: {"abc12345678"})
    llamado = {"process": False}

    async def _nope(*a, **k):
        llamado["process"] = True

    monkeypatch.setattr(yt, "_process_entry", _nope)
    res = asyncio.run(yt.ingest_video("https://youtu.be/abc12345678"))
    assert res.already_present == ["abc12345678"]
    assert res.created == []
    assert llamado["process"] is False  # idempotente: ni lo procesa


def test_ingest_video_feliz_delega_al_pipeline(monkeypatch):
    monkeypatch.setattr(yt, "fetch_video_entry", lambda u: yt.VideoEntry("abc12345678", "Un video", "Canal"))
    monkeypatch.setattr(yt, "existing_video_ids", lambda: set())
    procesados = []

    async def fake_process(entry, topics, min_rel, result):
        procesados.append(entry.video_id)
        result.created.append(
            {"video_id": entry.video_id, "note_id": "n1", "title": entry.title,
             "relevancia": "útil", "relevancia_score": 4}
        )

    monkeypatch.setattr(yt, "_process_entry", fake_process)
    res = asyncio.run(yt.ingest_video("https://www.youtube.com/watch?v=abc12345678"))
    assert procesados == ["abc12345678"]
    assert len(res.created) == 1
    assert res.total_in_playlist == 1


def test_ingest_video_force_reprocesa_aunque_exista(monkeypatch):
    monkeypatch.setattr(yt, "fetch_video_entry", lambda u: yt.VideoEntry("abc12345678", "Un video"))
    monkeypatch.setattr(yt, "existing_video_ids", lambda: {"abc12345678"})
    procesados = []

    async def fake_process(entry, topics, min_rel, result):
        procesados.append(entry.video_id)

    monkeypatch.setattr(yt, "_process_entry", fake_process)
    res = asyncio.run(yt.ingest_video("https://youtu.be/abc12345678", force=True))
    assert procesados == ["abc12345678"]  # con force sí reprocesa
    assert res.already_present == []
