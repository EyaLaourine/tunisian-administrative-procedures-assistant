"""Dense retrieval with metadata filtering and traceable citations."""

from pydantic import BaseModel, Field

from backend.settings import Settings
from rag.embeddings import EmbeddingClient
from rag.indexing import collection_name
from rag.vector_store import QdrantStore


class RetrievalFilters(BaseModel):
    procedure_category: str | list[str] | None = None
    document_type: str | list[str] | None = None
    language: str | list[str] | None = None
    doc_id: str | list[str] | None = None

    def as_dict(self) -> dict:
        return {k: v for k, v in self.model_dump().items() if v}


class Citation(BaseModel):
    doc_id: str
    title: str
    source_organization: str
    url: str
    official_reference: str | None
    publication_date: str | None
    applicability: str
    page_start: int | None
    page_end: int | None
    heading_path: list[str]
    sha256: str
    language: str | None = None  # document language from the source registry
    document_type: str | None = None
    procedure_category: str | None = None


class RetrievedPassage(BaseModel):
    score: float
    text: str
    chunk_id: str
    citation: Citation


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=50)
    strategy: str = Field(default="structure", pattern="^(structure|recursive)$")
    filters: RetrievalFilters = Field(default_factory=RetrievalFilters)
    # Passages scoring below this cosine similarity are dropped rather than returned as weak evidence.
    min_score: float = Field(default=0.0, ge=-1.0, le=1.0)


def retrieve(req: RetrievalRequest, settings: Settings, embedder: EmbeddingClient, store: QdrantStore) -> list[RetrievedPassage]:
    return retrieve_by_vector(req, embedder.embed([req.query])[0], settings, store)


def retrieve_by_vector(req: RetrievalRequest, vector: list[float], settings: Settings, store: QdrantStore) -> list[RetrievedPassage]:
    """Same as retrieve(), with the query vector computed by the caller (e.g. batched)."""
    points = store.search(collection_name(settings, req.strategy), vector, req.top_k, req.filters.as_dict())
    results = []
    for p in points:
        if p.score < req.min_score:
            continue
        pl = p.payload or {}
        results.append(
            RetrievedPassage(
                score=p.score,
                text=pl["text"],
                chunk_id=pl["chunk_id"],
                citation=Citation(
                    doc_id=pl["doc_id"],
                    title=pl["title"],
                    source_organization=pl["source_organization"],
                    url=pl["url"],
                    official_reference=pl.get("official_reference"),
                    publication_date=pl.get("publication_date"),
                    applicability=pl.get("applicability", "unverified"),
                    page_start=pl.get("page_start"),
                    page_end=pl.get("page_end"),
                    heading_path=pl.get("heading_path") or [],
                    sha256=pl["sha256"],
                    language=pl.get("language"),
                    document_type=pl.get("document_type"),
                    procedure_category=pl.get("procedure_category"),
                ),
            )
        )
    return results
