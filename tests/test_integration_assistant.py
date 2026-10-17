"""End-to-end tests through n8n (workflow 03) against the running stack and host Ollama.

Run: pytest -m integration   (skipped when n8n / the assistant webhook is not reachable)
"""

import base64
import glob
import json

import fitz
import httpx
import pytest

from backend.settings import REPO_ROOT
from telegram_bridge.bridge import TelegramBridge

pytestmark = pytest.mark.integration

WEBHOOK = "http://localhost:5678/webhook/assistant"


@pytest.fixture(scope="module")
def ask():
    try:
        httpx.post(WEBHOOK, json={"text": "bonjour"}, timeout=30).raise_for_status()
    except httpx.HTTPError:
        pytest.skip("n8n assistant webhook not reachable (import and publish workflow 03)")

    def _ask(payload: dict) -> dict:
        r = httpx.post(WEBHOOK, json=payload, timeout=900)
        r.raise_for_status()
        return r.json()

    return _ask


def test_primary_scenario_checklist_fr(ask):
    d = ask({"text": "Quelles pièces fournir pour renouveler un passeport ?"})
    assert d["agent"] == "checklist_builder" and d["found"]
    assert d["route"]["procedure_category"] == "passport" and d["route"]["intent"] == "required_documents"
    assert "Pièces à fournir" in d["text"] and "services.interieur.gov.tn" in d["text"]
    assert d["warnings"]  # FR and AR official versions state different stamp duty amounts


def test_derja_question_gets_arabic_official_text(ask):
    d = ask({"text": "شنوة الأوراق اللازمة باش نجدد الباسبور؟"})
    assert d["route"]["language"] == "derja" and d["doc_id"] == "interior-passport-guide-ar"


def test_english_question_gets_validated_translation(ask):
    d = ask({"text": "What documents do I need to renew my passport? I live abroad"})
    assert d["route"]["language"] == "en" and "abroad" in d["route"]["hints"]
    assert d["translation"] is None or d["translation"]["validated"] in (True, False)
    assert "Official sources" in d["text"]


def test_rne_fee_question_quotes_official_table(ask):
    d = ask({"text": "Combien coûte l'immatriculation d'une SARL au RNE ?"})
    assert d["agent"] == "checklist_builder" and "RNE C 012" in d["text"] and "50 TND" in d["text"]


def test_free_question_goes_to_grounded_answer_with_citations(ask):
    d = ask({"text": "What is the penalty for late registration with the RNE?"})
    assert d["agent"] == "grounded_answer" and d["citations"]
    assert d["method"] in ("llm_grounded", "passages_fallback")


def test_out_of_scope_and_uncovered_procedures(ask):
    assert ask({"text": "quelle est la météo demain"})["route"]["intent"] == "out_of_scope"
    d = ask({"text": "comment obtenir un extrait de naissance ?"})
    assert d["route"]["procedure_category"] == "birth_certificate" and "pas encore couverte" in d["text"]


def test_form_upload_pdf_and_scanned_image(ask):
    path = glob.glob(str(REPO_ROOT / "data" / "raw" / "rne-form-f002-legal-entity-registration" / "*.pdf"))[0]
    pdf = open(path, "rb").read()
    d = ask({"file": {"filename": "f.pdf", "mime_type": "application/pdf", "data_b64": base64.b64encode(pdf).decode()}})
    assert d["agent"] == "form_helper" and d["form_doc_id"] == "rne-form-f002-legal-entity-registration"
    assert len(d["missing"]) == 8
    png = fitz.open(path)[0].get_pixmap(dpi=200).tobytes("png")
    d = ask({"file": {"filename": "p.png", "mime_type": "image/png", "data_b64": base64.b64encode(png).decode()},
             "language": "en"})
    assert d["form_doc_id"] == "rne-form-f002-legal-entity-registration" and len(d["missing"]) == 8


def test_telegram_bridge_through_real_n8n(ask):
    """Telegram API mocked; the webhook call goes to the real n8n -> agents -> backend chain."""
    sent: list[dict] = []
    real = httpx.Client(timeout=900)

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == WEBHOOK:
            r = real.post(url, content=request.content, headers={"content-type": "application/json"})
            return httpx.Response(r.status_code, content=r.content, headers={"content-type": "application/json"})
        if url.endswith("/sendMessage"):
            sent.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True, "result": {}})

    bridge = TelegramBridge("123:TEST", WEBHOOK, 10 * 1024 * 1024, client=httpx.Client(transport=httpx.MockTransport(handler)))
    bridge.handle_message({"chat": {"id": 5}, "from": {"language_code": "fr"},
                           "text": "Quelles pièces fournir pour renouveler un passeport ?"})
    text = "\n".join(m["text"] for m in sent)
    assert "Pièces à fournir" in text and all(len(m["text"]) <= 4096 for m in sent)


# ---------------------------------------------------------------------- dossier branch (mode = "dossier")
F001_DIR = REPO_ROOT / "data" / "raw" / "rne-form-f001-natural-person-registration"
F002_DIR = REPO_ROOT / "data" / "raw" / "rne-form-f002-legal-entity-registration"


def _upload(path_or_bytes, mime="application/pdf", name="form.pdf") -> dict:
    data = path_or_bytes if isinstance(path_or_bytes, bytes) else open(path_or_bytes, "rb").read()
    return {"filename": name, "mime_type": mime, "data_b64": base64.b64encode(data).decode()}


def test_upload_without_mode_keeps_the_form_check_path(ask):
    d = ask({"file": _upload(glob.glob(str(F002_DIR / "*.pdf"))[0]), "language": "fr"})
    assert d["agent"] == "form_helper" and d["form_doc_id"] == "rne-form-f002-legal-entity-registration"
    # Exact response contract of the pre-existing "Respond: form check" node (deploy/n8n_rollback/).
    assert set(d) == {"text", "agent", "recognised", "form_doc_id", "missing", "error", "form_url", "language"}
    assert len(d["missing"]) == 8 and d["language"] == "fr"


def test_dossier_mode_returns_structured_readiness_report(ask):
    d = ask({"file": _upload(glob.glob(str(F002_DIR / "*.pdf"))[0]), "language": "en", "mode": "dossier"})
    assert d["agent"] == "dossier_validator" and d["recognised"] and d["form_doc_id"] == "rne-form-f002-legal-entity-registration"
    assert d["form_url"].startswith("https://home.registre-entreprises.tn/")
    assert len(d["report"]["form_fields"]["missing"]) == 8 and d["missing"] == d["report"]["form_fields"]["missing"]
    dossier = d["report"]["dossier"]
    assert dossier["official_checklist_available"] is False and dossier["completeness_certified"] is False
    assert {q["status"] for q in dossier["official_requirements"]} >= {"supported_by_official_source", "official_requirement_unavailable"}
    assert "This report is not an official validation." in d["report"]["readiness_summary"]
    assert any(c["doc_id"] == "rne-formalities-procedure-table" for c in d["citations"])
    assert "approved" not in d["text"].lower() and "certified" not in d["text"].lower()


def test_dossier_mode_on_a_scan_like_image_in_arabic(ask):
    png = fitz.open(glob.glob(str(F001_DIR / "*.pdf"))[0])[0].get_pixmap(dpi=200).tobytes("png")
    d = ask({"file": _upload(png, "image/png", "scan.png"), "language": "ar", "mode": "dossier"})
    assert d["recognised"] and d["form_doc_id"] == "rne-form-f001-natural-person-registration"
    assert len(d["missing"]) == 7 and "لا يمكن تقييم اكتمال الملف" in d["report"]["readiness_summary"]


def test_dossier_mode_rejects_unrelated_documents(ask):
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), "Neutral placeholder document", fontsize=12)
    d = ask({"file": _upload(doc.tobytes()), "mode": "dossier"})
    assert d["agent"] == "dossier_validator" and d["recognised"] is False and not d["missing"]


def test_dossier_response_fits_the_bridge_contract(ask):
    from telegram_bridge.contracts import AssistantResponse  # read-only use of the bridge contract

    d = ask({"file": _upload(glob.glob(str(F001_DIR / "*.pdf"))[0]), "mode": "dossier", "language": "fr"})
    parsed = AssistantResponse.model_validate(d)
    assert parsed.text and parsed.agent == "dossier_validator" and parsed.recognised is True


def test_text_questions_unaffected_by_dossier_mode_field(ask):
    d = ask({"text": "Combien coûte l'immatriculation d'une SARL ?", "mode": "dossier"})
    assert d["agent"] == "checklist_builder" and "RNE C 012" in d["text"]
