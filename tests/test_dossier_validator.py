"""Smart Administrative Dossier Validator (no running services needed).

Authenticity: the form templates are the official RNE blank forms from data/raw/. Filled variants are
TEST FIXTURES: neutral placeholder text written onto a copy of the blank form; they are not
administrative evidence and contain no personal data.
"""

import base64
import glob
import logging

import fitz
import pytest

from agents.checklist_builder import ChecklistBuilder
from agents.corpus import Corpus
from agents.dossier_validator import FORM_RULES, QUOTE_ALL_FIELDS, QUOTE_CONTACT, QUOTE_DOCUMENTS, DossierValidator
from agents.form_helper import FormHelper
from agents.prompts import PromptLibrary
from agents.schemas import ChecklistResult, ChecklistSection, FormCheckRequest, FormCheckResult, FormField
from backend.settings import REPO_ROOT, get_settings
from rag.evaluation import norm

F001, F002 = "rne-form-f001-natural-person-registration", "rne-form-f002-legal-entity-registration"
PLACEHOLDER = "PLACEHOLDER 12"  # test fixture text, not personal data


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    s = get_settings()
    c = Corpus(s.raw_dir, s.processed_dir)
    if F002 not in FormHelper(c, s.max_upload_bytes).templates():
        pytest.skip("official RNE forms not available")
    return c


@pytest.fixture(scope="module")
def validator(corpus) -> DossierValidator:
    s = get_settings()
    forms = FormHelper(corpus, s.max_upload_bytes)
    return DossierValidator(forms, ChecklistBuilder(corpus, None, PromptLibrary(REPO_ROOT / "prompts")), corpus)


def no_retrieval(query, route):
    return []


def _pdf(doc_id: str) -> bytes:
    return open(glob.glob(str(REPO_ROOT / "data" / "raw" / doc_id / "*.pdf"))[0], "rb").read()


def _req(data: bytes, mime="application/pdf", lang="en") -> FormCheckRequest:
    return FormCheckRequest(mime_type=mime, data_b64=base64.b64encode(data).decode(), language=lang)


def _filled_copy(validator, doc_id: str, label_prefixes: tuple[str, ...]) -> bytes:
    """TEST FIXTURE: placeholder text on the dotted lines of the given fields of the official blank form."""
    doc = fitz.open(stream=_pdf(doc_id), filetype="pdf")
    for f in validator.forms.templates()[doc_id].fields:
        if f.label.startswith(label_prefixes):
            doc[0].insert_text((f.region[0] + 10, f.region[3] - 4), PLACEHOLDER, fontsize=9)
    return doc.tobytes()


def _official_text(corpus, doc_id: str) -> str:
    return norm("".join(b["text"] for b in corpus.blocks(doc_id)))


# 1. supported-form recognition ---------------------------------------------------------------
@pytest.mark.parametrize("doc_id,n_fields", [(F001, 7), (F002, 8)])
def test_official_blank_forms_are_recognised_with_all_fields_missing(validator, doc_id, n_fields):
    r = validator.validate(_req(_pdf(doc_id)), no_retrieval)
    assert r.recognized and r.form_type["doc_id"] == doc_id
    assert len(r.missing_fields) == n_fields and not r.filled_fields and not r.unreadable_fields
    assert r.unverifiable_fields == FORM_RULES[doc_id]["cannot_verify"]


# 2. unsupported / invalid input ----------------------------------------------------------------
def test_unrelated_pdf_is_rejected(validator, make_pdf):
    path = make_pdf([[("Neutral placeholder line " * 3, 11)] * 5])
    r = validator.validate(_req(path.read_bytes()), no_retrieval)
    assert not r.recognized and not r.recognized_fields and r.limitations


def test_invalid_type_and_oversized_files_are_rejected(validator, corpus):
    assert validator.validate(_req(b"hello", mime="text/plain"), no_retrieval).error
    small = DossierValidator(FormHelper(corpus, max_bytes=10), validator.checklist, corpus)
    assert "larger" in small.validate(_req(_pdf(F002)), no_retrieval).error


# 3-4. filled and missing fields; mandatory contact fields ----------------------------------------
def test_filled_fields_are_separated_from_missing_ones(validator):
    r = validator.validate(_req(_filled_copy(validator, F002, ("E-mail", "Dénomination"))), no_retrieval)
    assert {x.split(" /")[0] for x in r.filled_fields} == {"E-mail", "Dénomination"}
    assert not any(x.startswith(("E-mail", "Dénomination")) for x in r.missing_fields)
    gsm = next(f for f in r.recognized_fields if f.label.startswith("N°GSM"))
    assert gsm.status == "missing" and "form_contact" in gsm.required_by
    assert "N°GSM / الهاتف الجوال (mandatory according to the form)" in r.text
    mandatory = {f.label.split(" /")[0] for f in r.recognized_fields if "form_contact" in f.required_by}
    assert mandatory == {"E-mail", "N°GSM"}  # exactly the two fields named by the official instruction


# 5. unreadable fields ----------------------------------------------------------------------------
def test_unreadable_fields_are_reported_as_such(validator, corpus):
    class StubForms:
        def check(self, req, default_language="fr"):
            return FormCheckResult(text="", recognised=True, method="ocr_ink", form_doc_id=F002,
                                   form_title="t", form_url="https://x",
                                   fields=[FormField(label="E-mail / البريد الإلكتروني", status="not_found"),
                                           FormField(label="Dénomination / إسم المؤسسة", status="filled")])
    r = DossierValidator(StubForms(), validator.checklist, corpus).validate(_req(b"x"), no_retrieval)
    assert r.unreadable_fields == ["E-mail / البريد الإلكتروني"] and r.filled_fields == ["Dénomination / إسم المؤسسة"]
    assert "could not be read" in r.text


# 6. missing official checklist -------------------------------------------------------------------
def test_missing_official_checklist_means_completeness_cannot_be_assessed(validator):
    r = validator.validate(_req(_pdf(F001)), no_retrieval)
    docs = next(q for q in r.official_requirements if q.id == "supporting_documents")
    assert not r.official_checklist_available and docs.status == "official_requirement_unavailable"
    assert "cannot be assessed" in r.readiness_summary


def test_checklist_status_follows_the_checklist_builder(validator, corpus):
    class BuilderWithDocuments:
        def build(self, req):
            return ChecklistResult(text="", found=True, sections=[ChecklistSection(kind="documents", heading="h", items=["i"])])
    r = DossierValidator(validator.forms, BuilderWithDocuments(), corpus).validate(_req(_pdf(F001)), no_retrieval)
    assert r.official_checklist_available
    assert next(q for q in r.official_requirements if q.id == "supporting_documents").status == "supported_by_official_source"


# 7-8. official sources only; no invented requirements -------------------------------------------
@pytest.mark.parametrize("doc_id", [F001, F002])
def test_every_requirement_and_label_is_quoted_from_an_official_source(validator, corpus, doc_id):
    r = validator.validate(_req(_pdf(doc_id)), no_retrieval)
    form_text = _official_text(corpus, doc_id)
    table_text = _official_text(corpus, "rne-formalities-procedure-table")
    for q in r.official_requirements:
        assert q.source is not None and q.source.url.startswith("https://")
        for part in q.official_quote.split("\n\n"):
            assert norm(part) in (form_text if q.source.doc_id == doc_id else table_text), q.id
    for label in FORM_RULES[doc_id]["cannot_verify"]:
        assert norm(label) in form_text
    for quote in (QUOTE_ALL_FIELDS, QUOTE_CONTACT, QUOTE_DOCUMENTS):
        assert norm(quote) in form_text
    refs = [c.doc_id for c in r.source_references]
    assert refs[0] == doc_id and "rne-formalities-procedure-table" in refs
    assert not ({F001, F002} - {doc_id}) & set(refs)  # the other form is not cited


# 9. no legal validation claims ---------------------------------------------------------------------
def test_report_never_claims_validation(validator):
    r = validator.validate(_req(_filled_copy(validator, F002, ("",))), no_retrieval)  # every field filled
    assert not r.missing_fields and "All 8 detected fields appear filled" in r.readiness_summary
    assert "This report is not an official validation." in r.readiness_summary
    lowered = r.text.lower()
    for claim in ("approved", "certified", "dossier is complete", "valid dossier"):
        assert claim not in lowered
    assert len(r.requirements_not_verified) == 4


# 10. privacy -----------------------------------------------------------------------------------------
def test_field_values_are_not_reported_or_logged(validator, caplog):
    with caplog.at_level(logging.DEBUG):
        r = validator.validate(_req(_filled_copy(validator, F002, ("E-mail",))), no_retrieval)
    assert PLACEHOLDER not in r.model_dump_json()
    assert PLACEHOLDER not in caplog.text


# 11. multilingual summaries ------------------------------------------------------------------------
@pytest.mark.parametrize("lang,phrase", [
    ("fr", "ne peut pas être évaluée"), ("ar", "لا يمكن تقييم اكتمال الملف"),
    ("derja", "ما نجمش نقيّم"), ("en", "cannot be assessed"),
])
def test_summary_in_user_language(validator, lang, phrase):
    r = validator.validate(_req(_pdf(F002), lang=lang), no_retrieval)
    assert phrase in r.readiness_summary
    assert QUOTE_CONTACT in r.text  # official quotation kept in its original language


# 12. compatibility with the Form-Filling Helper -------------------------------------------------
def test_field_statuses_match_the_form_filling_helper(validator):
    req = _req(_filled_copy(validator, F001, ("E-mail",)))
    helper = validator.forms.check(req)
    report = validator.validate(req, no_retrieval)
    mapping = {"filled": "filled", "empty": "missing", "not_found": "unreadable"}
    assert [(f.label, mapping[f.status]) for f in helper.fields] == \
        [(f.label, f.status) for f in report.recognized_fields if f.status != "cannot_verify"]
