"""Embeddings enchufables: uno real (servidor local OpenAI-compatible: LM Studio u Ollama) y uno simulado (mock).

- `LocalEmbedder` le habla a `<base_url>/embeddings`. Por privacidad SOLO acepta una dirección de esta PC, salvo que la
  config diga `allow_remote: true` (y entonces la clave sale de la variable que nombre `api_key_env`, nunca del archivo).
  Si el servidor no responde devuelve `None`: quien llama cae a palabra clave y lo avisa. Nunca levanta.
- `MockEmbedder` es determinista (bolsa de palabras hasheada): las notas que comparten palabras quedan cerca. Es lo que
  usan los tests y la demo; NO es semántico de verdad.
"""

from __future__ import annotations

import hashlib
import math
import os
from collections.abc import Mapping
from typing import Any, Protocol

import httpx

from .config import MemoriaConfig, embeddings_target, is_local_url
from .textutil import tokens


class Embedder(Protocol):
    name: str
    model: str
    last_error: str | None

    def embed(self, text: str) -> list[float] | None: ...


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return 0.0 if na == 0.0 or nb == 0.0 else dot / (na * nb)


class MockEmbedder:
    name = "mock"
    model = "mock-hash-256"

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim
        self.last_error: str | None = None

    def embed(self, text: str) -> list[float] | None:
        words = tokens(text)
        if not words:
            return None
        v = [0.0] * self.dim
        for w in words:
            h = int.from_bytes(hashlib.sha1(w.encode()).digest()[:4], "big")
            v[h % self.dim] += 1.0
        return v


class LocalEmbedder:
    name = "local"

    def __init__(self, base_url: str, model: str, *, timeout: float = 10.0, api_key: str = "",
                 transport: httpx.BaseTransport | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.api_key = api_key
        self.transport = transport
        self.last_error: str | None = None

    def embed(self, text: str) -> list[float] | None:
        text = (text or "").strip()
        if not text:
            return None
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport) as c:
                r = c.post(f"{self.base_url}/embeddings", json={"model": self.model, "input": text}, headers=headers)
                r.raise_for_status()
                vec = r.json()["data"][0]["embedding"]
            self.last_error = None
            return [float(x) for x in vec]
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError, OSError) as exc:
            self.last_error = f"el servidor de embeddings ({self.base_url}) no respondió bien: {type(exc).__name__}"
            return None


class NoEmbedder:
    name = "off"
    model = ""

    def __init__(self, reason: str = "embeddings apagados") -> None:
        self.last_error: str | None = reason

    def embed(self, text: str) -> list[float] | None:
        return None


def build_embedder(cfg: MemoriaConfig, env: Mapping[str, str] | None = None, *,
                   transport: httpx.BaseTransport | None = None) -> Embedder:
    """El embedder que corresponde a la config. Una dirección que no es de esta PC se rechaza sin `allow_remote`."""
    env = os.environ if env is None else env
    e = cfg.embeddings
    if e.provider == "off":
        return NoEmbedder()
    if e.provider == "mock":
        return MockEmbedder()
    url, model = embeddings_target(cfg, env)
    if not is_local_url(url) and not e.allow_remote:
        return NoEmbedder(f"la dirección de embeddings ({url}) no es de esta PC: lo privado no sale "
                          "(poné embeddings.allow_remote: true si de verdad querés usarla)")
    key = env.get(e.api_key_env, "") if e.api_key_env else ""
    if e.api_key_env and not key and not is_local_url(url):
        return NoEmbedder(f"falta la clave en {e.api_key_env}")
    return LocalEmbedder(url, model, timeout=e.timeout_seconds, api_key=key, transport=transport)


class EmbeddingIndex:
    """Índice de vectores guardado en el espacio de la brigada (colección `embeddings`), con el modelo que lo generó:
    cambiar de modelo invalida los vectores viejos (otra dimensión nunca se compara)."""

    COLLECTION = "embeddings"

    def __init__(self, space: Any, embedder: Embedder) -> None:
        self.space = space
        self.embedder = embedder

    def load(self) -> dict[str, list[float]]:
        out: dict[str, list[float]] = {}
        # `Space.list` devuelve solo los docs; el id viaja adentro
        for d in self.space.list(self.COLLECTION):
            if d.get("model") == self.embedder.model and d.get("id"):
                out[d["id"]] = d["v"]
        return out

    def update(self, note_id: str, text: str) -> bool:
        key = hashlib.sha1(note_id.encode()).hexdigest()[:20]
        digest = hashlib.sha1(text.encode()).hexdigest()
        cur = self.space.get(self.COLLECTION, key)
        if cur and cur.get("h") == digest and cur.get("model") == self.embedder.model:
            return True
        vec = self.embedder.embed(text)
        if vec is None:
            return False
        self.space.put(self.COLLECTION, key, {"id": note_id, "h": digest, "model": self.embedder.model, "v": vec})
        return True

    def remove(self, note_id: str) -> None:
        self.space.delete(self.COLLECTION, hashlib.sha1(note_id.encode()).hexdigest()[:20])

    def reindex(self, items: list[tuple[str, str]]) -> dict[str, int]:
        """Recalcula los vectores de `(id, texto)`. `skipped` cuenta notas sin vector (servidor caído a mitad)."""
        done = skipped = 0
        keep: set[str] = set()
        for nid, text in items:
            keep.add(hashlib.sha1(nid.encode()).hexdigest()[:20])
            if self.update(nid, text):
                done += 1
            else:
                skipped += 1
        for d in self.space.list(self.COLLECTION):                       # vectores de notas que ya no existen
            key = hashlib.sha1(d.get("id", "").encode()).hexdigest()[:20]
            if key not in keep:
                self.space.delete(self.COLLECTION, key)
        return {"indexed": done, "skipped": skipped}

