"""Persistent manifest of retrieved originals (data/raw/manifest.json)."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from ingestion.models import ManifestRecord, VerificationStatus


class Manifest:
    def __init__(self, path: Path):
        self.path = path
        self.records: dict[str, ManifestRecord] = {}
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            for item in raw.get("records", []):
                rec = ManifestRecord.model_validate(item)
                self.records[rec.doc_id] = rec

    def find_by_sha256(self, sha256: str, exclude_doc_id: str | None = None) -> ManifestRecord | None:
        """Return the first non-duplicate record with these exact bytes (duplicate detection)."""
        for rec in self.records.values():
            if (
                rec.sha256 == sha256
                and rec.doc_id != exclude_doc_id
                and rec.verification_status == VerificationStatus.OFFICIAL_SOURCE_VERIFIED
            ):
                return rec
        return None

    def upsert(self, record: ManifestRecord) -> None:
        self.records[record.doc_id] = record

    def indexable(self) -> list[ManifestRecord]:
        """Records eligible for RAG indexing: verified, unique, and with a file on disk."""
        return [
            r
            for r in self.records.values()
            if r.verification_status == VerificationStatus.OFFICIAL_SOURCE_VERIFIED and r.file_path
        ]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "records": [r.model_dump(mode="json") for r in sorted(self.records.values(), key=lambda r: r.doc_id)],
        }
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)
