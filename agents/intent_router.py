"""Intent Router agent: language, procedure category, intent and the next agent to call.

Deterministic keyword rules run first. The LLM (versioned prompt `intent_router`) is consulted only
when the rules cannot identify a procedure, and its output is validated against fixed enums.
"""

import json
import logging
import re
import unicodedata

from agents import i18n
from agents.language import detect_language, resolve_language
from agents.llm import LLMError, OllamaChatClient
from agents.prompts import PromptLibrary
from agents.schemas import RouteDecision, RouteRequest

log = logging.getLogger(__name__)

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "passport": ["passeport", "passport", "passbor", "basbor", "paspor", "باسبور", "الباسبور", "جواز",
                 "pèlerinage", "pelerinage", "pélerinage", "pilgrimage", "hajj", "الحج"],
    "national_id": [
        "carte d'identité", "carte d identite", "carte d'identite", "carte identité", "carte d identité", r"\bcin\b",
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
        # Indefinite Arabic and Latin-script Derja names of the beneficial-owner and name-reservation decrees.
        r"\bمستفيد(?:ا|ون|ين)?\s+حقيقي(?:ا|ون|ين)?", r"\b(?:mou?stafid|mustafid)\w*\s+(?:7a9i9i|ha9i9i|haqiqi|hakiki)", r"\b(?:7ajz|hajz)\b.{0,25}(?:esm|ism|tasmi|chara)",
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
             r"\bd[ée]t[ée]rior", r"\bab[îi]m[ée]", "damage", "سرق", "ضيع", "ضيّع", r"\bdh?ay+a3",
             # the official duplicate scenario: "duplicata (pour cause de perte, de vol ou de détérioration)" / "نظير"
             "نظير", "duplicata", r"\bduplicate\b"],
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
UNMATCHED_CASE = (
    r"ne correspond pas|ne s.applique pas|mon cas est (?:diff|particul|sp[ée]cial|autre)|ma situation est (?:diff|particul|autre)"
    r"|does ?n.?t (?:match|apply|fit)|does not (?:match|apply|fit)|my (?:case|situation) is (?:different|special|not)"
    r"|لا ينطبق|لا تنطبق|لا يتطابق|لا يتوافق|حالتي مختلفة|حالتي خاصة|ما ينطبقش|ما تنطبقش|موش نفس الحالة"
    r"|ma yentab9ch|mayentab9ch|7alti mokhtalfa|halti mokhtalfa"
)
# Administrative documents that sound like covered ones but are not in the corpus. Without this rule they reached
# the LLM fallback, which routed "carte grise" to an answer built from the national-ID guide (held-out H17).
UNCOVERED_PROCEDURE = (
    r"cartes? grises?|permis de conduire|driving licen[cs]e|driver.?s licen[cs]e|vehicle registration|car registration"
    r"|البطاقة الرمادية|بطاقة رمادية|رخصة السياقة|رخصة القيادة|رخصة سياقة|الكارت قريز|الكرت قريز"
)
# Distinguishing facts are the official scenario headings of each guide (no exception is invented).
UNMATCHED_REPLY = {
    "fr": {
        "passport": "D'accord. Le guide officiel du passeport distingue : première demande ou renouvellement, "
                    "changement d'un passeport ordinaire, duplicata après perte, vol ou détérioration, document pour "
                    "le pèlerinage, et la résidence en Tunisie ou à l'étranger. Laquelle de ces situations est la vôtre ? "
                    "Décrivez-la sans données personnelles. Si aucune ne correspond, seule l'administration compétente "
                    "peut vous orienter.",
        "national_id": "D'accord. Le guide officiel de la carte d'identité distingue : première demande, renouvellement, "
                       "changement pour modification de données, et changement pour vol, perte ou détérioration. Laquelle "
                       "correspond à votre situation ? Si aucune ne correspond, adressez-vous à l'administration compétente.",
        "business_registration": "D'accord. Pour le RNE, précisez le genre d'entreprise (personne physique ou morale), "
                                 "son type et l'opération (création, modification, radiation, dépôt des états "
                                 "financiers…), ou le code de procédure (ex. RNE C 001). Je ne peux pas déduire qu'une "
                                 "ligne s'applique à votre cas sans ces éléments.",
        "legal": "D'accord. Précisez quel point du texte vous concerne (article, obligation, délai, personne visée), "
                 "sans données personnelles ; je ne peux pas déduire que ce texte s'applique à votre cas.",
        "general": "D'accord. Précisez la démarche et votre situation (sans données personnelles) pour que je cherche "
                   "la section officielle correspondante.",
    },
    "en": {
        "passport": "Understood. The official passport guide distinguishes: first application or renewal, change of an "
                    "ordinary passport, duplicate after loss, theft or damage, the pilgrimage travel document, and residence "
                    "in Tunisia or abroad. Which of these is your situation? Describe it without personal data. If none "
                    "applies, only the competent administration can advise you.",
        "national_id": "Understood. The official ID-card guide distinguishes: first application, renewal, change for "
                       "modified data, and change after theft, loss or damage. Which one is your situation? If none "
                       "applies, please contact the competent administration.",
        "business_registration": "Understood. For the RNE, please give the entity kind (natural or legal person), its "
                                 "type and the operation (creation, modification, deregistration, filing of financial "
                                 "statements…), or the procedure code (e.g. RNE C 001). I cannot infer that a row applies "
                                 "to your case without these details.",
        "legal": "Understood. Please say which point of the text concerns you (article, obligation, deadline, person "
                 "concerned), without personal data; I cannot infer that this text applies to your case.",
        "general": "Understood. Please describe the procedure and your situation (without personal data) so that I can "
                   "look for the matching official section.",
    },
    "ar": {
        "passport": "حسنا. يميز الدليل الرسمي لجواز السفر بين: الحصول لأول مرة أو التجديد، تغيير جواز سفر عادي، استخراج "
                    "نظير بسبب الضياع أو السرقة أو الإتلاف، رخصة الحج، والإقامة بالتراب التونسي أو بالخارج. أي حالة "
                    "تنطبق عليك؟ صفها دون معطيات شخصية. إن لم تنطبق أي منها فالإدارة المختصة وحدها يمكنها توجيهك.",
        "national_id": "حسنا. يميز الدليل الرسمي لبطاقة التعريف بين: أول مرة، التجديد، التغيير بسبب تغيير المعطيات، "
                       "والتغيير بسبب السرقة أو الضياع أو الإتلاف. أي حالة تنطبق عليك؟ إن لم تنطبق أي منها فاتصل بالإدارة المختصة.",
        "business_registration": "حسنا. بالنسبة للسجل الوطني للمؤسسات، حدد صنف المؤسسة (شخص طبيعي أو معنوي) ونوعها "
                                 "والعملية (إحداث، تغيير، تشطيب، إيداع القوائم المالية...) أو رمز الإجراء (مثلا RNE C 001). "
                                 "لا يمكنني افتراض انطباق سطر ما على حالتك دون هذه المعطيات.",
        "legal": "حسنا. حدد النقطة التي تهمك في النص (الفصل، الواجب، الأجل، الشخص المعني) دون معطيات شخصية؛ لا يمكنني "
                 "افتراض انطباق هذا النص على حالتك.",
        "general": "حسنا. صف الإجراء وحالتك دون معطيات شخصية حتى أبحث عن القسم الرسمي المناسب.",
    },
    "derja": {
        "passport": "باهي. الدليل الرسمي متاع الباسبور يفرق بين: أول مرة ولا تجديد، تبديل باسبور عادي، نظير على خاطر "
                    "ضياع ولا سرقة ولا إتلاف، رخصة الحج، والسكنى في تونس ولا البرّا. شنية الحالة متاعك؟ احكيها من غير "
                    "معطيات شخصية. كان حتى وحدة ما تنطبق، الإدارة وحدها تنجم توجهك.",
        "national_id": "باهي. الدليل الرسمي متاع بطاقة التعريف يفرق بين: أول مرة، تجديد، تبديل على خاطر تبدلت "
                       "المعطيات، وتبديل على خاطر سرقة ولا ضياع ولا إتلاف. شنية الحالة متاعك؟ كان حتى وحدة ما تنطبق، "
                       "اتصل بالإدارة.",
        "business_registration": "باهي. للـRNE، قلّي الشخص طبيعي ولا معنوي، نوع المؤسسة والعملية (إحداث، تبديل، "
                                 "تشطيب، إيداع القوائم المالية...) ولا رمز الإجراء (مثلا RNE C 001). ما نجمش نفترض "
                                 "اللي سطر ينطبق على حالتك من غير المعطيات هاذي.",
        "legal": "باهي. قلّي شنية النقطة اللي تهمك في النص (الفصل، الواجب، الأجل، الشخص المعني) من غير معطيات شخصية؛ "
                 "ما نجمش نفترض اللي النص ينطبق على حالتك.",
        "general": "باهي. احكيلي على الإجراء وحالتك من غير معطيات شخصية باش نلوج على القسم الرسمي المناسب.",
    },
}
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

    def language(self, req: RouteRequest) -> str:
        """Response language of this message (AUTO mode, see agents/language.py); computed once per request."""
        cached = getattr(req, "_resolved_language", None)
        if cached is None:
            cached = resolve_language(req.text, req.language, req.context, self.llm if self.llm_fallback else None,
                                      self.prompts)
            object.__setattr__(req, "_resolved_language", cached)
        return cached[0]

    def route(self, req: RouteRequest) -> RouteDecision:
        from agents import conversation
        decision = self._route(req)
        if decision.context is not None:
            # The conversation language travels in the dialogue context (passed through unchanged by n8n), so a
            # later short answer such as "oui" or "في تونس" keeps it. A None context still means "unchanged".
            # A pure courtesy message ("merci", "يعطيك الصحة") is answered in its own language but does not
            # redirect the conversation language.
            if not (conversation.classify(req.text) and decision.context.language):
                decision.context.language = decision.language
            decision.context.preferred_language = req.context.preferred_language if req.context else None
        return decision

    def _route(self, req: RouteRequest) -> RouteDecision:
        from agents import conversation
        kind = conversation.classify(req.text)
        if kind:
            # Affirmation, negation, gratitude, greeting or farewell: answered before any retrieval. The dialogue
            # context is returned unchanged so a pending clarification (and the procedure) is kept. The expression's
            # own language wins ("يعطيك الصحة" is Derja even in a French conversation); neutral words ("ok") follow
            # the conversation.
            lang = conversation.expression_language(req.text, req.context) or self.language(req)
            return RouteDecision(language=lang, intent="greeting", procedure_category="none", next_agent="reply",
                                 reply=conversation.reply(kind, lang, req.context), method="rules",
                                 context=req.context)
        stripped = conversation.strip_courtesy(req.text)
        if stripped != req.text:
            # "merci, et pour les frais ?" is routed as "et pour les frais ?" (not as a greeting).
            req = req.model_copy(update={"text": stripped})
        if re.search(UNMATCHED_CASE, _normalize(req.text)):
            # "My case does not match": keep the conversation context and ask for the distinguishing facts the
            # official source uses, instead of repeating the previous answer.
            lang = self.language(req)
            ctx = req.context
            category = (ctx.category if ctx and ctx.category else None) or _rule_category(_normalize(req.text)) or "general"
            key = "legal" if ctx and ctx.legal_subject else category
            reply = UNMATCHED_REPLY[lang].get(key) or UNMATCHED_REPLY[lang]["general"]
            return RouteDecision(language=lang, intent="procedure_info", procedure_category=category,
                                 hints=list(ctx.hints) if ctx else [], next_agent="reply", reply=reply,
                                 method="rules", context=ctx)
        if re.search(LIMITS_REQUEST, _normalize(req.text)):
            # Validity, acceptance and completeness are never certified: answer deterministically instead of
            # letting a generator assert them (the corpus marks every text's applicability as unverified).
            lang = self.language(req)
            category = _rule_category(_normalize(req.text)) or "general"
            return RouteDecision(language=lang, intent="procedure_info", procedure_category=category,
                                 next_agent="reply", reply=LIMITS_REPLY[lang], method="rules", context=req.context)
        if re.search(UNCOVERED_PROCEDURE, _normalize(req.text)) and _rule_category(_normalize(req.text)) is None:
            lang = self.language(req)
            return RouteDecision(language=lang, intent="out_of_scope", procedure_category="none", next_agent="reply",
                                 reply=_reply_text("none", "out_of_scope", lang), method="rules", context=req.context)
        if req.context is not None:
            from agents.dialogue import route_dialogue
            decision = route_dialogue(self,req)
            if decision is not None:
                return decision
        lang = self.language(req)
        text = _normalize(req.text)
        hints = [h for h, kws in HINT_KEYWORDS.items() if _hits(text, kws)]
        category = _rule_category(text)
        intent = _rule_intent(text)
        method, prompt_ref = "rules", None

        if category is None:
            from agents.legal_evidence import CLARIFY, identify_form, requested_article
            if identify_form(req.text):
                # A question about the printed content of an official RNE form (F-001, F-002) is recognised
                # deterministically, before the LLM fallback (which classified it as out of scope).
                category, intent = "business_registration", "procedure_info"
            elif requested_article(req.text) is not None:
                # An article number without the act it belongs to cannot be resolved: ask, never guess.
                return RouteDecision(language=lang, intent="procedure_info", procedure_category="general",
                                     hints=hints, next_agent="reply", reply=CLARIFY[lang], method="rules")
        if category is None:
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
