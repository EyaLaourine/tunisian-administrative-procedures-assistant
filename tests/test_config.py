import pytest
from pydantic import ValidationError

from backend.settings import REPO_ROOT, Settings
from ingestion.models import SourceRegistry, SourceStatus
from ingestion.registry import load_registry


def test_settings_defaults_load_without_env_file():
    s = Settings(_env_file=None)
    assert s.embedding_model == "bge-m3"
    assert s.embedding_dim == 1024
    assert s.raw_dir == REPO_ROOT / "data" / "raw"


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("QDRANT_URL", "http://qdrant:6333")
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "1234")
    s = Settings(_env_file=None)
    assert s.qdrant_url == "http://qdrant:6333"
    assert s.max_upload_bytes == 1234


def test_settings_reject_invalid_limits(monkeypatch):
    monkeypatch.setenv("MAX_DOWNLOAD_BYTES", "0")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_project_registry_is_valid():
    registry = load_registry(REPO_ROOT / "config" / "sources.yaml")
    approved = registry.approved()
    assert approved, "registry must contain approved official sources"
    for entry in approved:
        assert entry.url.host in registry.allowed_domains
    for entry in registry.sources:
        if entry.status != SourceStatus.APPROVED:
            assert entry.exclusion_reason


def _registry(**override) -> dict:
    entry = {
        "doc_id": "sample-doc",
        "status": "approved",
        "source_organization": "Org",
        "url": "https://official.example.tn/a.pdf",
        "title": "A",
        "document_type": "decree",
        "procedure_category": "general",
    }
    entry.update(override)
    return {"allowed_domains": ["official.example.tn"], "sources": [entry]}


def test_registry_rejects_non_allowlisted_domain():
    with pytest.raises(ValidationError, match="allowed_domains"):
        SourceRegistry.model_validate(_registry(url="https://elsewhere.example.com/a.pdf"))


def test_registry_rejects_duplicate_ids():
    raw = _registry()
    raw["sources"].append(dict(raw["sources"][0]))
    with pytest.raises(ValidationError, match="duplicate doc_id"):
        SourceRegistry.model_validate(raw)


def test_registry_requires_reason_for_excluded():
    with pytest.raises(ValidationError, match="exclusion_reason"):
        SourceRegistry.model_validate(_registry(status="excluded"))


def test_registry_rejects_unknown_document_type():
    with pytest.raises(ValidationError):
        SourceRegistry.model_validate(_registry(document_type="blog_post"))
