"""Retrieval metrics, relevance judgement, BM25 tokenisation and evaluation-set integrity."""

import json

import pytest

from backend.settings import REPO_ROOT
from rag.evaluation import Alternative, aggregate, group_hit_ranks, norm, question_metrics
from rag.hybrid import BM25, tokenize

EVAL_SET = REPO_ROOT / "data" / "evaluation" / "eval_set.jsonl"


def test_norm_ignores_spacing_case_and_diacritics():
    assert norm("Placeholder  Text") == norm("placeholdertext")
    assert norm("تُساوي") == norm("تساوي")
    assert norm("l’article") == norm("l'article")


def test_relevance_requires_document_and_evidence():
    alt = Alternative("doc-a", "needle phrase")
    assert alt.matches("doc-a", "some text with the Needle  Phrase inside")
    assert not alt.matches("doc-b", "some text with the needle phrase inside")
    assert not alt.matches("doc-a", "unrelated")
    assert Alternative("doc-a", None).matches("doc-a", "anything")


def test_metrics_for_two_groups():
    groups = [[Alternative("a", "x1")], [Alternative("b", "y1"), Alternative("c", "y2")]]
    retrieved = [("z", "..."), ("c", "has y2"), ("a", "has x1")]
    ranks = group_hit_ranks(groups, retrieved)
    assert ranks == [3, 2]
    m = question_metrics(ranks)
    assert m["recall@1"] == 0 and m["recall@3"] == 1 and m["hit@5"] == 1 and m["mrr@5"] == 0.5
    assert question_metrics([None])["mrr@5"] == 0 and question_metrics([None])["hit@5"] == 0
    assert question_metrics([None, 1])["recall@5"] == 0.5


def test_aggregate_reports_latency():
    rows = [{**question_metrics([1]), "latency_ms": 10}, {**question_metrics([None]), "latency_ms": 30}]
    a = aggregate(rows)
    assert a["n"] == 2 and a["hit@5"] == 0.5 and a["latency_ms_median"] == 20


def test_tokenize_keeps_procedure_codes():
    assert "004.03" in tokenize("Code RNE M 004.03")
    assert "suarl" in tokenize("frais SUARL ?")


def test_bm25_prefers_exact_rare_token():
    docs = [tokenize("placeholder code 004.03 alpha"), tokenize("placeholder code 004.04 alpha"), tokenize("other text")]
    ranked = BM25(docs).scores(tokenize("004.03"), [0, 1, 2])
    assert ranked[0][0] == 0 and len(ranked) == 1


def test_eval_set_integrity():
    if not EVAL_SET.exists():
        pytest.skip("evaluation set not built")
    rows = [json.loads(line) for line in EVAL_SET.read_text(encoding="utf-8").splitlines() if line]
    assert len(rows) >= 40 and len({r["id"] for r in rows}) == len(rows)
    for r in rows:
        assert r["verification_status"] != "UNVERIFIED", r["id"]
        for g in r["evidence_groups"]:
            for a in g:
                assert a["source_url"] and a["source_url"].startswith("http")
                if a["evidence"]:
                    assert norm(a["evidence"]) in norm(a["reference_extract"])
        if r["answerability"] in ("unsupported", "out_of_scope"):
            assert not r["evidence_groups"]
    assert {r["language"] for r in rows} == {"en", "fr", "ar", "derja"}
