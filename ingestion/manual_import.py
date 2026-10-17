"""Import an official file that a person downloaded manually from the registry URL.

Use only when automated retrieval is blocked by robots.txt but the file is published for the
public to download (e.g. a printable form). The file must correspond to an `approved` registry
entry; it is validated, checksummed and stored unmodified like an automated download.

    python -m ingestion.manual_import --doc-id interior-passport-application-form --file ~/Downloads/02.pdf
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from backend.settings import get_settings
from ingestion.integrity import sha256_bytes, validate_document
from ingestion.manifest import Manifest
from ingestion.models import ManifestRecord, VerificationStatus
from ingestion.pipeline import _relative, original_basename
from ingestion.registry import load_registry


def import_file(doc_id: str, file_path: Path) -> ManifestRecord:
    settings = get_settings()
    registry = load_registry(settings.registry_path)
    entry = next((e for e in registry.approved() if e.doc_id == doc_id), None)
    if entry is None:
        raise SystemExit(f"{doc_id} is not an approved registry entry")
    data = file_path.read_bytes()
    if len(data) > settings.max_download_bytes:
        raise SystemExit("file too large")
    validated = validate_document(data, None)
    sha = sha256_bytes(data)
    manifest = Manifest(settings.raw_dir / "manifest.json")
    target = settings.raw_dir / doc_id / f"{sha[:12]}_{original_basename(str(entry.url), validated.file_format)}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    duplicate = manifest.find_by_sha256(sha, exclude_doc_id=doc_id)
    record = ManifestRecord(
        doc_id=doc_id,
        source_organization=entry.source_organization,
        url=str(entry.url),
        title=entry.title,
        document_type=entry.document_type,
        procedure_category=entry.procedure_category,
        language=entry.language,
        publication_date=entry.publication_date,
        official_reference=entry.official_reference,
        applicability=entry.applicability,
        retrieval_timestamp=datetime.now(timezone.utc),
        retrieval_method="manual",
        file_format=validated.file_format,
        file_path=_relative(target),
        size_bytes=len(data),
        sha256=sha,
        page_count=validated.page_count,
        has_text_layer=validated.has_text_layer,
        duplicate_of=duplicate.doc_id if duplicate else None,
        verification_status=VerificationStatus.DUPLICATE if duplicate else VerificationStatus.OFFICIAL_SOURCE_VERIFIED,
    )
    manifest.upsert(record)
    manifest.save()
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--doc-id", required=True)
    parser.add_argument("--file", required=True, type=Path)
    args = parser.parse_args()
    record = import_file(args.doc_id, args.file.expanduser())
    print(json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
