"""Ingestion pipeline tests using an in-process HTTP mock (no network)."""

import httpx
import pytest

from ingestion.downloader import Downloader, DownloadError
from ingestion.manifest import Manifest
from ingestion.models import SourceEntry, VerificationStatus
from ingestion.pipeline import ingest_entry, original_basename
from ingestion.robots import RobotsPolicy

HOST = "official.example.tn"
UA = "TestAgent/1.0"


def _client(routes: dict[str, httpx.Response]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        key = f"{request.url.host}{request.url.path}"
        return routes.get(key, httpx.Response(404))

    return httpx.Client(transport=httpx.MockTransport(handler), headers={"User-Agent": UA}, follow_redirects=True)


def _entry(doc_id: str, path: str) -> SourceEntry:
    return SourceEntry(
        doc_id=doc_id,
        status="approved",
        source_organization="Org",
        url=f"https://{HOST}{path}",
        title="Fixture",
        document_type="decree",
        procedure_category="general",
    )


@pytest.fixture
def pdf_bytes(make_pdf):
    return make_pdf([[("Fixture body text for ingestion tests", 11)] * 4]).read_bytes()


def _run(entry, routes, tmp_path, manifest=None, ai_agents=("ClaudeBot",)):
    client = _client(routes)
    robots = RobotsPolicy(client, UA, list(ai_agents))
    downloader = Downloader(client, [HOST], max_bytes=5_000_000, default_delay=0)
    manifest = manifest or Manifest(tmp_path / "raw" / "manifest.json")
    return ingest_entry(entry, downloader, robots, manifest, tmp_path / "raw"), manifest


def test_successful_download_records_checksum_and_stores_original(tmp_path, pdf_bytes):
    routes = {f"{HOST}/doc.pdf": httpx.Response(200, content=pdf_bytes, headers={"content-type": "application/pdf"})}
    rec, _ = _run(_entry("doc-a", "/doc.pdf"), routes, tmp_path)
    assert rec.verification_status == VerificationStatus.OFFICIAL_SOURCE_VERIFIED
    assert rec.sha256 and len(rec.sha256) == 64
    stored = list((tmp_path / "raw" / "doc-a").iterdir())
    assert len(stored) == 1 and stored[0].read_bytes() == pdf_bytes  # unmodified original
    assert stored[0].name.startswith(rec.sha256[:12])


def test_duplicate_detection_by_checksum(tmp_path, pdf_bytes):
    routes = {
        f"{HOST}/a.pdf": httpx.Response(200, content=pdf_bytes),
        f"{HOST}/b.pdf": httpx.Response(200, content=pdf_bytes),
    }
    first, manifest = _run(_entry("doc-a", "/a.pdf"), routes, tmp_path)
    manifest.upsert(first)
    second, _ = _run(_entry("doc-b", "/b.pdf"), routes, tmp_path, manifest=manifest)
    assert second.verification_status == VerificationStatus.DUPLICATE
    assert second.duplicate_of == "doc-a"
    manifest.upsert(second)
    assert [r.doc_id for r in manifest.indexable()] == ["doc-a"]


def test_rerun_same_document_is_not_flagged_duplicate(tmp_path, pdf_bytes):
    routes = {f"{HOST}/a.pdf": httpx.Response(200, content=pdf_bytes)}
    first, manifest = _run(_entry("doc-a", "/a.pdf"), routes, tmp_path)
    manifest.upsert(first)
    again, _ = _run(_entry("doc-a", "/a.pdf"), routes, tmp_path, manifest=manifest)
    assert again.verification_status == VerificationStatus.OFFICIAL_SOURCE_VERIFIED


def test_robots_ai_optout_blocks_download(tmp_path, pdf_bytes):
    robots_txt = "User-agent: *\nAllow: /\n\nUser-agent: ClaudeBot\nDisallow: /\n"
    routes = {
        f"{HOST}/robots.txt": httpx.Response(200, text=robots_txt, headers={"content-type": "text/plain"}),
        f"{HOST}/a.pdf": httpx.Response(200, content=pdf_bytes),
    }
    rec, _ = _run(_entry("doc-a", "/a.pdf"), routes, tmp_path)
    assert rec.verification_status == VerificationStatus.BLOCKED_BY_POLICY
    assert "ClaudeBot" in rec.error


def test_robots_path_disallow_blocks_download(tmp_path, pdf_bytes):
    routes = {
        f"{HOST}/robots.txt": httpx.Response(200, text="User-agent: *\nDisallow: /uploads/\n"),
        f"{HOST}/uploads/a.pdf": httpx.Response(200, content=pdf_bytes),
    }
    rec, _ = _run(_entry("doc-a", "/uploads/a.pdf"), routes, tmp_path)
    assert rec.verification_status == VerificationStatus.BLOCKED_BY_POLICY


def test_http_error_is_recorded_not_raised(tmp_path):
    rec, _ = _run(_entry("doc-a", "/missing.pdf"), {}, tmp_path)
    assert rec.verification_status == VerificationStatus.FAILED
    assert rec.error == "HTTP 404"
    assert rec.sha256 is None


def test_invalid_content_is_rejected(tmp_path):
    routes = {f"{HOST}/a.pdf": httpx.Response(200, content=b"\x89PNG\r\n\x1a\nnot a document")}
    rec, _ = _run(_entry("doc-a", "/a.pdf"), routes, tmp_path)
    assert rec.verification_status == VerificationStatus.FAILED


def test_downloader_refuses_non_allowlisted_host():
    downloader = Downloader(_client({}), [HOST], max_bytes=100, default_delay=0)
    with pytest.raises(DownloadError, match="not allow-listed"):
        downloader.fetch("https://unofficial.example.com/a.pdf")


def test_downloader_refuses_redirect_off_allowlist():
    routes = {f"{HOST}/a.pdf": httpx.Response(302, headers={"location": "https://evil.example.com/a.pdf"})}
    downloader = Downloader(_client(routes), [HOST], max_bytes=100, default_delay=0)
    with pytest.raises(DownloadError, match="non-allow-listed"):
        downloader.fetch(f"https://{HOST}/a.pdf")


def test_downloader_enforces_size_cap():
    routes = {f"{HOST}/a.pdf": httpx.Response(200, content=b"%PDF-" + b"0" * 500)}
    downloader = Downloader(_client(routes), [HOST], max_bytes=100, default_delay=0)
    with pytest.raises(DownloadError, match="exceeds|too large"):
        downloader.fetch(f"https://{HOST}/a.pdf")


def test_original_basename():
    assert original_basename("https://h.tn/formalites/", "html") == "formalites.html"
    assert original_basename("https://h.tn/x/De%CC%81cret.pdf", "pdf") == "De_cret.pdf"
    assert original_basename("https://h.tn/docs/02.html", "html") == "02.html"
