"""Qdrant collection management, upsert and filtered search."""

import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

# Payload fields that retrieval can filter on.
KEYWORD_INDEXES = ["doc_id", "procedure_category", "document_type", "language", "chunk_language", "source_organization"]


def point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


class QdrantStore:
    def __init__(self, url: str, api_key: str | None = None, timeout: int = 30):
        self.client = QdrantClient(url=url, api_key=api_key or None, timeout=timeout)

    def ping(self) -> bool:
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False

    def recreate_collection(self, name: str, dim: int) -> None:
        if self.client.collection_exists(name):
            self.client.delete_collection(name)
        self.client.create_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
        )
        for field in KEYWORD_INDEXES:
            self.client.create_payload_index(name, field_name=field, field_schema=qm.PayloadSchemaType.KEYWORD)

    def upsert(self, name: str, ids: list[str], vectors: list[list[float]], payloads: list[dict[str, Any]]) -> None:
        points = [qm.PointStruct(id=point_id(i), vector=v, payload=p) for i, v, p in zip(ids, vectors, payloads)]
        for start in range(0, len(points), 128):
            self.client.upsert(collection_name=name, points=points[start : start + 128], wait=True)

    def count(self, name: str) -> int:
        return self.client.count(name, exact=True).count

    def search(self, name: str, vector: list[float], top_k: int, filters: dict[str, str | list[str]] | None = None):
        conditions = []
        for key, value in (filters or {}).items():
            if isinstance(value, list):
                conditions.append(qm.FieldCondition(key=key, match=qm.MatchAny(any=value)))
            else:
                conditions.append(qm.FieldCondition(key=key, match=qm.MatchValue(value=value)))
        query_filter = qm.Filter(must=conditions) if conditions else None
        return self.client.query_points(
            collection_name=name, query=vector, limit=top_k, query_filter=query_filter, with_payload=True
        ).points
