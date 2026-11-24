"""Tests del ingester de arXiv: parseo del Atom y fetch (con red mockeada)."""

from __future__ import annotations

from app.ingestion.arxiv_source import ArxivSource, parse_atom

_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2401.12345v1</id>
    <title>A Great Paper on Agents</title>
    <summary>  We show that agents are great.  </summary>
    <published>2024-01-15T00:00:00Z</published>
    <author><name>Ada Lovelace</name></author>
    <author><name>Alan Turing</name></author>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2312.99999</id>
    <title>Neurons and Cognition</title>
    <summary>Connectomics stuff.</summary>
    <published>2023-12-01T00:00:00Z</published>
    <author><name>Bob</name></author>
  </entry>
</feed>"""


def test_parse_atom_dos_papers():
    items = parse_atom(_SAMPLE)
    assert len(items) == 2

    a, b = items
    # el id versionado (v1) se normaliza a la base
    assert a.source_id == "2401.12345"
    assert a.title == "A Great Paper on Agents"
    assert a.text == "We show that agents are great."  # colapsa espacios
    assert a.authors == ["Ada Lovelace", "Alan Turing"]
    assert a.published == "2024-01-15"
    assert a.url == "https://arxiv.org/abs/2401.12345"
    assert a.source == "arxiv" and a.domain == "ciencia"

    assert b.source_id == "2312.99999"


def test_parse_atom_basura_no_rompe():
    assert parse_atom("esto no es xml") == []
    assert parse_atom("<feed xmlns='http://www.w3.org/2005/Atom'></feed>") == []


def test_fetch_arma_query_y_parsea():
    captured = {}

    def fake_get(url, timeout=30.0):
        captured["url"] = url
        return _SAMPLE

    src = ArxivSource(http_get=fake_get)
    items = src.fetch("cat:cs.AI", 5)
    assert len(items) == 2
    assert "search_query=" in captured["url"]
    assert "max_results=5" in captured["url"]
    assert "sortBy=submittedDate" in captured["url"]
