"""Lightweight conversational intents handled before the administrative pipeline (deterministic, no LLM).

A message is small talk only when every word belongs to the lexicons below (affirmation, negation, gratitude,
greeting, farewell, plus a few fillers such as "beaucoup" or "برشا"). Anything else ("oui, en Tunisie",
"merci, et pour les frais ?") goes through the normal routing, after a leading or trailing courtesy word is
removed. Replies never contain administrative facts; an affirmation or negation is interpreted against the
clarification question still pending in the dialogue context.
"""

import re
import unicodedata

_PUNCT = re.compile(r"[^\w\s']+", re.UNICODE)
_TASHKEEL = re.compile(r"[ً-ْـ]")
_REPEAT = re.compile(r"(\w)\1{2,}", re.UNICODE)  # "merciii", "okkk", "شكراااا"

# Multi-word expressions are joined before word matching.
_PHRASES = {
    "thank you": "thanks", "thanks a lot": "thanks", "merci beaucoup": "merci", "mille merci": "merci",
    "يعطيك الصحة": "يعيشك", "يعطيك الصحه": "يعيشك", "ya3tik saha": "ya3tik", "ya3tik essa7a": "ya3tik",
    "ya3tik sa7a": "ya3tik", "yaatik saha": "ya3tik", "yaatik sa7a": "ya3tik", "yaatek saha": "ya3tik",
    "ya3tek saha": "ya3tik", "y3atik saha": "ya3tik", "barak allahou fik": "merci", "بارك الله فيك": "شكرا", "الله يبارك فيك": "شكرا",
    "السلام عليكم": "سلام", "au revoir": "bye", "bonne journée": "bye", "bonne soirée": "bye", "à bientôt": "bye",
    "a bientot": "bye", "good bye": "bye", "see you": "bye", "مع السلامة": "بالسلامة", "bi slema": "bslema",
    "d'accord": "ok", "c'est bon": "ok", "ça marche": "ok", "ca marche": "ok", "bien sûr": "oui", "bien sur": "oui",
    "pas du tout": "non", "no thanks": "non thanks", "non merci": "non merci",
}
AFFIRM = {
    "oui", "ouais", "ouaip", "yes", "yeah", "yep", "yup", "ok", "okay", "daccord", "parfait", "exact",
    "exactement", "certainement", "sure", "correct", "right", "alright", "ey", "eyy", "eyh", "ih", "iyeh", "eh",
    "behi", "bahi", "mrigel", "sahit", "sa7it", "tamam", "naam", "na3am", "نعم", "اي", "ايه", "ايوا", "اكيد",
    "باهي", "مريقل", "تمام", "صحيح", "صحيت", "اوكي",
}
DENY = {"non", "no", "nope", "nan", "la", "le", "lala", "mouch", "moch", "لا", "لالا", "موش", "ابدا", "never"}
THANKS = {"merci", "thanks", "thx", "ty", "choukran", "chokran", "shukran", "y3aychek", "ya3tik", "3aychek",
          "yaichek", "شكرا", "يعيشك", "مرسي", "متشكر"}
GREETING = {"bonjour", "bonsoir", "salut", "hello", "hi", "hey", "salam", "slm", "aslema", "3aslema", "ahla",
            "ahlan", "marhba", "مرحبا", "سلام", "عسلامة", "اهلا", "أهلا", "اهلين", "صباح", "مساء", "الخير", "النور"}
FAREWELL = {"bye", "ciao", "tchao", "bslema", "beslema", "بالسلامة", "بسلامة", "وداعا"}
FILLER = {"beaucoup", "bcp", "bien", "très", "tres", "vraiment", "encore", "alors", "a", "lot", "so", "much",
          "very", "you", "u", "monsieur", "madame", "sir", "برشا", "برشة", "جزيلا", "ياسر", "سيدي", "خويا", "و",
          "w", "et", "and", "ça", "ca", "va", "cava", "labes", "لاباس", "then", "barcha", "yesser", "khouya", "please"}
_ALL = AFFIRM | DENY | THANKS | GREETING | FAREWELL
_WORDS = _ALL | FILLER


def _tokens(text: str) -> list[str]:
    t = unicodedata.normalize("NFKC", text).lower().replace("’", "'")
    t = _TASHKEEL.sub("", t).replace("إ", "ا").replace("أ", "ا").replace("آ", "ا").replace("ى", "ي")
    t = _REPEAT.sub(r"\1", _PUNCT.sub(" ", t))
    t = f" {' '.join(t.split())} "
    for phrase, repl in sorted(_PHRASES.items(), key=lambda p: -len(p[0])):
        t = t.replace(f" {phrase} ", f" {repl} ")
    return t.split()


# Full-message matches only: never treat a negative document declaration or a
# courtesy prefix followed by a real administrative question as conversation closing.
_DERJA_CLOSING = re.compile(
    r"(?:le|la)\s+ma\s*nhe+b{1,2}\s+(?:chay|chey|chayy|chai)\s+(?:ekhr|ekher|e5er|akher)"
    r"|barra\s+(?:ya+tik|ya3tik|yaatek|y3atik)\s+(?:saha|sa7a|essa7a)"
)


def _closing_text(text: str) -> str:
    # Accent folding is limited to this bounded matcher (e.g. 'lé').
    folded = "".join(c for c in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(c))
    return " ".join(_REPEAT.sub(r"\1", _PUNCT.sub(" ", folded)).split())


def _is_derja_closing(text: str) -> bool:
    normalized = _closing_text(text)
    return bool(_DERJA_CLOSING.fullmatch(normalized)) or normalized in {"la merci", "le merci"}


def classify(text: str, context=None) -> str | None:
    """closing | affirm | deny | thanks | greeting | farewell; substantive text returns None."""
    # "barra" also means "abroad": while residence is being clarified, a short
    # "barra + thanks" is a substantive answer, not a farewell.
    residence_answer = (
        _closing_text(text).startswith("barra ") and _is_derja_closing(text)
        and context is not None and context.category == "passport"
        and context.pending_intent and context.residence is None
    )
    if residence_answer:
        return None
    if _is_derja_closing(text) or _closing_text(text) == "non merci":
        return "closing"
    words = _tokens(text)
    if not words or len(words) > 6 or not all(w in _WORDS for w in words) or not any(w in _ALL for w in words):
        return None
    present = set(words)
    for kind, lexicon in (("thanks", THANKS), ("farewell", FAREWELL), ("deny", DENY), ("affirm", AFFIRM),
                          ("greeting", GREETING)):
        if present & lexicon:
            return kind
    return None


# Language carried by the courtesy expression itself. Arabic-script words shared by MSA and Derja ("شكرا", "نعم")
# follow the conversation (Derja if it is Derja, else MSA); neutral words ("ok", "bye") follow the conversation.
_EXPRESSION_LANGUAGE = {
    "derja": {"ya3tik", "y3aychek", "3aychek", "yaichek", "behi", "bahi", "mrigel", "sahit", "sa7it", "bslema",
              "beslema", "aslema", "3aslema", "ey", "eyy", "eyh", "iyeh", "le", "lala", "mouch", "moch", "khouya",
              "barcha", "yesser", "يعيشك", "باهي", "مريقل", "صحيت", "عسلامة", "بالسلامة", "موش", "برشا",
              "برشة", "خويا", "لاباس", "ياسر"},
    "fr": {"merci", "oui", "ouais", "non", "nan", "daccord", "parfait", "exactement", "certainement", "bonjour",
           "bonsoir", "salut", "beaucoup", "bcp", "tres", "très", "vraiment", "monsieur", "madame"},
    "en": {"thanks", "thx", "yes", "yeah", "yep", "yup", "no", "nope", "hello", "hi", "hey", "sure", "please",
           "much", "lot", "very", "sir", "alright", "right", "correct"},
    "arabic": {"شكرا", "نعم", "لا", "مرحبا", "سلام", "اهلا", "اي", "ايه", "ايوا", "اكيد", "جزيلا", "صباح", "مساء",
               "الخير", "النور", "وداعا", "صحيح", "متشكر", "مرسي"},
}


def expression_language(text: str, context=None) -> str | None:
    """Language of a pure courtesy message from its own words, or None when its words are neutral ("ok")."""
    if _is_derja_closing(text):
        return "derja"
    words = set(_tokens(text))
    conversation = getattr(context, "language", None) or getattr(context, "preferred_language", None)
    if words & _EXPRESSION_LANGUAGE["derja"]:
        return "derja"
    if words & _EXPRESSION_LANGUAGE["fr"]:
        # French courtesy words ("merci", "oui", "bonjour") are everyday Derja too: keep Derja in a Derja conversation.
        return "derja" if conversation == "derja" else "fr"
    if words & _EXPRESSION_LANGUAGE["en"]:
        return "en"
    if words & _EXPRESSION_LANGUAGE["arabic"]:
        return "derja" if conversation == "derja" else "ar"
    return None


def strip_courtesy(text: str) -> str:
    """Removes leading/trailing courtesy words ("merci, et pour les frais ?" -> "et pour les frais ?"), keeping the
    question's own punctuation. Returns the text unchanged when nothing substantive would remain."""
    words = list(re.finditer(r"[^\s,.!؟?;:،]+", text))
    if len(words) < 2:
        return text
    first, last = 0, len(words)
    while first < last and classify(words[first].group()) in {"thanks", "affirm", "greeting"}:
        first += 1
    while last > first and classify(words[last - 1].group()) in {"thanks", "greeting", "farewell"}:
        last -= 1
    if first == 0 and last == len(words) or first >= last:
        return text
    end = words[last].start() if last < len(words) else len(text)
    rest = text[words[first].start():end].rstrip(" ,;:،")
    return rest if classify(rest) is None else text


REPLIES = {
    "closing": {
        "en": "Alright, goodbye!",
        "fr": "D’accord, bonne continuation !",
        "ar": "حسنا، مع السلامة!",
        "derja": "باهي، بالسلامة! ربي يسهّل.",
    },
    "thanks": {
        "en": "You're welcome! If you have another question, I'm here.",
        "fr": "Avec plaisir ! Si vous avez une autre question, je suis là.",
        "ar": "على الرحب والسعة! إن كان لديك سؤال آخر فأنا في الخدمة.",
        "derja": "يعيشك، مرحبا بيك! كان عندك سؤال آخر، أنا هوني.",
    },
    "farewell": {
        "en": "Goodbye, and good luck with your procedure!",
        "fr": "Au revoir, et bon courage pour votre démarche !",
        "ar": "مع السلامة، وبالتوفيق في إجراءاتك!",
        "derja": "بالسلامة، ربي يسهّل في الإجراءات متاعك!",
    },
    "affirm": {
        "en": "Alright! You can ask me something else, for example about fees, processing time or where to submit the file.",
        "fr": "D'accord ! Vous pouvez me poser une autre question, par exemple sur les frais, le délai ou le lieu de dépôt.",
        "ar": "حسنا! يمكنك أن تطرح سؤالا آخر، مثلا حول المعاليم أو الآجال أو مكان إيداع الملف.",
        "derja": "باهي! تنجم تسألني على حاجة أخرى، كيف قدّاش تخلّص، قدّاش ياخو وقت، ولا وين تحطّ الملف.",
    },
    "deny": {
        "en": "Alright. If you need anything else, just ask.",
        "fr": "D'accord. Si vous avez besoin d'autre chose, posez votre question.",
        "ar": "حسنا. إن احتجت إلى شيء آخر فاطرح سؤالك.",
        "derja": "باهي. كان تحتاج حاجة أخرى، اسألني.",
    },
    "greeting_short": {
        "en": "Hello! How can I help you?",
        "fr": "Bonjour ! Comment puis-je vous aider ?",
        "ar": "مرحبا! كيف يمكنني مساعدتك؟",
        "derja": "عسلامة! كيفاش نجم نعاونك؟",
    },
    "reask": {
        "en": "To continue, I need this detail:",
        "fr": "Pour continuer, j'ai besoin de cette précision :",
        "ar": "للمواصلة، أحتاج إلى هذا التوضيح:",
        "derja": "باش نكمّل معاك، قلّي:",
    },
}


def pending_question(context, language: str) -> str | None:
    """The clarification the assistant is still waiting for (passport case or legal act), if any."""
    if context is None or not context.pending_intent:
        return None
    if context.category == "passport":
        from agents.dialogue import clarify
        return clarify(context, language)
    if context.category == "national_id":
        from agents.dialogue import APPLICATIONS, UI
        return None if any(h in APPLICATIONS for h in context.hints) else UI[language]["cin_application"]
    if context.category == "business_registration" and not context.legal_subject:
        if context.pending_intent in {"fees", "processing_time", "required_documents"}:
            if context.rne_code:
                return None
            from agents.rne_registration import QUESTION
            return QUESTION[language]  # the pending question is the legal form of the business
        from agents.legal_evidence import CLARIFY
        return CLARIFY[language]  # the pending question is which legal act (an article was asked without one)
    return None


def reply(kind: str, language: str, context) -> str:
    from agents.i18n import t
    question = pending_question(context, language)
    if kind in {"affirm", "deny"} and question:
        # "oui"/"non" cannot answer an either/or clarification: ask it again instead of guessing.
        return REPLIES["reask"][language] + "\n\n" + question
    if kind == "greeting":
        ongoing = context is not None and (context.category or context.last_intent)
        text = REPLIES["greeting_short"][language] if ongoing else t("greeting", language)
        return text + ("\n\n" + question if question else "")
    return REPLIES[kind][language]
