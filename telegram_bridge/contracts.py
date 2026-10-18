"""Validated bridge contracts; extra agent metadata is retained."""
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal

Language = Literal["en", "fr", "ar", "derja"]


class Upload(BaseModel):
    """Wire contract only; all document analysis remains in the backend."""
    filename: str = Field(default="upload", max_length=255)
    mime_type: Literal["application/pdf", "image/jpeg", "image/png"]
    data_b64: str = Field(min_length=1)


class ConversationItem(BaseModel):
    key: Literal["photos", "identity_card_copy", "application_form", "old_passport", "residence_proof", "school_proof", "payment_receipt", "birth_certificate", "guardian_authorization"]
    quantity: int | None = Field(default=None,ge=0,le=100)


class ConversationState(BaseModel):
    category: Literal["passport","national_id","business_registration","birth_certificate","general","none"] | None = None
    hints: list[Literal["abroad","loss","renewal","modification","first_time","pilgrimage"]] = Field(default_factory=list,max_length=6)
    residence: Literal["tunisia","abroad"] | None = None
    declared_items: list[ConversationItem] = Field(default_factory=list,max_length=9)
    pending_intent: Literal["required_documents","remaining_documents","fees","processing_time","submission_place","eligibility","procedure_info","form_help","greeting","out_of_scope"] | None = None
    last_intent: Literal["required_documents","remaining_documents","fees","processing_time","submission_place","eligibility","procedure_info","form_help","greeting","out_of_scope"] | None = None
    rne_code: str | None = Field(default=None, pattern=r"^RNE [CIM] \d{3}(?:\.\d+)*$")
    legal_subject: Literal["rne-arrete-2026-35", "rne-law-2018-52-ar", "rne-decree-beneficial-owners", "rne-decree-name-reservation", "rne-decree-2022-298-fees-fr", "rne-decree-law-2022-18-fr"] | None = None
    language: Language | None = None  # language of the last answer (resolves short or ambiguous messages)
    preferred_language: Language | None = None  # optional /language preference; absent = AUTO

class AssistantRequest(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=2000)
    language: Language | None = None
    file: Upload | None = None
    caption: str | None = Field(default=None, max_length=1000)
    mode: Literal["dossier"] | None = None
    context: ConversationState | None = None

    @model_validator(mode="after")
    def has_input(self):
        if not self.text and not self.file:
            raise ValueError("Input required")
        if self.mode and not self.file:
            raise ValueError("Dossier mode requires an upload")
        return self


class DossierFields(BaseModel):
    model_config = ConfigDict(extra="allow")
    filled: list[str] | None = None
    missing: list[str] | None = None
    unreadable: list[str] | None = None
    cannot_verify: list[str] | None = None


class DossierRequirement(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    status: Literal["supported_by_official_source", "not_verified", "official_requirement_unavailable"]
    note: str = ""
    official_quote: str | None = None
    source: dict | None = None


class DossierEvidence(BaseModel):
    model_config = ConfigDict(extra="allow")
    official_checklist_available: bool | None = None
    official_requirements: list[DossierRequirement] | None = None
    requirements_not_verified: list[str] | None = None
    completeness_certified: Literal[False] = False


class DossierReport(BaseModel):
    model_config = ConfigDict(extra="allow")
    form_fields: DossierFields | None = None
    dossier: DossierEvidence | None = None
    readiness_summary: str = ""
    limitations: list[str] = Field(default_factory=list)

class AssistantResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    text: str = Field(min_length=1)
    agent: str | None = None
    context: ConversationState | None = None
    route: dict = Field(default_factory=dict)
    citations: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    recognised: bool | None = None
    missing: list[str] = Field(default_factory=list)
    report: DossierReport | None = None
    form_url: str | None = None
    language: Language | None = None

