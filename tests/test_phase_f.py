"""Phase F: defects found in the real Telegram acceptance session (fixture: phase_e_telegram_session.json).

Official facts are read from the indexed corpus (RNE table, forms, CIN guide, manifest); nothing is invented here.
"""
import base64
import json
import logging
import re
from pathlib import Path

import fitz
import pytest

from agents.answer import GroundedAnswerer
from agents.checklist_builder import AMOUNT, ChecklistBuilder
from agents.conversation import REPLIES
from agents.corpus import Corpus
from agents.i18n import t
from agents.intent_router import IntentRouter
from agents.legal_evidence import CLARIFY
from agents.prompts import PromptLibrary
from agents.rne_registration import QUESTION, codes_for, detect_legal_form
from agents.schemas import ComposeRequest, DialogueContext, FormCheckRequest, RouteRequest
from backend.settings import REPO_ROOT, get_settings
from rag.retrieval import RetrievedPassage

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "phase_e_telegram_session.json").read_text(encoding="utf-8"))
TURNS = {t_["id"]: t_ for t_ in FIXTURE["turns"]}
CIN = "interior-national-id-guide-fr"
TABLE = "rne-formalities-procedure-table"
F001, F002 = "rne-form-f001-natural-person-registration", "rne-form-f002-legal-entity-registration"


@pytest.fixture(scope="module")
def corpus():
    s = get_settings()
    c = Corpus(s.raw_dir, s.processed_dir)
    if not c.scenarios(CIN) or not c.blocks(TABLE) or not c.blocks(F001):
        pytest.skip("Official extraction unavailable")
    return c


@pytest.fixture
def router():
    return IntentRouter(None, PromptLibrary(REPO_ROOT / "prompts"), False)


@pytest.fixture(scope="module")
def builder(corpus):
    return ChecklistBuilder(corpus, None, PromptLibrary(REPO_ROOT / "prompts"))


@pytest.fixture(scope="module")
def answerer(corpus):
    return GroundedAnswerer(None, PromptLibrary(REPO_ROOT / "prompts"), None, None, corpus)


def chain(router, messages, ctx=None):
    ctx, out = ctx or DialogueContext(), []
    for text in messages:
        d = router.route(RouteRequest(text=text, context=ctx))
        ctx = d.context if d.context is not None else ctx.model_copy(update={"language": d.language})
        out.append((d, ctx))
    return out


def table_rows(corpus):
    return {re.sub(r"\s+", "", b["text"].splitlines()[0].split(":", 1)[-1]): b["text"]
            for b in corpus.blocks(TABLE) if b["kind"] == "table_row"}


def compose(route, query, passages=()):
    return ComposeRequest(query=route.retrieval_query or query, route=route, passages=list(passages))


# ---------------------------------------------------------------- D1: deadline questions (all languages)
CIN_FIRST = DialogueContext(category="national_id", hints=["first_time"], language="fr")


@pytest.mark.parametrize("text,lang", [
    ("قداش تاخو وقت؟", "derja"),                       # observed in production (fixture D1)
    ("قداش ياخو وقت باش تخرج الكارطة؟", "derja"), ("قداش من وقت تاخو؟", "derja"),
    ("9adech takhou wa9t?", "derja"), ("9adech ta5ou wa9t?", "derja"), ("kadech yekhou wa9t", "derja"),
    ("كم من الوقت يستغرق ذلك؟", "ar"), ("كم يستغرق إصدار البطاقة؟", "ar"), ("ما هي آجال إصدار البطاقة؟", "ar"),
    ("Combien de temps faut-il ?", "fr"), ("Quel est le délai ?", "fr"), ("En combien de jours ?", "fr"),
    ("How long does it take?", "en"), ("How many weeks does it take?", "en"),
])
def test_d1_deadline_questions_route_to_processing_time(router, text, lang):
    (d, ctx), = chain(router, [text], CIN_FIRST)
    assert d.intent == "processing_time" and d.procedure_category == "national_id" and d.language == lang
    assert ctx.hints == ["first_time"]  # CIN context kept


@pytest.mark.parametrize("text", ["قداش نخلص؟", "Combien ça coûte ?", "How much does it cost?", "9adech nkhalles?"])
def test_d1_fee_questions_stay_fees(router, text):
    (d, _), = chain(router, [text], CIN_FIRST)
    assert d.intent == "fees"


def test_d1_observed_session_shows_official_delay_section_in_derja(router, builder, corpus):
    (d, _), = chain(router, [TURNS["D1"]["observed_input"]], CIN_FIRST)
    sc = corpus.scenarios(CIN)[0]
    r = builder.build(compose(d, d.retrieval_query, [RetrievedPassage(score=.7, text="n", chunk_id="n",
                                                                       citation=corpus.citation(CIN, sc.path))]))
    assert r.found and [s.kind for s in r.sections] == ["delay"]
    official = {i.strip() for s in sc.sections if s.kind == "delay" for i in s.items}
    assert all(i.strip() in official for i in r.sections[0].items)
    assert t("delay", "derja") in r.text and t("fees", "derja") not in r.text


# ---------------------------------------------------------------- D2: legal form before any registration procedure
@pytest.mark.parametrize("text,lang", [
    ("Je veux immatriculer une entreprise en Tunisie", "fr"),   # observed (fixture D2)
    ("Je veux créer une société", "fr"), ("I want to register a company in Tunisia", "en"),
    ("نحب نعمل شركة", "derja"), ("nheb na3mel chirka", "derja"),
])
def test_d2_ambiguous_business_registration_asks_legal_form(router, text, lang):
    (d, ctx), = chain(router, [text])
    assert d.procedure_category == "business_registration" and d.next_agent == "reply"
    assert d.reply == QUESTION[lang] and d.retrieval_query is None   # no procedure chosen from retrieval
    assert ctx.rne_code is None


@pytest.mark.parametrize("text,key", [
    ("Je veux immatriculer une personne physique au RNE", "natural_person"),
    ("Comment immatriculer une SARL au RNE ?", "sarl_family"),
    ("Je veux créer une SUARL", "sarl_family"),
    ("Je veux créer une SA", "sa"),
    ("Comment immatriculer une association ?", "association"),
    ("Je veux immatriculer une association étrangère", "foreign_association"),
    ("Je suis commerçant, comment m'immatriculer ?", "trader"),
    ("Comment enregistrer une coopérative ?", "cooperative"),
])
def test_d2_legal_form_selects_its_official_rows(router, builder, corpus, text, key):
    assert detect_legal_form(text) == key
    (d, _), = chain(router, [text])
    assert d.procedure_category == "business_registration" and d.next_agent == "checklist"
    rows = table_rows(corpus)
    r = builder.build(compose(d, text))
    expected = [rows[c.replace(" ", "")] for c in codes_for(key)]
    shown = r.sections[-1].items
    assert shown == expected                      # exactly the official creation rows of this legal form
    assert all("Procédure: Création" in row for row in shown)
    assert {m.group(1) for m in AMOUNT.finditer(r.text)} <= {m.group(1) for row in rows.values() for m in AMOUNT.finditer(row)}


def test_d2_french_possessive_sa_is_not_a_legal_form():
    assert detect_legal_form("Je veux immatriculer sa société") is None


def test_d2_answering_the_clarification_and_switching_from_cin(router):
    turns = chain(router, ["Ma carte d'identité est abîmée, quelles pièces ?", "Je veux immatriculer une entreprise en Tunisie", "SARL"])
    (_, cin), (q, _), (d, ctx) = turns
    assert "loss" in cin.hints and q.reply == QUESTION["fr"]
    assert d.next_agent == "checklist" and ctx.rne_code == "RNE C 012" and "loss" not in ctx.hints


# ---------------------------------------------------------------- D3: F-001 / F-002 conversational handling
@pytest.mark.parametrize("messages,form", [
    (["Que contient le formulaire F-001 ?"], F001),                                   # observed (D3a)
    (["Que contient le formulaire F-001 ?", "Et le formulaire F-002 ?"], F002),       # observed follow-up (D3b)
    (["Que contient le formulaire F-001 ?", "Et le F-002 ?"], F002),
    (["Je veux immatriculer une entreprise en Tunisie", "Et le formulaire F-002 ?"], F002),
])
def test_d3_form_content_and_follow_up(router, answerer, corpus, messages, form):
    *_, (d, _) = chain(router, messages)
    assert d.next_agent == "answer" and d.procedure_category == "business_registration"
    r = answerer.answer(ComposeRequest(query=messages[-1], route=d, passages=[]))
    assert r.found and r.citations and r.citations[0].doc_id == form
    labels = [re.match(r"^(.*?)\s*:\s*[.\s/]{4,}", b["text"]).group(1).strip()
              for b in corpus.blocks(form) if "...." in b["text"] and re.match(r"^(.*?)\s*:\s*[.\s/]{4,}", b["text"])]
    assert labels and all(label in r.text for label in labels)        # printed field labels, verbatim
    assert t("form_overview", "fr") in r.text and CLARIFY["fr"] not in r.text


def test_d3_specific_unindexed_question_states_the_limitation(router, answerer):
    (d, _), = chain(router, ["Que dit le formulaire F-002 sur le capital social ?"])
    r = answerer.answer(ComposeRequest(query="Que dit le formulaire F-002 sur le capital social ?", route=d, passages=[]))
    assert t("form_section_unavailable", "fr") in r.text and "capital" not in r.text.split(t("form_overview", "fr"))[-1].lower()


def test_d3_specific_indexed_question_still_quotes_the_passage(router, answerer):
    q = "Que dit le formulaire F-001 sur les pièces à joindre ?"
    (d, _), = chain(router, [q])
    r = answerer.answer(ComposeRequest(query=q, route=d, passages=[]))
    assert r.found and "Extraits officiels" in r.text and t("form_section_unavailable", "fr") not in r.text


# ---------------------------------------------------------------- D4: fees only for an identified legal form
def test_d4_fees_without_legal_form_ask_for_it(router):
    turns = chain(router, ["Je veux immatriculer une entreprise en Tunisie", "Quels sont les frais ?"])   # observed (D4)
    d = turns[-1][0]
    assert d.next_agent == "reply" and d.reply == QUESTION["fr"]


def test_d4_fees_after_legal_form_quote_the_official_row(router, builder, corpus):
    *_, (d, ctx) = chain(router, ["Je veux immatriculer une entreprise en Tunisie", "SARL", "Quels sont les frais ?"])
    assert d.next_agent == "checklist" and ctx.rne_code == "RNE C 012"
    r = builder.build(compose(d, "Quels sont les frais ?"))
    row = table_rows(corpus)["RNEC012"]
    assert r.sections[-1].items == [row] and "Redevance demandée: cinquante dinars (50 TND)" in r.text
    assert F002 in {c.doc_id for c in r.citations} and F001 not in {c.doc_id for c in r.citations}  # legal entity form


def test_d4_yes_reasks_the_legal_form(router):
    *_, (d, _) = chain(router, ["Quels sont les frais d'immatriculation au RNE ?", "oui"])
    assert d.reply.startswith(REPLIES["reask"]["fr"]) and QUESTION["fr"] in d.reply


def test_d4_article_question_after_a_code_still_asks_for_the_act(router):
    *_, (d, _) = chain(router, ["Comment immatriculer une SARL ?", "Que dit l'article 5 ?"])
    assert d.reply == CLARIFY["fr"]


# ---------------------------------------------------------------- D5: form download
def test_d5_passport_form_download_gives_the_verified_official_link(router, answerer, corpus):
    # Phase G stored the official file (manual import), so the link is now verified.
    q = TURNS["D5"]["observed_input"]
    (d, ctx), = chain(router, [q], DialogueContext(category="passport", hints=["renewal"], residence="tunisia", language="fr"))
    assert d.next_agent == "answer" and d.procedure_category == "passport" and ctx.hints == ["renewal"]
    r = answerer.answer(ComposeRequest(query=q, route=d, passages=[]))
    record = corpus.records()["interior-passport-application-form"]
    assert record.file_path and record.url in r.text and r.found
    assert [c.doc_id for c in r.citations] == [record.doc_id] and t("form_download_unavailable", "fr") not in r.text


@pytest.mark.parametrize("q,form", [("Où télécharger le formulaire F-001 ?", F001),
                                    ("Where can I download form F-002?", F002)])
def test_d5_verified_rne_form_download_link(router, answerer, corpus, q, form):
    (d, _), = chain(router, [q])
    r = answerer.answer(ComposeRequest(query=q, route=d, passages=[]))
    assert r.found and corpus.records()[form].url in r.text and r.citations[0].doc_id == form


def test_d5_cin_form_download_gives_the_verified_official_link(router, answerer, corpus):
    q = "Où télécharger le formulaire de la carte d'identité ?"
    (d, _), = chain(router, [q])
    r = answerer.answer(ComposeRequest(query=q, route=d, passages=[]))
    record = corpus.records()["interior-national-id-application-form"]
    assert r.found and record.url in r.text and [c.doc_id for c in r.citations] == [record.doc_id]


# ---------------------------------------------------------------- D6: unrecognised PDFs
def test_d6_unrecognised_pdf_names_supported_forms_and_logs_metadata_only(corpus, caplog):
    from agents.form_helper import FormHelper
    doc = fitz.open()
    doc.new_page().insert_text((72, 100), "Neutral test document. " * 20, fontsize=10)
    data = doc.tobytes()
    s = get_settings()
    with caplog.at_level(logging.INFO):
        r = FormHelper(corpus, s.max_upload_bytes).check(FormCheckRequest(mime_type="application/pdf", language="fr",
                                                                          data_b64=base64.b64encode(data).decode()))
    assert r.recognised is False and "RNE F-001" in r.text and "RNE F-002" in r.text
    events = [rec for rec in caplog.records if rec.getMessage() == "form_unrecognised"]
    assert events and set(events[0].fields) == {"closest_template", "closest_overall", "threshold", "method"}
    assert "Neutral" not in json.dumps(events[0].fields)                # no file content in logs


def test_d6_official_blank_forms_are_still_recognised(corpus):
    import glob
    from agents.form_helper import FormHelper
    s = get_settings()
    helper = FormHelper(corpus, s.max_upload_bytes)
    for form in (F001, F002):
        data = open(glob.glob(str(REPO_ROOT / "data" / "raw" / form / "*.pdf"))[0], "rb").read()
        r = helper.check(FormCheckRequest(mime_type="application/pdf", language="fr", data_b64=base64.b64encode(data).decode()))
        assert r.recognised and r.form_doc_id == form
