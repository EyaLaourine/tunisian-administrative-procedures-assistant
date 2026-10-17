"""Phase 3 retrieval and agent changes (no running services needed)."""

import pytest

from agents.checklist_builder import ChecklistBuilder
from agents.corpus import Corpus
from agents.intent_router import IntentRouter
from agents.prompts import PromptLibrary
from agents.retriever import arabizi_terms, entity_terms, expand_query
from agents.schemas import ComposeRequest, RouteDecision, RouteRequest
from backend.settings import REPO_ROOT, Settings, get_settings
from rag import hybrid
from rag.retrieval import Citation, RetrievedPassage


def _route(**kw) -> RouteDecision:
    base = dict(language="fr", intent="fees", procedure_category="business_registration", next_agent="checklist", method="rules")
    return RouteDecision(**{**base, **kw})


def test_entity_terms_map_company_types_to_official_french():
    assert entity_terms("fee for a public limited company", _route(language="en")) == ["Société anonyme"]
    assert entity_terms("register an SUARL", _route(language="en")) == ["Sarl Suarl"]
    assert entity_terms("sa carte", _route()) == []  # French possessive, not "SA"
    assert entity_terms("public limited company", _route(procedure_category="passport")) == []


def test_arabizi_terms_only_for_latin_script_derja():
    r = _route(language="derja")
    assert set(arabizi_terms("9adech el khtiya fel tasjil", r)) == {"خطية", "تسجيل"}
    assert arabizi_terms("chnowa el khtiya", _route(language="fr")) == []
    assert arabizi_terms("شنوة khtiya", r) == []  # Arabic script present: no transliteration needed
    assert "خطية" in expand_query("9adech el khtiya", r)


def test_question_with_rne_code_goes_to_checklist():
    router = IntentRouter(llm=None, prompts=PromptLibrary(REPO_ROOT / "prompts"), llm_fallback=False)
    assert router.route(RouteRequest(text="À quoi correspond le code RNE M 004.03 ?")).next_agent == "checklist"


def test_retrieval_mode_setting_is_validated():
    assert Settings(_env_file=None).retrieval_mode in ("agent", "hybrid")
    with pytest.raises(ValueError):
        Settings(_env_file=None, retrieval_mode="other")


# ---------------------------------------------------------------------- real corpus
@pytest.fixture(scope="module")
def corpus() -> Corpus:
    s = get_settings()
    c = Corpus(s.raw_dir, s.processed_dir)
    if not c.blocks("rne-formalities-procedure-table") or not c.blocks("interior-passport-guide-fr"):
        pytest.skip("extracted corpus not available")
    return c


def _table_passage(corpus: Corpus, code: str) -> RetrievedPassage:
    row = next(b["text"] for b in corpus.blocks("rne-formalities-procedure-table") if f"Code procédure: {code}\n" in b["text"] + "\n")
    cit = corpus.citation("rne-formalities-procedure-table")
    return RetrievedPassage(score=0.5, text="Formalités > Table\n" + row, chunk_id=code, citation=cit)


def test_rne_rows_follow_retrieval_order(corpus):
    builder = ChecklistBuilder(corpus, llm=None, prompts=PromptLibrary(REPO_ROOT / "prompts"))
    passages = [_table_passage(corpus, "RNE M 004.36"), _table_passage(corpus, "RNE C 012")]
    res = builder.build(ComposeRequest(query="radiation", route=_route(), passages=passages))
    assert res.sections[0].items[0].startswith("Code procédure: RNE M 004.36")
    assert res.text.index("RNE M 004.36") < res.text.index("RNE C 012")


def test_generic_fee_question_avoids_modification_scenario(corpus):
    builder = ChecklistBuilder(corpus, llm=None, prompts=PromptLibrary(REPO_ROOT / "prompts"))
    passages = []
    for i in (2, 0):  # "Changement" scenario retrieved first
        sc = corpus.scenarios("interior-passport-guide-fr")[i]
        cit = corpus.citation("interior-passport-guide-fr", ["t"] + sc.path + ["s"])
        passages.append(RetrievedPassage(score=0.7, text="x", chunk_id=str(i), citation=cit))
    res = builder.build(ComposeRequest(query="timbre passeport", route=_route(procedure_category="passport"), passages=passages))
    assert "Changement" not in res.scenario


# ---------------------------------------------------------------------- fusion and cap
def _p(cid: str, doc: str) -> RetrievedPassage:
    cit = Citation(doc_id=doc, title="t", source_organization="o", url="https://x", official_reference=None,
                   publication_date=None, applicability="unverified", page_start=None, page_end=None,
                   heading_path=[], sha256="0" * 64)
    return RetrievedPassage(score=0.5, text="placeholder", chunk_id=cid, citation=cit)


def test_rrf_fusion_and_per_document_cap(monkeypatch, tmp_path):
    chunks = tmp_path / "chunks_structure.jsonl"
    chunks.write_text("", encoding="utf-8")
    s = Settings(_env_file=None, data_dir=tmp_path)
    (tmp_path / "processed").mkdir()
    (tmp_path / "processed" / "chunks_structure.jsonl").write_text("", encoding="utf-8")

    class FakeEmbedder:
        dim = 3

        def embed(self, texts):
            return [[0.0, 0.0, 1.0] for _ in texts]

    lists = {"raw": [_p("a1", "A"), _p("a2", "A"), _p("a3", "A"), _p("b1", "B")],
             "exp": [_p("a1", "A"), _p("b1", "B"), _p("a2", "A")]}
    calls = iter(["raw", "exp"])
    monkeypatch.setattr(hybrid.HybridRetriever, "_dense", lambda self, q, v, c: list(lists[next(calls)]))
    r = hybrid.HybridRetriever(s, FakeEmbedder(), store=None, components=("raw", "expanded"), max_per_doc=2)
    out = r.retrieve("q", _route(), 4)
    # RRF: a1 = 2/61, a2 = 1/62 + 1/63, b1 = 1/64 + 1/62; a3 would be 4th but the cap allows 2 chunks of A.
    assert [p.chunk_id for p in out] == ["a1", "a2", "b1"]


def test_unknown_rne_code_is_reported_not_answered(corpus):
    builder = ChecklistBuilder(corpus, llm=None, prompts=PromptLibrary(REPO_ROOT / "prompts"))
    res = builder.build(ComposeRequest(query="redevance du code RNE C 014 ?", route=_route(), passages=[]))
    assert not res.found and "RNE C 014" in res.text and not res.sections
    ok = builder.build(ComposeRequest(query="code RNE M 004.03", route=_route(), passages=[]))
    assert ok.found
