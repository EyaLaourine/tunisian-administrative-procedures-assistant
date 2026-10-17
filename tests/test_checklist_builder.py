"""Checklist Builder: scenario parsing (fixtures) and behaviour on the real extracted official corpus."""

import pytest

from agents.checklist_builder import ChecklistBuilder, _parse_numbered, _same_numbers
from agents.corpus import Corpus, parse_scenarios, section_kind
from agents.prompts import PromptLibrary
from agents.schemas import ComposeRequest, RouteDecision
from backend.settings import REPO_ROOT, get_settings
from rag.retrieval import Citation, RetrievedPassage

# Neutral placeholder content: section headings use the official heading words, items do not
# describe any procedure.
FIXTURE_BLOCKS = [
    {"kind": "heading", "level": 1, "text": "Placeholder title", "page": None},
    {"kind": "heading", "level": 3, "text": "Group A", "page": None},
    {"kind": "heading", "level": 4, "text": "Case A1", "page": None},
    {"kind": "heading", "level": 6, "text": "Conditions d'obtentions", "page": None},
    {"kind": "list_item", "level": 0, "text": "placeholder condition", "page": None},
    {"kind": "heading", "level": 6, "text": "Pièces à fournir", "page": None},
    {"kind": "list_item", "level": 0, "text": "placeholder item 1", "page": None},
    {"kind": "list_item", "level": 0, "text": "placeholder item 2", "page": None},
    {"kind": "heading", "level": 4, "text": "Case A2 (من أجل placeholder)", "page": None},
    {"kind": "heading", "level": 6, "text": "Délais", "page": None},
    {"kind": "list_item", "level": 0, "text": "placeholder delay", "page": None},
]


def test_parse_scenarios_fixture():
    scenarios = parse_scenarios(FIXTURE_BLOCKS)
    assert [s.title for s in scenarios] == ["Case A1", "Case A2 (من أجل placeholder)"]
    assert [(x.kind, x.items) for x in scenarios[0].sections] == [
        ("conditions", ["placeholder condition"]), ("documents", ["placeholder item 1", "placeholder item 2"])]
    assert scenarios[1].sections[0].kind == "delay"


def test_section_heading_detection_is_anchored():
    assert section_kind("أجل الحصول على الخدمة") == "delay"
    assert section_kind("استخراج نظير من جواز سفر (من أجل السرقة)") is None
    assert section_kind("Pièces à fournir") == "documents"


def test_translation_validation_helpers():
    assert _parse_numbered("1. a\n2. b", 2) == ["a", "b"]
    assert _parse_numbered("1. a\n3. b", 2) is None
    assert _same_numbers("De 20 dinars, format 3.5/4.5 cm", "20 dinars, size 3.5/4.5 cm")
    assert not _same_numbers("De 20 dinars", "25 dinars")


# ---------------------------------------------------------------------- real corpus
@pytest.fixture(scope="module")
def corpus() -> Corpus:
    s = get_settings()
    c = Corpus(s.raw_dir, s.processed_dir)
    if not c.blocks("interior-passport-guide-fr") or not c.blocks("interior-passport-guide-ar"):
        pytest.skip("extracted corpus not available (run POST /index/run)")
    return c


@pytest.fixture(scope="module")
def builder(corpus) -> ChecklistBuilder:
    return ChecklistBuilder(corpus, llm=None, prompts=PromptLibrary(REPO_ROOT / "prompts"))


def _passage(corpus: Corpus, doc_id: str, scenario_index: int) -> RetrievedPassage:
    sc = corpus.scenarios(doc_id)[scenario_index]
    cit: Citation = corpus.citation(doc_id, ["title"] + sc.path + ["section"])
    return RetrievedPassage(score=0.7, text="(retrieved chunk)", chunk_id=f"{doc_id}:{scenario_index}", citation=cit)


def _route(lang="fr", intent="required_documents", hints=(), category="passport") -> RouteDecision:
    return RouteDecision(language=lang, intent=intent, procedure_category=category, hints=list(hints),
                         next_agent="checklist", method="rules")


def test_fr_and_ar_passport_guides_are_structurally_aligned(corpus):
    fr = corpus.scenarios("interior-passport-guide-fr")
    ar = corpus.scenarios("interior-passport-guide-ar")
    assert len(fr) == len(ar) == 7
    assert [[s.kind for s in x.sections] for x in fr] == [[s.kind for s in x.sections] for x in ar]


def test_checklist_items_are_verbatim_official_text(corpus, builder):
    passages = [_passage(corpus, "interior-passport-guide-fr", 0)]
    res = builder.build(ComposeRequest(query="pièces passeport", route=_route(), passages=passages))
    official = corpus.scenarios("interior-passport-guide-fr")[0]
    docs = next(s for s in official.sections if s.kind == "documents")
    assert res.found and res.sections[0].kind == "documents"
    assert res.sections[0].items == docs.items
    assert res.citations[0].doc_id == "interior-passport-guide-fr"
    assert all(c.url.startswith("http") and c.applicability == "unverified" for c in res.citations)


def test_derja_user_gets_parallel_arabic_official_version(corpus, builder):
    passages = [_passage(corpus, "interior-passport-guide-fr", 0)]
    res = builder.build(ComposeRequest(query="باسبور", route=_route(lang="derja"), passages=passages))
    assert res.doc_id == "interior-passport-guide-ar" and res.source_language == "ar"
    assert res.translation is None  # no machine translation towards Arabic


def test_fee_discrepancy_between_official_versions_is_flagged(corpus, builder):
    passages = [_passage(corpus, "interior-passport-guide-fr", 0)]
    res = builder.build(ComposeRequest(query="passeport", route=_route(intent="fees"), passages=passages))
    assert res.sections[0].kind == "fees"
    assert res.warnings and "20/60" in res.warnings[0] and "25/80" in res.warnings[0]


def test_abroad_hint_selects_the_abroad_scenario(corpus, builder):
    passages = [_passage(corpus, "interior-passport-guide-fr", i) for i in (0, 1)]
    res = builder.build(ComposeRequest(query="passport abroad", route=_route(hints=["abroad"]), passages=passages))
    assert "étranger" in res.scenario
    res = builder.build(ComposeRequest(query="passport", route=_route(), passages=passages[::-1]))
    assert "territoire" in res.scenario


def test_no_passages_means_not_found(builder):
    res = builder.build(ComposeRequest(query="passeport", route=_route(), passages=[]))
    assert not res.found and not res.sections


def test_business_registration_states_missing_checklist_and_quotes_table(corpus, builder):
    if not corpus.blocks("rne-formalities-procedure-table"):
        pytest.skip("RNE table not extracted")
    route = _route(intent="required_documents", category="business_registration")
    res = builder.build(ComposeRequest(query="créer une SARL", route=route, passages=[]))
    assert "ne contiennent pas de liste" in res.text
    assert any("RNE C 012" in row for row in res.sections[0].items)
    table_rows = [b["text"] for b in corpus.blocks("rne-formalities-procedure-table") if b["kind"] == "table_row"]
    assert all(row in table_rows for row in res.sections[0].items)
