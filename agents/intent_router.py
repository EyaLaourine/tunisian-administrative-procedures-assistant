"""Intent Router agent: language, procedure category, intent and the next agent to call.

Deterministic keyword rules run first. The LLM (versioned prompt `intent_router`) is consulted only
when the rules cannot identify a procedure, and its output is validated against fixed enums.
"""

import json
import logging
import re
import unicodedata

from agents import i18n
from agents.language import detect_language
from agents.llm import LLMError, OllamaChatClient
from agents.prompts import PromptLibrary
from agents.schemas import RouteDecision, RouteRequest

log = logging.getLogger(__name__)

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "passport": ["passeport", "passport", "passbor", "basbor", "paspor", "باسبور", "الباسبور", "جواز",
                 "pèlerinage", "pelerinage", "pélerinage", "pilgrimage", "hajj", "الحج"],
    "national_id": [
        "carte d'identité", "carte d identite", "carte d'identite", "carte identité", r"\bcin\b",
        "identity card", "national id", r"\bid card", "بطاقة التعريف", "بطاقة تعريف", "الكارطة",
        r"\bkarta\b", r"\blkarta\b",
    ],
    "business_registration": [
        r"\brne\b", "registre national des entreprises", "registre des entreprises", "registre de commerce",
        "entreprise", "société", "societe", r"\bsarl\b", r"\bsuarl\b", "company", "business",
        "commerçant", "commercant", "artisan", "bénéficiaire effectif", "beneficiaire effectif",
        "beneficial owner", "immatriculation", "charika", "chrika", "sharika",
        "dénomination sociale", "nom commercial", "réservation", "trade name", "company name",
        "التسمية الاجتماعية", "الاسم التجاري", "حجز الشارة", "حجز التسمية",
        "شركة", "شركه", "السجل الوطني للمؤسسات", "المستفيد الحقيقي", "مؤسسة", "تاجر", "حرفي",
    ],
    "birth_certificate": [
        "extrait de naissance", "acte de naissance", "birth certificate", "مضمون ولادة", "شهادة ميلاد",
        "madhmoun", "mathmoun",
    ],
}

INTENT_KEYWORDS: dict[str, list[str]] = {
    # Order matters: processing_time is tested before fees ("combien de temps" vs "combien").
    "processing_time": [
        "délai", "delai", "combien de temps", "durée", "duree", "how long", "processing time",
        "how many days", r"\bأجل\b(?!\s+(?:السرقة|الضياع|الإتلاف))", "آجال", "مدة", "وقتاش", "wa9tech", "waqtech", "قداش ياخو", "9adech ya5o",
    ],
    "fees": [
        "prix", "frais", "coût", "cout", "combien", "tarif", "timbre", "redevance", r"\bfees?\b",
        r"\bcost", "price", "how much", r"\bpay\b", "payer", "dinar", "قداش", "بقداش", "9adech", "qadech",
        "معلوم", "معاليم", "ثمن", r"\bكم\b", "الطابع", "نخلص", "nkhalles",
    ],
    "submission_place": [
        r"\boù\b", "where", "lieu", "déposer", "deposer", "bureau", r"\bwin\b", "وين", "أين", "مكان",
        "nhot", "نحط",
    ],
    "eligibility": ["condition", "éligible", "eligible", "who can", "شروط", "شرط", "chourout"],
    "form_help": [
        "formulaire", "imprimé", "imprime", r"\bform\b", "fill in", "fill out", "remplir",
        "مطبوعة", "استمارة", "تعمير", "n3amer", "na3mer",
    ],
    "required_documents": [
        "pièce", "piece", "document", "papier", "dossier", "fournir", "required", "need", "faut",
        "الوثائق", "وثائق", "أوراق", "الأوراق", "اوراق", "لازم", "يلزم", "wra9", "awra9", "lezem",
        "lezm", "nheb", "n7eb", "نحب", "شنوة", "chnowa", "chnia",
    ],
}

GREETING_KEYWORDS = [
    "hello", r"\bhi\b", "bonjour", "salut", "salam", "aslema", "3aslema", "bonsoir", "merci", "thanks",
    "thank you", "مرحبا", "السلام عليكم", "عسلامة", "شكرا", "يعيشك", "/start", "/help",
]

HINT_KEYWORDS: dict[str, list[str]] = {
    "abroad": [
        "étranger", "etranger", "abroad", "consulat", "consulate", "ambassade", "embassy",
        "بالخارج", "الخارج", "برّا", "برا", "barra", "kharej", "5arej",
    ],
    "loss": ["perte", "perdu", r"\bvol\b", "volé", "lost", "stolen", "theft", "damaged", "détérioration", "deterioration", "الإتلاف", "تلف", "ضياع", "ضاع", "سرقة", "تسرق", "dha3", "tsre9",
             # stems and spelling variants: détériorée, abîmée, سرقت, ضيّعت, dhaya3t
             r"\bd[ée]t[ée]rior", r"\bab[îi]m[ée]", "damage", "سرق", "ضيع", "ضيّع", r"\bdh?ay+a3"],
    "renewal": ["renouvel", "renew", "تجديد", "جدد", "nejjedd", "jadded", r"\bn?[jg]add?e?d", r"\bt[ae]?jdid"],
    "modification": ["changement", "modification", "modifier", "change", "update my", "تغيير", "بدّل", "nbaddel", r"\bbaddel", "معطيات"],
    "first_time": ["première fois", "premiere fois", "first time", "أول مرة", "لأول مرة", "awel marra"],
    "pilgrimage": ["pèlerinage", "pelerinage", "pélerinage", "pilgrimage", "hajj", "الحج", "حج", "omra", "عمرة"],
}

# Procedures for which the knowledge base holds structured official procedure guides / tables.
CHECKLIST_CATEGORIES = {"passport", "national_id"}
# Other business questions (penalties, beneficial owners, ...) go to the grounded answer agent.
BUSINESS_CHECKLIST_INTENTS = {"required_documents", "fees", "processing_time"}
TABLE_SIGNALS = [
    "immatricul", "registration", "register", "enregistr", "inscri", "création", "creation", "créer", "creer",
    "create", "radiation", "transfert", "siège", "siege", "états financiers", "etats financiers",
    "financial statement", r"\bsarl\b", r"\bsuarl\b", "société", "societe", "company", "entreprise individuelle",
    "commerçant", "commercant", "artisan", "trader", "تسجيل", "شركة", "تاجر", "حرفي", "charika", "chrika",
    "tasjil", "nsajjel", "sajjel",
]
RNE_CODE = re.compile(r"\bRNE\s*[CIM]\s*\d{3}(?:\.\d+)*", re.I)
# Requests to *certify* validity, acceptance or completeness (never possible from the sources). Questions about a
# document's scope are not included: they are answered from the official text with the non-certification notice.
# Matched on the normalised (lower-case, diacritic-free) text.
LIMITS_REQUEST = (
    r"garanti|guarantee|toujours en vigueur|encore en vigueur|still in force|still valid|currently in force"
    r"|sera accept|will be accepted|sera approuv|will be approved|sans contr[oô]le|without (?:any )?(?:check|control)"
    r"|d[ée]duire.{0,80}complet|deduce.{0,80}complete|officiellement complet|officially complete"
    # applicability of a text to the user's current procedure
    r"|v[ée]rifier avant d.appliquer|verify before applying|before applying (?:this|the) text"
    # Arabic: explicit guarantee phrasings only ("مضمون ولادة" is a birth certificate, "الضمان الاجتماعي" social
    # security; neither is a guarantee request).
    r"|اضمن لي|تضمن لي|هل تضمن|ضمان قبول|ما زال ساري|مازال ساري|ساري المفعول|سارية المفعول|سيقبل ملف|سيتم قبول"
)
LIMITS_REPLY = {
    "fr": "Je ne peux garantir ni qu'un texte officiel est toujours en vigueur, ni qu'un dossier sera accepté ou "
          "complet : mes sources sont des documents officiels dont l'applicabilité actuelle n'est pas vérifiée, "
          "et seule l'administration compétente se prononce sur un dossier. Je peux citer ce que disent les textes "
          "sur un point précis (pièces, frais, délais, article) : posez votre question sur ce point.",
    "en": "I cannot guarantee that an official text is still in force, nor that a file will be accepted or is "
          "complete: my sources are official documents whose current applicability is not verified, and only the "
          "competent administration decides on a file. I can quote what the texts say on a specific point "
          "(documents, fees, deadlines, an article): please ask about that point.",
    "ar": "لا يمكنني ضمان أن نصا رسميا ما زال ساري المفعول، ولا أن ملفا سيقبل أو أنه مكتمل: مصادري وثائق رسمية لم "
          "يتم التحقق من سريانها الحالي، والإدارة المختصة وحدها تبت في الملف. يمكنني نقل ما تنص عليه النصوص بخصوص "
          "نقطة محددة (الوثائق، المعاليم، الآجال، فصل معين): اطرح سؤالك حول هذه النقطة.",
    "derja": "ما نجمش نضمنلك اللي نص رسمي مازال ساري، ولا اللي الملف باش يتقبل ولا كامل: المصادر متاعي وثائق رسمية "
             "ما تثبتناش من سريانها توا، والإدارة وحدها تقرر في الملف. نجم ننقلك شنوة تقول النصوص على نقطة محددة "
             "(الأوراق، المعاليم، الآجال، فصل): اسألني على النقطة هاذي.",
}
COVERED_CATEGORIES = {"passport", "national_id", "business_registration", "general"}


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower().replace("’", "'")
    return re.sub(r"[\u064b-\u0652\u0640]", "", text)  # Arabic diacritics and tatweel


def _hits(text: str, patterns: list[str]) -> int:
    return sum(1 for p in patterns if re.search(p if p.startswith(r"\b") else re.escape(p), text))


def _rule_category(text: str) -> str | None:
    from agents.legal_evidence import identify_subject
    if identify_subject(text) or RNE_CODE.search(text):
        return 'business_registration'
    scores = {c: _hits(text, kws) for c, kws in CATEGORY_KEYWORDS.items()}
    # Birth certificates are listed as supporting documents of other procedures; another
    # procedure named in the same message takes precedence.
    if scores["birth_certificate"] and any(scores[c] for c in ("passport", "national_id")):
        scores["birth_certificate"] = 0
    best = max(scores, key=lambda c: scores[c])
    return best if scores[best] else None


def _rule_intent(text: str) -> str | None:
    # "For the purpose of" is not a deadline, including titles about loss/theft.
    text = re.sub(r"من\s+أجل", "", text)
    for intent, kws in INTENT_KEYWORDS.items():
        if _hits(text, kws):
            return intent
    return None


def next_agent_for(category: str, intent: str) -> str:
    if intent in {"greeting", "out_of_scope", "form_help"} or category in {"none", "birth_certificate"}:
        return "reply"
    if category in CHECKLIST_CATEGORIES:
        return "checklist"
    if category == "business_registration" and intent in BUSINESS_CHECKLIST_INTENTS:
        return "checklist"
    return "answer"


def _reply_text(category: str, intent: str, lang: str) -> str | None:
    if intent == "greeting":
        return i18n.t("greeting", lang)
    if category == "birth_certificate":
        return i18n.t("uncovered_category", lang)
    if intent == "form_help":
        return i18n.t("greeting", lang)
    if intent == "out_of_scope" or category == "none":
        return i18n.t("out_of_scope", lang)
    return None


class IntentRouter:
    def __init__(self, llm: OllamaChatClient | None, prompts: PromptLibrary, llm_fallback: bool = True):
        self.llm = llm
        self.prompts = prompts
        self.llm_fallback = llm_fallback

    def route(self, req: RouteRequest) -> RouteDecision:
        if re.search(LIMITS_REQUEST, _normalize(req.text)):
            # Validity, acceptance and completeness are never certified: answer deterministically instead of
            # letting a generator assert them (the corpus marks every text's applicability as unverified).
            lang = req.language or detect_language(req.text)
            category = _rule_category(_normalize(req.text)) or "general"
            return RouteDecision(language=lang, intent="procedure_info", procedure_category=category,
                                 next_agent="reply", reply=LIMITS_REPLY[lang], method="rules", context=req.context)
        if req.context is not None:
            from agents.dialogue import route_dialogue
            decision = route_dialogue(self,req)
            if decision is not None:
                return decision
        lang = req.language or detect_language(req.text)
        text = _normalize(req.text)
        hints = [h for h, kws in HINT_KEYWORDS.items() if _hits(text, kws)]
        category = _rule_category(text)
        intent = _rule_intent(text)
        method, prompt_ref = "rules", None

        if category is None:
            from agents.legal_evidence import CLARIFY, requested_article
            if requested_article(req.text) is not None:
                # An article number without the act it belongs to cannot be resolved: ask, never guess.
                return RouteDecision(language=lang, intent="procedure_info", procedure_category="general",
                                     hints=hints, next_agent="reply", reply=CLARIFY[lang], method="rules")
            greeting = _hits(text, GREETING_KEYWORDS) > 0
            if greeting and len(text.split()) <= 6:
                category, intent = "none", "greeting"
            elif self.llm_fallback and self.llm is not None:
                category, intent, prompt_ref = self._llm_classify(req.text, intent)
                method = "llm" if prompt_ref else "default"
            else:
                category, method = "general", "default"
        if intent is None:
            intent = "procedure_info"
        if category == "none" and intent not in {"greeting", "out_of_scope"}:
            intent = "out_of_scope"

        nxt = next_agent_for(category, intent)
        if intent == "form_help":
            from agents.legal_evidence import identify_form
            if identify_form(req.text):
                # A question about what an official form says is answered from its printed text, not with
                # the upload instructions.
                category, intent, nxt = "business_registration", "procedure_info", "answer"
        # A question naming an RNE procedure code is answered from the official table row.
        if category == "business_registration" and RNE_CODE.search(req.text):
            nxt = "checklist"
        elif category == "business_registration":
            from agents.legal_evidence import identify_subject
            if identify_subject(req.text):
                nxt = 'answer'
            elif nxt == 'checklist' and not _hits(text, TABLE_SIGNALS):
                nxt = 'answer'
        return RouteDecision(
            language=lang, intent=intent, procedure_category=category, hints=hints, next_agent=nxt,
            reply=_reply_text(category, intent, lang) if nxt == "reply" else None,
            method=method, prompt_ref=prompt_ref,
        )

    def _llm_classify(self, message: str, rule_intent: str | None) -> tuple[str, str | None, str | None]:
        spec = self.prompts.get("intent_router")
        try:
            result = self.llm.run(spec, message=message)
            data = json.loads(result.text)
        except (LLMError, json.JSONDecodeError, TypeError) as exc:
            log.warning("intent_llm_failed", extra={"fields": {"error": type(exc).__name__}})
            return "general", rule_intent, None
        category = data.get("procedure_category")
        intent = data.get("intent")
        valid_categories = set(CATEGORY_KEYWORDS) | {"general", "none"}
        valid_intents = set(INTENT_KEYWORDS) | {"procedure_info", "greeting", "out_of_scope"}
        if category not in valid_categories:
            category = "general"
        if intent not in valid_intents:
            intent = rule_intent
        return category, rule_intent or intent, spec.ref
