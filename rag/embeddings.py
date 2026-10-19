"""Embedding client interface and the Ollama (BGE-M3) implementation."""

import logging
import time

from typing import Protocol

import httpx


log = logging.getLogger(__name__)


class EmbeddingClient(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class EmbeddingError(Exception):
    pass


class OllamaEmbeddingClient:
    """Calls Ollama's /api/embed. BGE-M3 returns L2-normalized 1024-d dense vectors."""

    def __init__(self, base_url: str, model: str, dim: int, timeout: float = 300.0, batch_size: int = 16):
        self._url = base_url.rstrip("/") + "/api/embed"
        self.model = model
        self.dim = dim
        self._timeout = timeout
        self._batch_size = batch_size

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        with httpx.Client(timeout=self._timeout) as client:
            for i in range(0, len(texts), self._batch_size):
                batch = texts[i : i + self._batch_size]
                started = time.perf_counter()
                try:
                    resp = client.post(self._url, json={"model": self.model, "input": batch})
                    resp.raise_for_status()
                except httpx.HTTPError as exc:
                    raise EmbeddingError(f"Ollama embedding request failed: {exc}") from exc
                batch_vectors = resp.json().get("embeddings") or []
                if len(batch_vectors) != len(batch) or any(len(v) != self.dim for v in batch_vectors):
                    raise EmbeddingError(f"unexpected embedding shape from model {self.model}")
                vectors.extend(batch_vectors)
                log.info("embedding_timing", extra={"fields": {
                    "model": self.model, "items": len(batch),
                    "ms": round((time.perf_counter() - started) * 1000)}})
        return vectors

    def ping(self) -> bool:
        try:
            with httpx.Client(timeout=5) as client:
                return client.get(self._url.removesuffix("/api/embed") + "/api/tags").status_code == 200
        except httpx.HTTPError:
            return False
