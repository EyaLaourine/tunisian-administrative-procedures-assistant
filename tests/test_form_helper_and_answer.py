"""Form-Filling Helper (on the real official blank forms) and the Grounded Answer agent."""

import base64
import glob

import fitz
import pytest

from agents.answer import GroundedAnswerer
from agents.corpus import Corpus
from agents.form_helper import FormHelper
from agents.llm import LLMResult
from agents.prompts import PromptLibrary
from agents.schemas import ComposeRequest, FormCheckRequest, RouteDecision
from backend.settings import REPO_ROOT, get_settings
from rag.retrieval import Citation, RetrievedPassage

F002 = "rne-form-f002-legal-entity-registration"


@pytest.fixture(scope="module")
def helper() -> FormHelper:
    s = get_settings()
    h = FormHelper(Corpus(s.raw_dir, s.processed_dir), max_bytes=s.max_upload_bytes)
    if F002 not in h.templates():
        pytest.skip("official RNE forms not downloaded")
    return h


def _official_pdf(doc_id: str) -> bytes:
    path = glob.glob(str(REPO_ROOT / "data" / "raw" / doc_id / "*.pdf"))[0]
    return open(path, "rb").read()


def _req(data: bytes, mime="application/pdf", lang="fr") -> FormCheckRequest:
    return FormCheckRequest(mime_type=mime, data_b64=base64.b64encode(data).decode(), language=lang)


def test_blank_official_forms_are_recognised_with_all_fields_empty(helper):
    for doc_id in helper.templates():
        res = helper.check(_req(_official_pdf(doc_id)))
        assert res.recognised and res.form_doc_id == doc_id and res.method == "text_layer"
        assert res.fields and all(f.status == "empty" for f in res.fields)
        assert res.form_url.startswith("https://")


def test_filled_field_is_detected(helper):
    doc = fitz.open(stream=_official_pdf(F002), filetype="pdf")
    field = next(f for f in helper.templates()[F002].fields if f.label.startswith("E-mail"))
    doc[0].insert_text((field.region[0] + 80, field.region[3] - 5), "placeholder", fontsize=9)
    res = helper.check(_req(doc.tobytes(), lang="en"))
    statuses = {f.label: f.status for f in res.fields}
    assert statuses[field.label] == "filled"
    assert sum(1 for s in statuses.values() if s == "filled") == 1
    assert field.label not in res.missing and "Fields that look empty" in res.text


def test_rejects_invalid_or_unsupported_uploads(helper):
    assert helper.check(FormCheckRequest(mime_type="application/pdf", data_b64="%%%")).error
    assert "unsupported" in helper.check(_req(b"hello", mime="text/plain")).error
    small = FormHelper(helper.corpus, max_bytes=10)
    assert "larger" in small.check(_req(_official_pdf(F002))).error


def test_unrelated_pdf_is_not_recognised(helper, make_pdf):
    path = make_pdf([[("Neutral placeholder line " * 3, 11)] * 5])
    res = helper.check(_req(path.read_bytes()))
    assert not res.recognised and not res.fields


# ---------------------------------------------------------------------- grounded answer
def _passages(n: int) -> list[RetrievedPassage]:
    out = []
    for i in range(n):
        doc = "doc-a" if i < 2 else "doc-b"
        cit = Citation(doc_id=doc, title=f"Title {doc}", source_organization="Org", url=f"https://example.org/{doc}",
                       official_reference=None, publication_date=None, applicability="unverified",
                       page_start=i + 1, page_end=i + 1, heading_path=[], sha256="0" * 64)
        out.append(RetrievedPassage(score=0.8, text=f"placeholder passage {i}", chunk_id=f"c{i}", citation=cit))
    return out


class _FakeLLM:
    def __init__(self, text, truncated=False):
        self.text, self.truncated = text, truncated

    def run(self, spec, **values):
        return LLMResult(text=self.text, model="fake", prompt_ref=spec.ref, seconds=0, eval_tokens=0,
                         truncated=self.truncated)


ROUTE = RouteDecision(language="en", intent="procedure_info", procedure_category="general",
                      next_agent="answer", method="rules")


def _answer(llm, n=3):
    a = GroundedAnswerer(llm, PromptLibrary(REPO_ROOT / "prompts"))
    return a.answer(ComposeRequest(query="question", route=ROUTE, passages=_passages(n)))


def test_answer_with_valid_citations_is_merged_per_document():
    res = _answer(_FakeLLM("Fact one [1], [2]. Fact two [3]."))
    assert res.method == "llm_grounded"
    assert [c.doc_id for c in res.citations] == ["doc-a", "doc-b"]
    assert res.text.startswith("Fact one [1]. Fact two [2].")
    assert "p. 1, 2" in res.text


def test_answer_without_citations_or_with_invalid_ones_falls_back_to_passages():
    for text in ("An unsupported claim.", "A claim [7]."):
        res = _answer(_FakeLLM(text))
        assert res.method == "passages_fallback"
        assert "placeholder passage 0" in res.text


def test_truncated_answer_is_cut_at_last_sentence():
    res = _answer(_FakeLLM("Complete sentence [1]. Second complete sentence [1]. Cut off mid", truncated=True))
    assert "Cut off" not in res.text


def test_no_passages_gives_not_found():
    a = GroundedAnswerer(_FakeLLM("x [1]"), PromptLibrary(REPO_ROOT / "prompts"))
    res = a.answer(ComposeRequest(query="q", route=ROUTE, passages=[]))
    assert not res.found and res.method == "none"
