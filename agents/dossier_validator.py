"""Smart Administrative Dossier Validator (innovation extension of the Form-Filling Helper).

Given an uploaded official form, produces a structured readiness report that keeps three things apart:

  1. form-field status       - is each visible field filled? (Form-Filling Helper: filled / missing /
                               unreadable; sections the helper cannot analyse are `cannot_verify`)
  2. official requirements    - only requirements that an official source states, quoted verbatim:
                               the instructions printed on the official form itself and the official
                               RNE formalities table; each with `supported_by_official_source`,
                               `not_verified` or `official_requirement_unavailable`
  3. dossier completeness     - never certified: supporting documents, payment, signature and the
                               correctness of the values cannot be checked from a form image.

Whether an official checklist of supporting documents exists is decided by the existing RAG Retriever
and Checklist Builder for the form's procedure; it is never reconstructed by a language model.

Deterministic, no LLM call. Privacy: the upload is processed in memory by the Form-Filling Helper; only
counts and identifiers are logged; field values are never extracted into the report.
"""

import logging
import re
from collections.abc import Callable

from pydantic import BaseModel, Field

from agents import i18n
from agents.checklist_builder import ChecklistBuilder, sources_footer
from agents.corpus import Corpus
from agents.form_helper import FormHelper
from agents.schemas import ComposeRequest, FormCheckRequest, RouteDecision
from rag.evaluation import norm
from rag.retrieval import Citation, RetrievedPassage

log = logging.getLogger(__name__)

TABLE_DOC = "rne-formalities-procedure-table"

# Per supported form: verbatim official statements printed on the form, sections that the field
# detector cannot analyse (checkboxes, signature), the procedure query used to retrieve official
# evidence, and how the form maps to rows of the official RNE table. Every quote and label is checked
# verbatim against the extracted official form by the tests.
FORM_RULES = {
    "rne-form-f001-natural-person-registration": {
        "procedure_query": "Déclaration d'immatriculation d'une personne physique au Registre National des Entreprises",
        "table_filter": {"Genre d'Entreprise": "Personne physique", "Procédure": "Création"},
        "cannot_verify": ["إمضاء المصرّ ح أو من ينوبه بتوكيل", "Type de Pièce d’identité / نوع بطاقة الهوية",
                          "Métier Libéral - مهنة حرّ ة Artisan - حرفيCommerçant -تاجر", "IDENTIFIANT UNIQUE -المعرّف الوحيد"],
    },
    "rne-form-f002-legal-entity-registration": {
        "procedure_query": "Déclaration d'immatriculation d'une personne morale au Registre National des Entreprises",
        "table_filter": {"Genre d'Entreprise": "Personne Morale", "Procédure": "Création"},
        "cannot_verify": ["إمضاء الممثل القانوني أو من ينوبه بتوكيل", "Type de Pièce d’identité / نوع بطاقة الهوية",
                          "RIB -المعرف البنكي", "IDENTIFIANT UNIQUE -المعرّف الوحيد"],
    },
}
# Instructions printed on both RNE forms (Arabic original, verbatim).
QUOTE_ALL_FIELDS = "الرجاء تعمير البيانات كاملة ,بكل دقة و بوضوح و كل بيان ناقص موجب لرفض الطلب"
QUOTE_CONTACT = "تضمين البريد الالكتروني و الهاتف الجوال وجوبي"
QUOTE_DOCUMENTS = "كل تصريح يتضمن بيانات مخالفة للواقع أو تنقصه الوثائق المطلوبة يعتبر لاغيا"
MAX_TABLE_ROWS_SHOWN = 3


class FieldReport(BaseModel):
    label: str  # official bilingual label of the field on the form
    status: str  # filled | missing | unreadable | cannot_verify
    required_by: list[str] = Field(default_factory=list)  # ids of official requirements naming this field


class Requirement(BaseModel):
    id: str
    status: str  # supported_by_official_source | not_verified | official_requirement_unavailable
    official_quote: str | None = None  # verbatim official text (original language)
    source: Citation | None = None
    note: str = ""  # localised explanation


class DossierReport(BaseModel):
    text: str
    recognized: bool
    form_type: dict | None = None
    method: str | None = None
    recognized_fields: list[FieldReport] = Field(default_factory=list)
    filled_fields: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    unreadable_fields: list[str] = Field(default_factory=list)
    unverifiable_fields: list[str] = Field(default_factory=list)
    official_checklist_available: bool = False
    official_requirements: list[Requirement] = Field(default_factory=list)
    requirements_not_verified: list[str] = Field(default_factory=list)
    source_references: list[Citation] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    readiness_summary: str = ""
    error: str | None = None


RetrieveFn = Callable[[str, RouteDecision], list[RetrievedPassage]]


def _arabic_tokens(text: str) -> set[str]:
    """Arabic words with alef variants folded (the form writes both "الإلكتروني" and "الالكتروني")."""
    return {re.sub("[أإآ]", "ا", norm(t)) for t in re.findall(r"[؀-ۿ]+", text) if len(t) > 2}


class DossierValidator:
    def __init__(self, forms: FormHelper, checklist: ChecklistBuilder, corpus: Corpus):
        self.forms = forms
        self.checklist = checklist
        self.corpus = corpus

    def validate(self, req: FormCheckRequest, retrieve: RetrieveFn, default_language: str = "fr") -> DossierReport:
        lang = req.language or default_language
        check = self.forms.check(req, default_language)  # file type, size, recognition, field status
        if check.error or not check.recognised:
            return DossierReport(text=check.text, recognized=False, error=check.error, method=check.method,
                                 limitations=[i18n.t("dossier_lim_unsupported", lang)])
        rules = FORM_RULES.get(check.form_doc_id)
        if rules is None:  # recognised form without validator rules: report fields only
            return DossierReport(text=check.text, recognized=True, method=check.method,
                                 form_type={"doc_id": check.form_doc_id, "title": check.form_title, "url": check.form_url},
                                 limitations=[i18n.t("dossier_lim_no_rules", lang)])
        form_cit = self.corpus.citation(check.form_doc_id)

        # 1. Field status (from the Form-Filling Helper) + sections it cannot analyse.
        status_map = {"filled": "filled", "empty": "missing", "not_found": "unreadable"}
        contact_tokens = _arabic_tokens(QUOTE_CONTACT)
        fields = []
        for f in check.fields:
            arabic = _arabic_tokens(f.label)
            required_by = ["form_all_fields"] + (["form_contact"] if arabic and arabic <= contact_tokens else [])
            fields.append(FieldReport(label=f.label, status=status_map[f.status], required_by=required_by))
        fields += [FieldReport(label=label, status="cannot_verify") for label in rules["cannot_verify"]]

        # 2. Official requirements, each quoted from an official source.
        requirements = [
            Requirement(id="form_all_fields", status="supported_by_official_source", official_quote=QUOTE_ALL_FIELDS,
                        source=form_cit, note=i18n.t("dossier_req_all_fields", lang)),
            Requirement(id="form_contact", status="supported_by_official_source", official_quote=QUOTE_CONTACT,
                        source=form_cit, note=i18n.t("dossier_req_contact", lang)),
        ]
        # Supporting documents: is there an official checklist? Ask the existing agents.
        route = RouteDecision(language=lang, intent="required_documents", procedure_category="business_registration",
                              next_agent="checklist", method="rules")
        passages = retrieve(rules["procedure_query"], route)
        built = self.checklist.build(ComposeRequest(query=rules["procedure_query"], route=route, passages=passages))
        checklist_available = any(s.kind == "documents" for s in built.sections)
        requirements.append(Requirement(
            id="supporting_documents",
            status="supported_by_official_source" if checklist_available else "official_requirement_unavailable",
            official_quote=QUOTE_DOCUMENTS, source=form_cit,
            note=i18n.t("dossier_req_documents_ok" if checklist_available else "dossier_req_documents_missing", lang)))
        # Fee and deadline: rows of the official table matching the form's procedure.
        table_rows = self._table_rows(rules["table_filter"])
        table_cit = self.corpus.citation(TABLE_DOC)
        if table_rows:
            requirements.append(Requirement(
                id="registration_fee", status="not_verified",
                official_quote="\n\n".join(table_rows[:MAX_TABLE_ROWS_SHOWN]), source=table_cit,
                note=i18n.t("dossier_req_fee", lang, n=str(len(table_rows)))))

        unverified = [i18n.t(k, lang) for k in ("dossier_nv_documents", "dossier_nv_payment", "dossier_nv_signature",
                                                "dossier_nv_values")]
        refs: list[Citation] = [c for c in [form_cit, table_cit] if c]
        for c in built.citations:  # evidence used by the Checklist Builder, except other forms
            if c.doc_id not in {r.doc_id for r in refs} and c.document_type != "official_form":
                refs.append(c)
        report = DossierReport(
            text="", recognized=True, method=check.method,
            form_type={"doc_id": check.form_doc_id, "title": check.form_title, "url": check.form_url},
            recognized_fields=fields,
            filled_fields=[f.label for f in fields if f.status == "filled"],
            missing_fields=[f.label for f in fields if f.status == "missing"],
            unreadable_fields=[f.label for f in fields if f.status == "unreadable"],
            unverifiable_fields=[f.label for f in fields if f.status == "cannot_verify"],
            official_checklist_available=checklist_available, official_requirements=requirements,
            requirements_not_verified=unverified, source_references=refs,
            limitations=[i18n.t("dossier_lim_detection", lang), i18n.t("dossier_lim_not_certification", lang)],
        )
        report.readiness_summary = self._summary(report, lang)
        report.text = self._render(report, lang, check.form_title or "")
        log.info("dossier_check", extra={"fields": {
            "form": check.form_doc_id, "method": check.method, "filled": len(report.filled_fields),
            "missing": len(report.missing_fields), "unreadable": len(report.unreadable_fields),
            "rag_passages": len(passages), "checklist_builder_found": built.found,
            "checklist_available": checklist_available}})
        return report

    def _table_rows(self, criteria: dict[str, str]) -> list[str]:
        rows = []
        for b in self.corpus.blocks(TABLE_DOC):
            if b["kind"] != "table_row":
                continue
            fields = dict(line.split(": ", 1) for line in b["text"].splitlines() if ": " in line)
            if all(fields.get(k, "").strip().lower() == v.lower() for k, v in criteria.items()):
                rows.append(b["text"])
        return rows

    @staticmethod
    def _summary(r: DossierReport, lang: str) -> str:
        detected = len(r.filled_fields) + len(r.missing_fields) + len(r.unreadable_fields)
        if r.missing_fields or r.unreadable_fields:
            first = i18n.t("dossier_sum_attention", lang, missing=str(len(r.missing_fields)),
                           unreadable=str(len(r.unreadable_fields)), total=str(detected))
        else:
            first = i18n.t("dossier_sum_filled", lang, total=str(detected))
        second = i18n.t("dossier_sum_no_checklist" if not r.official_checklist_available else "dossier_sum_checklist", lang)
        return f"{first} {second} {i18n.t('dossier_sum_not_certified', lang)}"

    @staticmethod
    def _render(r: DossierReport, lang: str, title: str) -> str:
        out = [f"🗂️ {i18n.t('dossier_title', lang)}", f"📝 {i18n.t('form_identified', lang, title=title)}", "",
               r.readiness_summary, ""]
        if r.filled_fields:
            out += [f"✅ {i18n.t('dossier_filled', lang)}:"] + [f"• {x}" for x in r.filled_fields] + [""]
        attention = r.missing_fields + r.unreadable_fields
        if attention:
            out.append(f"❗ {i18n.t('dossier_attention', lang)}:")
            mandatory = {f.label for f in r.recognized_fields if "form_contact" in f.required_by}
            out += [f"• {x}" + (f" ({i18n.t('dossier_mandatory', lang)})" if x in mandatory else "") for x in r.missing_fields]
            out += [f"• {x} ({i18n.t('dossier_unreadable', lang)})" for x in r.unreadable_fields]
            out.append("")
        out += [f"❔ {i18n.t('dossier_cannot_verify', lang)}:"] + [f"• {x}" for x in r.unverifiable_fields] + [""]
        out.append(f"📜 {i18n.t('dossier_requirements', lang)}:")
        for q in r.official_requirements:
            out.append(f"• [{i18n.t('dossier_status_' + q.status, lang)}] {q.note}")
            if q.official_quote and q.id != "registration_fee":
                out.append(f"  « {q.official_quote} »")
        out += ["", f"⚠️ {i18n.t('dossier_not_verified_title', lang)}:"] + [f"• {x}" for x in r.requirements_not_verified]
        return "\n".join(out + sources_footer(lang, r.source_references))
