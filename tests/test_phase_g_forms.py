"""Phase G: recognition of the Ministry of the Interior CIN (01.pdf) and passport (02.pdf) application
forms, and the role of every field (applicant required / optional / conditional / administration-only).

Completed copies are synthesised from the stored official blank forms with neutral placeholder text."""

import base64
import glob
import json

import fitz
import pytest

from agents import form_roles, i18n
from agents.corpus import Corpus
from agents.form_helper import FormHelper, ocr_available
from agents.schemas import FormCheckRequest
from backend.settings import REPO_ROOT, get_settings

CIN = "interior-national-id-application-form"
PASSPORT = "interior-passport-application-form"
F001 = "rne-form-f001-natural-person-registration"
F002 = "rne-form-f002-legal-entity-registration"
SHA = {CIN: "1ccece129f681dc936c65ea22921bc83e69760d2607d58a71fb6bb9731d2fe63",
       PASSPORT: "7e667ead43869ad17d8a9ac5b881dd3bf27afce9e8d3cdae5a5e8341d598168d"}


@pytest.fixture(scope="module")
def helper() -> FormHelper:
    s = get_settings()
    h = FormHelper(Corpus(s.raw_dir, s.processed_dir), max_bytes=s.max_upload_bytes)
    if not {CIN, PASSPORT, F001, F002} <= set(h.templates()):
        pytest.skip("official forms not stored")
    return h


def _official_pdf(doc_id: str) -> bytes:
    return open(glob.glob(str(REPO_ROOT / "data" / "raw" / doc_id / "*.pdf"))[0], "rb").read()


def _req(data: bytes, mime="application/pdf", lang="fr") -> FormCheckRequest:
    return FormCheckRequest(mime_type=mime, data_b64=base64.b64encode(data).decode(), language=lang)


def _fill(helper, doc_id: str, roles: set[str], only: set[int] | None = None) -> fitz.Document:
    """Official blank form with a neutral placeholder written on the dot leaders of the chosen fields."""
    doc = fitz.open(stream=_official_pdf(doc_id), filetype="pdf")
    for i, f in enumerate(helper.templates()[doc_id].fields):
        if f.role in roles and (only is None or i in only):
            x0, _, x1, y1 = f.region
            doc[f.page].insert_text((x0 + min(20, (x1 - x0) / 4), y1 - 3), "Placeholder", fontsize=8)
    return doc


def _labels(helper, doc_id: str, role: str) -> list[str]:
    return [f.label for f in helper.templates()[doc_id].fields if f.role == role]


# ---------------------------------------------------------------- registry and provenance
def test_both_forms_are_registered_and_stored_from_the_official_listing():
    s = get_settings()
    import yaml
    registry = {e["doc_id"]: e for e in yaml.safe_load(s.registry_path.read_text(encoding="utf-8"))["sources"]}
    records = {r["doc_id"]: r for r in json.loads((s.raw_dir / "manifest.json").read_text(encoding="utf-8"))["records"]}
    for doc_id, n in [(CIN, "01"), (PASSPORT, "02")]:
        e, r = registry[doc_id], records[doc_id]
        assert e["status"] == "approved" and e["document_type"] == "official_form"
        assert e["url"] == f"https://services.interieur.gov.tn/uploads/imprimes/{n}.pdf"
        assert e["language"] == "unknown" and e["publication_date"] is None  # never guessed
        assert r["retrieval_method"] == "manual" and r["sha256"] == SHA[doc_id] and r["applicability"] == "unverified"
        assert (REPO_ROOT / r["file_path"]).name.startswith(SHA[doc_id][:12])


# ---------------------------------------------------------------- blank forms
@pytest.mark.parametrize("doc_id,counts", [
    (CIN, {"required": 10, "optional": 1, "conditional": 3, "administration": 7}),
    (PASSPORT, {"required": 10, "optional": 0, "conditional": 4, "administration": 14}),
])
def test_blank_interior_form_is_recognised_and_only_applicant_fields_are_reported(helper, doc_id, counts):
    res = helper.check(_req(_official_pdf(doc_id)))
    assert res.recognised and res.form_doc_id == doc_id and res.match_score == 1.0 and res.method == "text_layer"
    assert {k: sum(f.role == k for f in res.fields) for k in counts} == counts
    assert res.missing == _labels(helper, doc_id, "required")
    assert res.if_applicable == _labels(helper, doc_id, "conditional")
    for label in _labels(helper, doc_id, "administration") + _labels(helper, doc_id, "optional"):
        assert f"• {label}\n" not in res.text + "\n"
    assert i18n.t("form_admin_skipped", "fr", n=str(counts["administration"])) in res.text
    assert i18n.t("form_not_checked", "fr") in res.text and "• التوقيع" in res.text


def test_administration_sections_follow_the_printed_headings(helper):
    cin, passport = helper.templates()[CIN].fields, helper.templates()[PASSPORT].fields
    # CIN: "بيانـات خاصة بالإدارة" at y 475 of page 1; page 2 is administration only.
    assert [i for i, f in enumerate(cin) if f.role == "administration"] == list(range(14, 21))
    # Passport: "خــاص بالإدارة" at y 662 of page 1 (deposit receipt below it); page 2 is administration only.
    assert [i for i, f in enumerate(passport) if f.role == "administration"] == list(range(11, 15)) + list(range(18, 28))
    assert all(f.role == "administration" for f in cin + passport if f.page == 1)


def test_conditional_fields_are_spouse_previous_id_and_other_nationalities(helper):
    assert _labels(helper, CIN, "conditional") == ["إسم الزوج(ة)", "إسم الزوج(ة) — لقبه(ها)", "الهوية القديمة"]
    assert _labels(helper, PASSPORT, "conditional") == [
        "Prénom de l’Epoux(se) / إسم الزوج(ة)", "Nom de l’Epoux(se) / لقب الزوج(ة)",
        "Nationalité de l’Epoux(se) / جنسية الزوج(ة)", "جنسيات أخرى"]
    assert _labels(helper, CIN, "optional") == ["عنوان السكنى (2)"]


def test_cin_and_passport_are_not_confused(helper):
    for doc_id, other in [(CIN, PASSPORT), (PASSPORT, CIN)]:
        res = helper.check(_req(_fill(helper, doc_id, {"required", "conditional"}).tobytes()))
        assert res.form_doc_id == doc_id != other


# ---------------------------------------------------------------- synthetic completed copies
@pytest.mark.parametrize("doc_id", [CIN, PASSPORT])
def test_required_fields_filled_leaves_only_conditional_fields(helper, doc_id):
    res = helper.check(_req(_fill(helper, doc_id, {"required"}).tobytes(), lang="en"))
    assert res.recognised and res.missing == []
    assert res.if_applicable == _labels(helper, doc_id, "conditional")
    assert i18n.t("form_required_complete", "en") in res.text and i18n.t("form_missing", "en") not in res.text


@pytest.mark.parametrize("doc_id", [CIN, PASSPORT])
def test_every_applicant_field_filled_reports_nothing_missing(helper, doc_id):
    res = helper.check(_req(_fill(helper, doc_id, {"required", "optional", "conditional"}).tobytes(), lang="ar"))
    assert res.missing == [] and res.if_applicable == []
    assert all(f.status == "filled" for f in res.fields if f.role != "administration")
    assert all(f.status == "empty" for f in res.fields if f.role == "administration")
    assert i18n.t("form_required_complete", "ar") in res.text


@pytest.mark.parametrize("doc_id", [CIN, PASSPORT])
def test_partially_filled_copy_reports_exactly_the_empty_required_fields(helper, doc_id):
    required = [i for i, f in enumerate(helper.templates()[doc_id].fields) if f.role == "required"]
    filled = set(required[::2])
    res = helper.check(_req(_fill(helper, doc_id, {"required"}, only=filled).tobytes()))
    fields = helper.templates()[doc_id].fields
    assert res.missing == [fields[i].label for i in required if i not in filled]


@pytest.mark.parametrize("doc_id", [CIN, PASSPORT])
def test_administration_fields_never_count(helper, doc_id):
    res = helper.check(_req(_fill(helper, doc_id, {"administration"}).tobytes()))
    assert res.missing == _labels(helper, doc_id, "required")


# ---------------------------------------------------------------- rule guards
def test_rules_apply_only_to_the_pinned_official_file(helper):
    from agents.form_helper import _template_for, norm_token
    raw = _template_for(helper.templates()[CIN].path, 0.0)
    fields, unchecked = form_roles.assign(CIN, "0" * 64, raw.fields, raw.words, norm_token)
    assert unchecked == () and not any(f.role in ("conditional", "optional") for f in fields)
    assert [f.label for f in fields] == [f.label for f in raw.fields]  # no printed-label overrides
    assert sum(f.role == "administration" for f in fields) == 7  # the printed heading still applies


def test_rules_fall_back_when_the_derived_labels_change(helper):
    from agents.form_helper import _template_for, norm_token
    raw = _template_for(helper.templates()[PASSPORT].path, 0.0)
    shifted = raw.fields[1:]
    fields, unchecked = form_roles.assign(PASSPORT, SHA[PASSPORT], shifted, raw.words, norm_token)
    assert unchecked == () and not any(f.role == "conditional" for f in fields)


# ---------------------------------------------------------------- RNE regression
@pytest.mark.parametrize("doc_id", [F001, F002])
def test_rne_forms_are_unchanged(helper, doc_id):
    res = helper.check(_req(_official_pdf(doc_id)))
    assert res.recognised and res.form_doc_id == doc_id and res.match_score == 1.0
    assert all(f.role == "required" and f.status == "empty" for f in res.fields)
    assert res.missing == [f.label for f in res.fields] and res.if_applicable == []
    assert "🏛" not in res.text and i18n.t("form_missing", "fr") in res.text
    assert res.manual_verification and i18n.t("form_not_checked", "fr") in res.text


@pytest.mark.parametrize("lang", ["fr", "en", "ar", "derja"])
def test_unrecognised_file_names_every_supported_form(helper, make_pdf, lang):
    res = helper.check(_req(make_pdf([[("Neutral placeholder line " * 3, 11)] * 5]).read_bytes(), lang=lang))
    assert not res.recognised and "RNE F-001" in res.text and "RNE F-002" in res.text
    for doc_id in (CIN, PASSPORT):
        assert i18n.FORM_NAMES[doc_id][lang] in res.text


# ---------------------------------------------------------------- scanned copies (OCR)
needs_ocr = pytest.mark.skipif(not ocr_available(), reason="tesseract is not installed (runs in the backend image)")


def _scan(doc: fitz.Document) -> tuple[bytes, bytes]:
    """(150 dpi PNG of page 1, 200 dpi JPEG image-only PDF of every page): a phone photo and a scanner PDF."""
    png = doc[0].get_pixmap(dpi=150, colorspace=fitz.csGRAY).tobytes("png")
    out = fitz.open()
    for page in doc:
        img = page.get_pixmap(dpi=200, colorspace=fitz.csGRAY).tobytes("jpg", jpg_quality=85)
        out.new_page(width=page.rect.width, height=page.rect.height).insert_image(page.rect, stream=img)
    return png, out.tobytes()


@needs_ocr
@pytest.mark.parametrize("doc_id", [CIN, PASSPORT])
def test_scanned_blank_and_completed_copies(helper, doc_id):
    # The single-column OCR pass misses the Arabic label columns of these forms; the sparse-text pass
    # recognises them and aligns the scan on Arabic anchor words, so the ink comparison runs.
    blank = _scan(fitz.open(stream=_official_pdf(doc_id), filetype="pdf"))
    required = _scan(_fill(helper, doc_id, {"required"}))
    full = _scan(_fill(helper, doc_id, {"required", "optional", "conditional"}))
    for (png, pdf), missing, if_applicable in [
        (blank, _labels(helper, doc_id, "required"), _labels(helper, doc_id, "conditional")),
        (required, [], _labels(helper, doc_id, "conditional")),
        (full, [], []),
    ]:
        for data, mime in [(png, "image/png"), (pdf, "application/pdf")]:
            res = helper.check(_req(data, mime))
            assert res.recognised and res.form_doc_id == doc_id and res.method == "ocr_ink"
            assert res.missing == missing and res.if_applicable == if_applicable
