"""Data models for the official source registry and the download manifest."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl, model_validator


class SourceStatus(StrEnum):
    APPROVED = "approved"
    EXCLUDED = "excluded"
    NOT_FOUND = "not_found"


class DocumentType(StrEnum):
    LAW = "law"
    DECREE = "decree"
    MINISTERIAL_ORDER = "ministerial_order"
    CIRCULAR = "circular"
    PROCEDURE_GUIDE = "procedure_guide"
    PROCEDURE_TABLE = "procedure_table"
    OFFICIAL_FORM = "official_form"
    OTHER = "other"


class ProcedureCategory(StrEnum):
    BUSINESS_REGISTRATION = "business_registration"
    PASSPORT = "passport"
    BIRTH_CERTIFICATE = "birth_certificate"
    NATIONAL_ID = "national_id"
    GENERAL = "general"


class Language(StrEnum):
    FR = "fr"
    AR = "ar"
    EN = "en"
    MIXED = "mixed"  # e.g. bilingual Arabic/French forms
    UNKNOWN = "unknown"


class VerificationStatus(StrEnum):
    # Downloaded from an allow-listed official domain, file validated, checksum recorded.
    OFFICIAL_SOURCE_VERIFIED = "official_source_verified"
    # Same bytes as another manifest entry; kept for provenance, not indexed twice.
    DUPLICATE = "duplicate"
    FAILED = "failed"
    BLOCKED_BY_POLICY = "blocked_by_policy"


class Applicability(StrEnum):
    # Default: nobody has confirmed the document is still legally in force.
    UNVERIFIED = "unverified"
    VERIFIED_CURRENT = "verified_current"
    SUPERSEDED = "superseded"


class SourceEntry(BaseModel):
    """One entry of config/sources.yaml."""

    doc_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,80}$")
    status: SourceStatus
    source_organization: str
    url: HttpUrl
    listing_url: HttpUrl | None = None
    title: str
    document_type: DocumentType
    procedure_category: ProcedureCategory
    language: Language = Language.UNKNOWN
    # Date of the official publication (e.g. JORT issue date), read from the document itself.
    publication_date: date | None = None
    # Official citation as printed in the document, e.g. "Décret Présidentiel n° 2022-298 du 28 mars 2022".
    official_reference: str | None = None
    applicability: Applicability = Applicability.UNVERIFIED
    exclusion_reason: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _reason_required_when_not_approved(self) -> "SourceEntry":
        if self.status != SourceStatus.APPROVED and not self.exclusion_reason:
            raise ValueError(f"{self.doc_id}: exclusion_reason is required when status={self.status}")
        return self


class SourceRegistry(BaseModel):
    allowed_domains: list[str]
    ai_optout_agents: list[str] = Field(default_factory=list)
    sources: list[SourceEntry]

    @model_validator(mode="after")
    def _unique_ids_and_allowed_domains(self) -> "SourceRegistry":
        seen: set[str] = set()
        for entry in self.sources:
            if entry.doc_id in seen:
                raise ValueError(f"duplicate doc_id in registry: {entry.doc_id}")
            seen.add(entry.doc_id)
            if entry.status == SourceStatus.APPROVED and entry.url.host not in self.allowed_domains:
                raise ValueError(f"{entry.doc_id}: host {entry.url.host} is not in allowed_domains")
        return self

    def approved(self) -> list[SourceEntry]:
        return [s for s in self.sources if s.status == SourceStatus.APPROVED]


class ManifestRecord(BaseModel):
    """Provenance record for one retrieved original file (data/raw/manifest.json)."""

    doc_id: str
    source_organization: str
    url: str
    final_url: str | None = None
    title: str
    document_type: DocumentType
    procedure_category: ProcedureCategory
    language: Language
    publication_date: date | None = None
    official_reference: str | None = None
    applicability: Applicability = Applicability.UNVERIFIED
    retrieval_timestamp: datetime
    # "automated" = fetched by the pipeline; "manual" = downloaded by a person in a browser and
    # imported with `python -m ingestion.manual_import` (e.g. when robots.txt blocks crawlers).
    retrieval_method: str = "automated"
    http_status: int | None = None
    content_type: str | None = None
    http_last_modified: str | None = None
    file_format: str | None = None  # "pdf" | "html"
    file_path: str | None = None  # relative to the repository root, POSIX style
    size_bytes: int | None = None
    sha256: str | None = None
    page_count: int | None = None
    has_text_layer: bool | None = None
    duplicate_of: str | None = None
    verification_status: VerificationStatus
    error: str | None = None
