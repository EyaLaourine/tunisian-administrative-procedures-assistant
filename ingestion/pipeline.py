"""Official-document ingestion: registry -> policy check -> download -> validate -> manifest.

Original bytes are stored unmodified under data/raw/<doc_id>/<sha12>_<basename>. A changed
upstream file produces a new file next to the old one, so earlier snapshots are never overwritten.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

import httpx

from backend.settings import REPO_ROOT, Settings
from ingestion.downloader import Downloader, DownloadError
from ingestion.integrity import ValidationError, sha256_bytes, validate_document
from ingestion.manifest import Manifest
from ingestion.models import ManifestRecord, SourceEntry, VerificationStatus
from ingestion.registry import load_registry
from ingestion.robots import RobotsPolicy
from ingestion.tls import build_ssl_context

log = logging.getLogger(__name__)

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def original_basename(url: str, file_format: str) -> str:
    """Filesystem-safe basename derived from the URL path (e.g. '/formalites/' -> 'formalites.html')."""
    path = PurePosixPath(unquote(urlsplit(url).path))
    name = path.name or (path.parent.name if path.parent.name else "index")
    if not name.lower().endswith(f".{file_format}"):
        name = f"{name}.{file_format}"
    return _SAFE_NAME.sub("_", name)


@dataclass
class IngestionSummary:
    started_at: str
    finished_at: str | None = None
    results: list[dict] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for r in self.results:
            out[r["verification_status"]] = out.get(r["verification_status"], 0) + 1
        return out


def _relative(path: Path) -> str:
    """Repository-relative POSIX path when possible (portable manifest); absolute otherwise."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def ingest_entry(
    entry: SourceEntry,
    downloader: Downloader,
    robots: RobotsPolicy,
    manifest: Manifest,
    raw_dir: Path,
) -> ManifestRecord:
    base = dict(
        doc_id=entry.doc_id,
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
    )
    decision = robots.check(str(entry.url))
    if not decision.allowed:
        return ManifestRecord(**base, verification_status=VerificationStatus.BLOCKED_BY_POLICY, error=decision.reason)

    try:
        result = downloader.fetch(str(entry.url), crawl_delay=decision.crawl_delay)
        validated = validate_document(result.data, result.content_type)
    except (DownloadError, ValidationError) as exc:
        return ManifestRecord(**base, verification_status=VerificationStatus.FAILED, error=str(exc))

    sha = sha256_bytes(result.data)
    target = raw_dir / entry.doc_id / f"{sha[:12]}_{original_basename(str(entry.url), validated.file_format)}"
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(result.data)

    previous = manifest.records.get(entry.doc_id)
    if previous and previous.sha256 and previous.sha256 != sha:
        log.warning(
            "upstream_content_changed",
            extra={"fields": {"doc_id": entry.doc_id, "previous_sha256": previous.sha256, "sha256": sha}},
        )

    duplicate = manifest.find_by_sha256(sha, exclude_doc_id=entry.doc_id)
    return ManifestRecord(
        **base,
        final_url=result.final_url,
        http_status=result.status_code,
        content_type=result.content_type,
        http_last_modified=result.last_modified,
        file_format=validated.file_format,
        file_path=_relative(target),
        size_bytes=len(result.data),
        sha256=sha,
        page_count=validated.page_count,
        has_text_layer=validated.has_text_layer,
        duplicate_of=duplicate.doc_id if duplicate else None,
        verification_status=VerificationStatus.DUPLICATE if duplicate else VerificationStatus.OFFICIAL_SOURCE_VERIFIED,
    )


def run_ingestion(settings: Settings, only: list[str] | None = None) -> IngestionSummary:
    registry = load_registry(settings.registry_path)
    raw_dir = settings.raw_dir
    manifest = Manifest(raw_dir / "manifest.json")
    summary = IngestionSummary(started_at=datetime.now(timezone.utc).isoformat())

    entries = registry.approved()
    if only:
        entries = [e for e in entries if e.doc_id in set(only)]

    headers = {"User-Agent": settings.http_user_agent}
    ssl_ctx = build_ssl_context(settings.resolve(settings.extra_ca_dir))
    with httpx.Client(
        headers=headers, timeout=settings.http_timeout_seconds, follow_redirects=True, verify=ssl_ctx
    ) as client:
        robots = RobotsPolicy(client, settings.http_user_agent, registry.ai_optout_agents)
        downloader = Downloader(
            client, registry.allowed_domains, settings.max_download_bytes, settings.default_crawl_delay_seconds
        )
        for entry in entries:
            record = ingest_entry(entry, downloader, robots, manifest, raw_dir)
            manifest.upsert(record)
            fields = {
                "doc_id": record.doc_id,
                "status": record.verification_status.value,
                "sha256": record.sha256,
                "size_bytes": record.size_bytes,
                "duplicate_of": record.duplicate_of,
                "error": record.error,
            }
            log.info("document_ingested", extra={"fields": fields})
            summary.results.append({**fields, "verification_status": record.verification_status.value})

    manifest.save()
    summary.finished_at = datetime.now(timezone.utc).isoformat()
    run_log = raw_dir / "ingestion_log.jsonl"
    with run_log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"started_at": summary.started_at, "finished_at": summary.finished_at,
                             "counts": summary.counts(), "results": summary.results}, ensure_ascii=False) + "\n")
    return summary
