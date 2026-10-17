"""Integration tests against running services. Skipped (and reported as skipped) when unavailable.

Run: pytest -m integration
"""

import uuid

import pytest

from backend.settings import get_settings
from rag.embeddings import OllamaEmbeddingClient
from rag.retrieval import RetrievalRequest, retrieve
from rag.vector_store import QdrantStore

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def settings():
    return get_settings()


@pytest.fixture(scope="module")
def store(settings):
    s = QdrantStore(settings.qdrant_url, settings.qdrant_api_key, timeout=5)
    if not s.ping():
        pytest.skip(f"Qdrant not reachable at {settings.qdrant_url}")
    return s


@pytest.fixture(scope="module")
def embedder(settings):
    e = OllamaEmbeddingClient(settings.ollama_url, settings.embedding_model, settings.embedding_dim)
    if not e.ping():
        pytest.skip(f"Ollama not reachable at {settings.ollama_url}")
    return e


def test_qdrant_roundtrip(store):
    name = f"test_{uuid.uuid4().hex[:8]}"
    try:
        store.recreate_collection(name, 4)
        store.upsert(
            name,
            ["a", "b"],
            [[1, 0, 0, 0], [0, 1, 0, 0]],
            [{"doc_id": "a", "language": "fr"}, {"doc_id": "b", "language": "ar"}],
        )
        assert store.count(name) == 2
        hits = store.search(name, [1, 0, 0, 0], top_k=1)
        assert hits[0].payload["doc_id"] == "a"
        filtered = store.search(name, [1, 0, 0, 0], top_k=2, filters={"language": "ar"})
        assert [h.payload["doc_id"] for h in filtered] == ["b"]
    finally:
        store.client.delete_collection(name)


def test_ollama_bge_m3_embedding_shape(embedder):
    vectors = embedder.embed(["passeport", "جواز سفر"])
    assert len(vectors) == 2 and all(len(v) == 1024 for v in vectors)


def test_retrieval_returns_traceable_citations(settings, store, embedder):
    if not store.client.collection_exists(f"{settings.qdrant_collection_prefix}_structure"):
        pytest.skip("corpus not indexed yet (POST /index/run)")
    results = retrieve(
        RetrievalRequest(query="pièces à fournir passeport", top_k=3, filters={"procedure_category": "passport"}),
        settings,
        embedder,
        store,
    )
    assert results
    for r in results:
        assert r.citation.url.startswith("http")
        assert len(r.citation.sha256) == 64
        assert r.citation.applicability == "unverified"
