"""Language detection, intent routing (rules only) and the prompt library."""

import pytest

from agents.intent_router import IntentRouter, next_agent_for
from agents.language import detect_language
from agents.prompts import PromptLibrary, PromptSpec
from agents.retriever import expand_query
from agents.schemas import RouteRequest
from backend.settings import REPO_ROOT


@pytest.fixture(scope="module")
def prompts() -> PromptLibrary:
    return PromptLibrary(REPO_ROOT / "prompts")


@pytest.fixture(scope="module")
def router(prompts) -> IntentRouter:
    return IntentRouter(llm=None, prompts=prompts, llm_fallback=False)


@pytest.mark.parametrize("text,expected", [
    ("Quelles pièces fournir pour renouveler un passeport ?", "fr"),
    ("What documents do I need to renew my passport?", "en"),
    ("ما هي الوثائق المطلوبة لتجديد جواز السفر؟", "ar"),
    ("شنوة الأوراق اللازمة باش نجدد الباسبور؟", "derja"),
    ("chnowa lezmni bech nbaddel el karta mta3i", "derja"),
    ("9adech yekhou wa9t el passbor", "derja"),
])
def test_detect_language(text, expected):
    assert detect_language(text) == expected


@pytest.mark.parametrize("text,category,intent,next_agent", [
    ("Quelles pièces fournir pour renouveler un passeport ?", "passport", "required_documents", "checklist"),
    ("How much does a passport cost?", "passport", "fees", "checklist"),
    ("Combien de temps pour obtenir la carte d'identité nationale ?", "national_id", "processing_time", "checklist"),
    ("Où déposer le dossier de passeport ?", "passport", "submission_place", "checklist"),
    ("Combien coûte l'immatriculation d'une SARL ?", "business_registration", "fees", "checklist"),
    ("What is the penalty for late registration with the RNE?", "business_registration", "procedure_info", "answer"),
    ("استخراج مضمون ولادة", "birth_certificate", "procedure_info", "reply"),
    ("bonjour", "none", "greeting", "reply"),
])
def test_rule_routing(router, text, category, intent, next_agent):
    d = router.route(RouteRequest(text=text))
    assert (d.procedure_category, d.intent, d.next_agent) == (category, intent, next_agent)
    assert d.method == "rules"
    if next_agent == "reply":
        assert d.reply


def test_routing_hints_and_forced_language(router):
    d = router.route(RouteRequest(text="renew passport, I live abroad", language="fr"))
    assert d.language == "fr"
    assert set(d.hints) == {"abroad", "renewal"}


def test_birth_certificate_mentioned_inside_passport_question_is_not_the_procedure(router):
    d = router.route(RouteRequest(text="passeport pour mineur avec extrait de naissance"))
    assert d.procedure_category == "passport"


def test_unknown_without_llm_falls_back_to_general_answer(router):
    d = router.route(RouteRequest(text="Quels sont les textes applicables ?"))
    assert d.procedure_category == "general" and d.next_agent == "answer" and d.method == "default"


def test_next_agent_mapping():
    assert next_agent_for("passport", "eligibility") == "checklist"
    assert next_agent_for("general", "procedure_info") == "answer"
    assert next_agent_for("none", "out_of_scope") == "reply"


class _FakeLLM:
    def __init__(self, text):
        self.text = text

    def run(self, spec, **values):
        from agents.llm import LLMResult
        return LLMResult(text=self.text, model="fake", prompt_ref=spec.ref, seconds=0, eval_tokens=0)


def test_llm_fallback_output_is_validated(prompts):
    bad = IntentRouter(llm=_FakeLLM('{"procedure_category": "mars", "intent": "dance"}'), prompts=prompts)
    d = bad.route(RouteRequest(text="xyzzy plugh"))
    assert d.procedure_category == "general" and d.intent == "procedure_info" and d.method == "llm"
    broken = IntentRouter(llm=_FakeLLM("not json"), prompts=prompts)
    d = broken.route(RouteRequest(text="xyzzy plugh"))
    assert d.procedure_category == "general" and d.method == "default"


def test_query_expansion_adds_bilingual_terms(router):
    d = router.route(RouteRequest(text="passport documents abroad"))
    q = expand_query("passport documents abroad", d)
    assert "جواز السفر" in q and "pièces à fournir" in q and "l'étranger" in q


def test_prompt_library_active_versions_load(prompts):
    for name, version in prompts.active.items():
        spec = prompts.get(name)
        assert spec.version == version and spec.user_template
    assert {"v1", "v2"} <= set(prompts.list_versions()["grounded_answer"]["versions"])


def test_prompt_render_keeps_literal_braces():
    spec = PromptSpec(name="x", version="v1", system='{"a": 1} {lang}', user_template="{q}")
    system, user = spec.render(lang="French", q="hello")
    assert system == '{"a": 1} French' and user == "hello"


def test_prompt_version_mismatch_is_rejected(tmp_path):
    (tmp_path / "p").mkdir()
    (tmp_path / "registry.yaml").write_text("active:\n  p: v2\n", encoding="utf-8")
    (tmp_path / "p" / "v2.yaml").write_text("name: p\nversion: v1\nuser_template: x\n", encoding="utf-8")
    with pytest.raises(ValueError):
        PromptLibrary(tmp_path).get("p")


def test_every_prompt_version_parses(prompts):
    for name, info in prompts.list_versions().items():
        for version in info["versions"]:
            assert prompts.get(name, version).ref == f"{name}@{version}"


# Known uncovered procedures (vehicle registration "carte grise", driving licence) must be refused by rule.
# Before this rule they reached the LLM fallback, which routed "carte grise" to a generated answer built
# from the national-ID guide (multilingual evaluation 2026-10-18, case OOS-fr; held-out H17).
@pytest.mark.parametrize("text", [
    "Comment renouveler une carte grise ?",
    "Comment obtenir un permis de conduire ?",
    "How do I renew a vehicle registration card?",
    "How do I get a driving licence?",
    "كيفاش نجدد البطاقة الرمادية؟",
    "ما هي وثائق رخصة السياقة؟",
])
@pytest.mark.parametrize("context", [None, {}])
def test_known_uncovered_procedures_are_refused_by_rule(router, text, context):
    d = router.route(RouteRequest(text=text, context=context))
    assert (d.procedure_category, d.intent, d.next_agent, d.method) == ("none", "out_of_scope", "reply", "rules")
    assert d.reply


@pytest.mark.parametrize("text,category", [
    ("Comment renouveler la carte d'identité nationale ?", "national_id"),
    ("Quelles pièces pour renouveler un passeport ?", "passport"),
    ("Faut-il un permis pour immatriculer une SARL au RNE ?", "business_registration"),
])
def test_uncovered_rule_does_not_capture_covered_procedures(router, text, category):
    assert router.route(RouteRequest(text=text)).procedure_category == category
