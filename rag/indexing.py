"""Indexing pipeline: manifest -> extraction -> chunking (both strategies) -> embeddings -> Qdrant.

Only manifest records with verification_status=official_source_verified are indexed. Documents
without a text layer are skipped and reported (OCR is a later phase); nothing is fabricated.
Private user uploads never pass through this module.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from backend.settings import REPO_ROOT, Settings
from ingestion.manifest import Manifest
from rag.chunking import STRATEGIES, Chunk
from rag.embeddings import EmbeddingClient
from rag.extraction import detect_script_language, extract_document
from rag.vector_store import QdrantStore

log = logging.getLogger(__name__)


def collection_name(settings: Settings, strategy: str) -> str:
    return f"{settings.qdrant_collection_prefix}_{strategy}"


@dataclass
class IndexingReport:
    documents_indexed: list[str] = field(default_factory=list)
    documents_skipped: dict[str, str] = field(default_factory=dict)
    chunks_per_strategy: dict[str, int] = field(default_factory=dict)


def build_chunks(settings: Settings) -> tuple[dict[str, list[tuple[Chunk, dict]]], IndexingReport]:
    """Extract and chunk every indexable document. Returns {strategy: [(chunk, payload), ...]}."""
    manifest = Manifest(settings.raw_dir / "manifest.json")
    report = IndexingReport()
    out: dict[str, list[tuple[Chunk, dict]]] = {s: [] for s in STRATEGIES}
    extracted_dir = settings.processed_dir / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)

    for rec in sorted(manifest.indexable(), key=lambda r: r.doc_id):
        if rec.has_text_layer is False:
            report.documents_skipped[rec.doc_id] = "no text layer (OCR required)"
            continue
        blocks = extract_document(REPO_ROOT / rec.file_path, rec.file_format or "")
        if not blocks:
            report.documents_skipped[rec.doc_id] = "no extractable text"
            continue
        (extracted_dir / f"{rec.doc_id}.json").write_text(
            json.dumps([b.to_dict() for b in blocks], ensure_ascii=False, indent=1), encoding="utf-8"
        )
        doc_payload = {
            "doc_id": rec.doc_id,
            "title": rec.title,
            "source_organization": rec.source_organization,
            "url": rec.url,
            "document_type": rec.document_type.value,
            "procedure_category": rec.procedure_category.value,
            "language": rec.language.value,
            "publication_date": rec.publication_date.isoformat() if rec.publication_date else None,
            "official_reference": rec.official_reference,
            "applicability": rec.applicability.value,
            "sha256": rec.sha256,
            "retrieval_timestamp": rec.retrieval_timestamp.isoformat(),
        }
        for strategy, fn in STRATEGIES.items():
            for chunk in fn(rec.doc_id, blocks, doc_title=rec.title):
                payload = {
                    **doc_payload,
                    "chunk_id": chunk.chunk_id,
                    "strategy": strategy,
                    "chunk_index": chunk.index,
                    "text": chunk.text,
                    "heading_path": chunk.heading_path,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "chunk_language": detect_script_language(chunk.text),
                }
                out[strategy].append((chunk, payload))
        report.documents_indexed.append(rec.doc_id)

    for strategy, items in out.items():
        report.chunks_per_strategy[strategy] = len(items)
        path = settings.processed_dir / f"chunks_{strategy}.jsonl"
        with path.open("w", encoding="utf-8") as fh:
            for _, payload in items:
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return out, report


def run_indexing(settings: Settings, embedder: EmbeddingClient, store: QdrantStore) -> IndexingReport:
    chunks, report = build_chunks(settings)
    for strategy, items in chunks.items():
        name = collection_name(settings, strategy)
        store.recreate_collection(name, embedder.dim)
        if not items:
            continue
        vectors = embedder.embed([payload["text"] for _, payload in items])
        store.upsert(name, [c.chunk_id for c, _ in items], vectors, [p for _, p in items])
        log.info("collection_indexed", extra={"fields": {"collection": name, "points": store.count(name)}})
    return report
