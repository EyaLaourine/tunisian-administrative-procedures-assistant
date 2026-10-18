"""Request/response models exchanged between agents (and with n8n)."""

from typing import Literal

from pydantic import BaseModel, Field

from rag.retrieval import Citation, RetrievedPassage

Language = Literal["en", "fr", "ar", "derja"]
Intent = Literal[
    "required_documents", "fees", "processing_time", "submission_place", "eligibility",
    "procedure_info", "form_help", "greeting", "out_of_scope", "remaining_documents",
]
Category = Literal["passport", "national_id", "business_registration", "birth_certificate", "general", "none"]
NextAgent = Literal["checklist", "answer", "reply"]


ItemKey = Literal["photos", "identity_card_copy", "application_form", "old_passport", "residence_proof", "school_proof", "payment_receipt", "birth_certificate", "guardian_authorization"]
Hint = Literal["abroad", "loss", "renewal", "modification", "first_time", "pilgrimage"]


class DeclaredItem(BaseModel):
    key: ItemKey
    quantity: int | None = Field(default=None, ge=0, le=100)


class DialogueContext(BaseModel):
    category: Category | None = None
    hints: list[Hint] = Field(default_factory=list, max_length=6)
    residence: Literal["tunisia", "abroad"] | None = None
    declared_items: list[DeclaredItem] = Field(default_factory=list, max_length=9)
    pending_intent: Intent | None = None
    last_intent: Intent | None = None
    rne_code: str | None = Field(default=None, pattern=r"^RNE [CIM] \d{3}(?:\.\d+)*$")
    legal_subject: Literal["rne-arrete-2026-35", "rne-law-2018-52-ar", "rne-decree-beneficial-owners", "rne-decree-name-reservation", "rne-decree-2022-298-fees-fr", "rne-decree-law-2022-18-fr"] | None = None
    # Conversation language (set by the router on every turn) and the user's optional menu preference.
    # Both only resolve short or ambiguous messages; a clearly written message is answered in its own language.
    language: Language | None = None
    preferred_language: Language | None = None


class RouteRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    language: Language | None = None  # forced language (otherwise detected)
    context: DialogueContext | None = None


class RouteDecision(BaseModel):
    language: Language
    intent: Intent
    procedure_category: Category
    hints: list[str] = Field(default_factory=list)  # e.g. "abroad", "renewal", "loss"
    next_agent: NextAgent
    reply: str | None = None  # final text when next_agent == "reply"
    method: Literal["rules", "llm", "default"]
    prompt_ref: str | None = None
    context: DialogueContext | None = None
    retrieval_query: str | None = Field(default=None, max_length=2000)
    # Language of `reply` when it differs from the conversation language: a courtesy message ("يعطيك الصحة") is
    # answered in its own language, while `language` keeps the conversation language that clients remember.
    reply_language: Language | None = None


class AgentRetrieveRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    route: RouteDecision
    top_k: int = Field(default=8, ge=1, le=30)


class AgentRetrieveResponse(BaseModel):
    expanded_query: str
    filters: dict
    passages: list[RetrievedPassage]


class ComposeRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    route: RouteDecision
    passages: list[RetrievedPassage]


class ChecklistSection(BaseModel):
    kind: Literal["conditions", "documents", "place", "delay", "fees", "other"]
    heading: str  # heading exactly as printed in the official document
    items: list[str]  # verbatim official text
    translated_items: list[str] | None = None


class ChecklistResult(BaseModel):
    text: str  # rendered message for the user
    found: bool
    doc_id: str | None = None
    scenario: str | None = None
    source_language: str | None = None
    sections: list[ChecklistSection] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    translation: dict | None = None  # {model, prompt_ref, validated}
    # Discrepancy between parallel official versions on fee amounts; shown only when the answer contains an amount
    # or fees were asked for (see ChecklistBuilder._attach_fee_warning).
    fee_discrepancy: str | None = None


class AnswerResult(BaseModel):
    text: str
    found: bool
    method: Literal["llm_grounded", "passages_fallback", "none"]
    citations: list[Citation] = Field(default_factory=list)
    prompt_ref: str | None = None
    model: str | None = None
    seconds: float | None = None
    verification: dict | None = None  # topic and numerical-claim checks (agents/verification.py)


class FormCheckRequest(BaseModel):
    filename: str = Field(default="upload", max_length=255)
    mime_type: str = Field(max_length=100)
    data_b64: str
    language: Language | None = None
    caption: str | None = Field(default=None, max_length=1000)


class FormField(BaseModel):
    label: str
    status: Literal["filled", "empty", "not_found"]
    role: Literal["required", "optional", "conditional", "administration"] = "required"


class FormCheckResult(BaseModel):
    text: str
    recognised: bool
    method: str | None = None  # "text_layer" | "ocr"
    form_doc_id: str | None = None
    form_title: str | None = None
    form_url: str | None = None
    match_score: float | None = None
    fields: list[FormField] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)  # empty required applicant fields
    if_applicable: list[str] = Field(default_factory=list)  # empty conditional fields
    error: str | None = None
