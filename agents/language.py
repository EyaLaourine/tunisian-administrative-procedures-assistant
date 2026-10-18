"""Deterministic language identification for user messages: en, fr, ar (MSA) or derja.

Tunisian Derja is written either in Arabic script or in Latin script with digits standing for
Arabic letters ("3" = ع, "7" = ح, "9" = ق). The marker lists below are common function words and
question words, not administrative content.

`resolve_language` decides the response language of one message (AUTO mode):
1. an explicitly forced language (API callers, menu commands) wins;
2. otherwise a confident detection of the message itself;
3. a long Latin-script message without any marker may be classified by the local model (enum-validated);
4. a short or ambiguous message ("oui", "ok", "في تونس", "RNE C 001") keeps the conversation language,
   then the user's optional preferred language;
5. otherwise the best deterministic guess.
The language of retrieved official documents never influences this decision.
"""

import json
import logging
import re
import unicodedata
from dataclasses import dataclass

log = logging.getLogger(__name__)

LANGUAGES = ("en", "fr", "ar", "derja")
LANGUAGE_NAMES = {
    "en": "English",
    "fr": "French",
    "ar": "Modern Standard Arabic",
    "derja": "Tunisian Arabic (Derja), written in Arabic script",
}

_ARABIC = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
_LATIN = re.compile(r"[A-Za-zÀ-ÿ]")
_WORD = re.compile(r"[\w']+", re.UNICODE)
_TASHKEEL = re.compile(r"[ً-ْـ]")

# Derja in Arabic script. Strong markers are not used in Modern Standard Arabic; weak ones also occur in
# MSA or other dialects, so they only tip the balance.
_DERJA_ARABIC_STRONG = {
    "شنوة", "شنوا", "شنية", "شنيا", "شنو", "اشنوة", "آشنوة", "كيفاش", "قداش", "قداه", "وقتاش", "وقتاه",
    "علاش", "علاه", "منين", "شكون", "نحب", "باش", "بش", "برشا", "برشة", "فما", "مافماش", "فماش", "توا",
    "ننجم", "تنجم", "نجمش", "زادة", "زادا", "هاذا", "هاذي", "هذايا", "هاذيكا", "ياسر", "بربي", "يعيشك",
    "عسلامة", "متاع", "متاعي", "متاعك", "متاعو", "لازمني", "يلزمني", "يلزمك", "لازمك", "نهز", "نبدل",
    "الباسبور", "باسبور", "الكارطة", "كارطة", "موش", "ماهوش", "ماهيش", "ماعنديش", "عنديش", "نعرفش",
    "مانعرفش", "ياخي", "البرا", "تاو", "نلقى", "نخلص", "تحبش", "نحبش",
}
_DERJA_ARABIC_WEAK = {
    "عندي", "وين", "تو", "اللي", "هوني", "ساكن", "نجم", "نعمل", "نطلع", "نخرج", "مازال", "برك", "تحب", "يحب",
}
# Modern Standard Arabic function words and question forms that Derja speakers rarely write.
_MSA_ARABIC = {
    "هل", "ماذا", "لماذا", "متى", "أين", "كم", "أريد", "أود", "أرغب", "يجب", "ينبغي", "يمكن", "يمكنني",
    "الذي", "التي", "الذين", "لدي", "إلى", "حول", "بخصوص", "المطلوبة", "ليس", "لست", "سوف", "ذلك",
    "هذه", "هذا", "فيما", "يخص", "ما",
}
_DERJA_LATIN = {
    "chnowa", "chnoua", "chnouwa", "chnowwa", "chnouma", "chnia", "chneya", "chniya", "chnya", "chnoa",
    "kifech", "kifach", "kifeh", "kif", "9adech", "9adeh", "qadech", "kadech", "9addech", "ch7al", "wa9tech",
    "wa9teh", "waqtech", "3lech", "3lach", "3leh", "chkoun", "chkon", "nheb", "n7eb", "n7ib", "nhib", "t7eb",
    "bech", "bch", "bach", "barcha", "barsha", "famma", "fama", "famech", "mafamech", "tawa", "taw", "nejjem",
    "najjem", "nejem", "najem", "na3mel", "n3mel", "zeda", "zada", "hedha", "hedhi", "yesser", "barra",
    "brabbi", "ya3tik", "y3aychek", "3aychek", "aslema", "3aslema", "mta3", "mte3", "mta3i", "mte3i",
    "lezmni", "lazemni", "lezemni", "lezmek", "lazmek", "yelzem", "yelzemni", "lazem", "lezem", "lazmin",
    "3andi", "andi", "ma3andich", "maandich", "ness", "kima", "chbih", "nekhou", "nekhdh", "ne5ou", "na5ou",
    "ya5ou", "yekhou", "nod5el", "nemchi", "nestanna", "njadded", "njaded", "njeded", "nbaddel", "nbadel",
    "nhez", "nhezz", "netla3", "nkharej", "nkhalles", "n5alles", "5arej", "kharej", "7aja", "l7aja", "lwra9",
    "wra9", "lwara9", "war9a", "lwar9a", "passbor", "basbor", "lpassport", "lpasseport", "karta", "lkarta",
    "elli", "illi", "ya5i", "yezzi", "behi", "mrigel", "sa7a", "ena", "enti", "inti", "nta", "a7na", "houma",
    "mouch", "moch", "mech", "ken", "fil", "fel", "lel", "mel", "3al", "3la", "nzid", "n3awed",
}
_EN = {
    "the", "what", "how", "which", "do", "does", "i", "need", "my", "to", "for", "is", "are", "an", "of",
    "where", "when", "much", "documents", "renew", "get", "can", "you", "please", "hello", "hi", "thanks",
    "company", "register", "fee", "fees", "cost", "required", "card", "should", "would", "will", "with",
    "and", "or", "if", "it", "this", "that", "there", "have", "has", "am", "lost", "apply", "application",
    "who", "why", "many", "long", "take", "about", "identity", "birth", "certificate", "replace", "abroad",
    "live", "in", "on", "me", "your", "be", "duplicate", "first", "time", "new",
}
_FR = {
    "le", "la", "les", "des", "de", "du", "un", "une", "est", "quels", "quelles", "quel", "quelle",
    "comment", "pour", "je", "mon", "ma", "mes", "pièces", "fournir", "renouveler", "passeport",
    "obtenir", "carte", "société", "créer", "frais", "délai", "où", "bonjour", "merci", "faut", "il",
    "et", "dois", "combien", "coût", "s'il", "vous", "plaît", "nationale", "d'identité", "en", "au", "aux",
    "que", "qui", "quoi", "dans", "sur", "avec", "pas", "ne", "mais", "ou", "si", "j'ai", "c'est", "qu'est",
    "perdu", "perte", "vol", "renouvellement", "première", "fois", "dossier", "démarche", "faire",
    "peux", "puis", "veux", "voudrais", "besoin", "papiers", "documents", "inscription", "registre",
    "entreprise", "sarl", "suarl", "duplicata", "réside", "vis", "habite", "étranger", "tunisie",
}
# Acknowledgements and one-word answers never switch the conversation language on their own.
_ACK = {
    "oui", "non", "ok", "okay", "merci", "yes", "no", "thanks", "thank", "d'accord", "daccord", "parfait",
    "behi", "bahi", "mrigel", "sahit", "sa7it", "ey", "eyh", "ih", "eh", "la", "svp", "stp", "bien",
    "اي", "ايه", "إيه", "أيه", "نعم", "لا", "شكرا", "باهي", "مريقل", "يعيشك", "صحيت", "اوكي",
}
_ARABIZI = re.compile(r"[a-z][2379]|[2379][a-z]")


@dataclass(frozen=True)
class LanguageGuess:
    language: str
    confident: bool
    scores: dict


def _words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(unicodedata.normalize("NFKC", text))]


def detect_language_details(text: str) -> LanguageGuess:
    words = _words(text)
    content = [w for w in words if not w.isdigit()]
    only_ack = bool(content) and all(w in _ACK for w in content)
    short = len(content) <= 2

    if len(_ARABIC.findall(text)) > len(_LATIN.findall(text)):
        derja = msa = 0
        for w in (_TASHKEEL.sub("", w) for w in words):
            bare = w.removeprefix("و") if len(w) > 3 else w
            if w in _DERJA_ARABIC_STRONG or bare in _DERJA_ARABIC_STRONG:
                derja += 2
            elif w in _DERJA_ARABIC_WEAK or bare in _DERJA_ARABIC_WEAK:
                derja += 1
            if w in _MSA_ARABIC or bare in _MSA_ARABIC:
                msa += 1
        language = "derja" if derja > msa or (derja >= 2 and derja == msa) else "ar"
        gap = abs(derja - msa)
        confident = not only_ack and (gap >= 3 if short else (gap >= 2 or len(content) >= 4))
        return LanguageGuess(language, confident, {"derja": derja, "ar": msa})

    # Latin script: English, French or Arabizi Derja ("3", "7", "9" inside words, or Derja markers).
    arabizi = sum(1 for w in words if _ARABIZI.search(w))
    derja = sum(1 for w in words if w in _DERJA_LATIN and len(w) > 2) + 2 * arabizi
    en = sum(1 for w in words if w in _EN)
    fr = sum(1 for w in words if w in _FR)
    if re.search(r"[éèêàçùâîôûœ]", text.lower()):
        fr += 2
    scores = {"derja": derja, "en": en, "fr": fr}
    if derja >= 2 and derja >= max(en, fr):
        language = "derja"
    elif en > fr:
        language = "en"
    else:
        language = "fr"
    best, second = sorted(scores.values(), reverse=True)[:2]
    confident = not only_ack and best > second and (best >= 3 if short else (best >= 2 or len(content) >= 3))
    return LanguageGuess(language, confident, scores)


def detect_language(text: str) -> str:
    return detect_language_details(text).language


def _model_language(text: str, llm, prompts) -> str | None:
    """Local-model fallback for long Latin-script messages without any marker. Enum-validated."""
    try:
        res = llm.run(prompts.get("language_identification"), message=text)
        value = json.loads(res.text).get("language")
    except Exception as exc:  # no message content is logged
        log.warning("language_model_unavailable", extra={"fields": {"error": type(exc).__name__}})
        return None
    return value if value in {"en", "fr", "derja"} else None


def resolve_language(text: str, forced: str | None = None, context=None, llm=None, prompts=None) -> tuple[str, str]:
    """Returns (language, method); method is forced | detected | model | context | preference | default."""
    if forced in LANGUAGES:
        return forced, "forced"
    guess = detect_language_details(text)
    if guess.confident:
        return guess.language, "detected"
    words = [w for w in _words(text) if not w.isdigit()]
    latin = len(_LATIN.findall(text)) >= len(_ARABIC.findall(text))
    if latin and len(words) >= 4 and not any(guess.scores.values()) and llm is not None and prompts is not None:
        model = _model_language(text, llm, prompts)
        if model:
            return model, "model"
    previous = getattr(context, "language", None) if context is not None else None
    if previous in LANGUAGES:
        return previous, "context"
    preferred = getattr(context, "preferred_language", None) if context is not None else None
    if preferred in LANGUAGES:
        return preferred, "preference"
    return guess.language, "default"
