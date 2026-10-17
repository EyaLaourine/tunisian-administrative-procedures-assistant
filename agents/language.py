"""Deterministic language identification for user messages: en, fr, ar (MSA) or derja.

Tunisian Derja is written either in Arabic script or in Latin script with digits standing for
Arabic letters ("3" = ع, "7" = ح, "9" = ق). The marker lists below are common function words and
question words, not administrative content.
"""

import re
import unicodedata

LANGUAGES = ("en", "fr", "ar", "derja")
LANGUAGE_NAMES = {
    "en": "English",
    "fr": "French",
    "ar": "Modern Standard Arabic",
    "derja": "Tunisian Arabic (Derja), written in Arabic script",
}

_ARABIC = re.compile(r"[\u0600-\u06ff\u0750-\u077f\ufb50-\ufdff\ufe70-\ufeff]")
_LATIN = re.compile(r"[A-Za-zÀ-ÿ]")
_WORD = re.compile(r"[\w']+", re.UNICODE)

_DERJA_ARABIC = {
    "شنوة", "شنوا", "شنية", "شنيا", "كيفاش", "قداش", "وقتاش", "علاش", "منين", "شكون", "وين",
    "نحب", "نحبّ", "باش", "بش", "برشا", "فما", "مافماش", "توا", "تو", "نجم", "نجّم", "نعمل",
    "زادة", "هاذا", "هاذي", "هذايا", "ياسر", "بربي", "يعيشك", "عسلامة", "متاع", "متاعي", "متاعك",
    "لازمني", "نطلع", "نخرج", "الباسبور", "الكارطة", "باسبور", "كارطة", "مازال", "عندي",
}
_DERJA_LATIN = {
    "chnowa", "chnoua", "chnia", "chneya", "chniya", "kifech", "kifach", "kifeh", "9adech", "qadech",
    "9addech", "wa9tech", "waqtech", "3lech", "3lach", "chkoun", "win", "nheb", "n7eb", "n7ib", "nhib",
    "bech", "bch", "barcha", "famma", "fama", "tawa", "taw", "nejjem", "najjem", "na3mel", "n3mel",
    "zeda", "zada", "hedha", "hedhi", "yesser", "barra", "brabbi", "ya3tik", "y3aychek", "aslema",
    "3aslema", "mta3", "mte3", "mta3i", "lezmni", "lazemni", "3andi", "andi", "ness", "kima", "chbih",
    "nekhou", "nekhdh", "ne5ou", "na5ou", "ya5ou", "yekhou", "nod5el", "nemchi", "nestanna", "lezem", "mte3i",
    "passbor", "basbor", "karta", "lkarta", "el", "w", "ena", "enti", "inti",
}
_EN = {
    "the", "what", "how", "which", "do", "does", "i", "need", "my", "to", "for", "is", "are", "a",
    "an", "of", "where", "when", "much", "documents", "renew", "get", "can", "you", "please", "hello",
    "hi", "thanks", "passport", "company", "register", "fee", "fees", "cost", "required", "card",
}
_FR = {
    "le", "la", "les", "des", "de", "du", "un", "une", "est", "quels", "quelles", "quel", "quelle",
    "comment", "pour", "je", "mon", "ma", "mes", "pièces", "fournir", "renouveler", "passeport",
    "obtenir", "carte", "société", "créer", "frais", "délai", "où", "bonjour", "merci", "faut", "il",
    "et", "dois", "documents", "combien", "coût", "s'il", "vous", "plaît", "nationale", "d'identité",
}


def _words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(unicodedata.normalize("NFKC", text))]


def detect_language(text: str) -> str:
    words = _words(text)
    arabic_chars = len(_ARABIC.findall(text))
    latin_chars = len(_LATIN.findall(text))

    if arabic_chars > latin_chars:
        normalized = {w.replace("\u0651", "") for w in words}
        derja_hits = sum(1 for w in normalized if w in _DERJA_ARABIC or w.removeprefix("و") in _DERJA_ARABIC)
        return "derja" if derja_hits else "ar"

    # Latin-script Derja ("Arabizi"): letters mixed with 3/7/9 inside a word, or Derja markers.
    arabizi_tokens = sum(1 for w in words if re.search(r"[a-z][379]|[379][a-z]", w))
    derja_hits = sum(1 for w in words if w in _DERJA_LATIN and len(w) > 2) + 2 * arabizi_tokens
    en_hits = sum(1 for w in words if w in _EN)
    fr_hits = sum(1 for w in words if w in _FR)
    if re.search(r"[éèêàçùâîôû]", text.lower()):
        fr_hits += 2
    if derja_hits >= 2 and derja_hits >= max(en_hits, fr_hits):
        return "derja"
    if en_hits > fr_hits:
        return "en"
    return "fr"
