"""RNE registration: legal form -> official "Immatriculation principale" rows of the RNE formalities table.

The codes below are the creation rows of the official table (data/raw/rne-formalities-procedure-table), identified by
their "Type d entreprise" column. A registration, fee or deadline question is only answered once the legal form is
known; otherwise the assistant asks for it (the fee and the deadline depend on the form). Deterministic, no LLM.
"""
import re

# (key, pattern on the normalized message, official table codes). Order matters: specific forms first.
LEGAL_FORMS: list[tuple[str, str, tuple[str, ...]]] = [
    ("trader", r"commer[çc]ant|\btrader\b|merchant|تاجر|\btajer\b|\btejer\b", ("RNE C 001",)),
    ("artisan", r"artisan|craftsman|حرفي|\b7orfi\b|\bharfi\b", ("RNE C 002",)),
    ("liberal_profession", r"profession(?:nel)?s? lib[ée]rale?s?|m[ée]tier lib[ée]ral|liberal profession|مهنة حر",
     ("RNE C 003",)),
    ("sarl_family", r"\bs\.?a\.?r\.?l\b|\bsuarl\b|responsabilit[ée] limit[ée]e|ذات مسؤولية محدودة|ذات الشخص الواحد|\bllc\b"
                    r"|nom collectif|commandite|soci[ée]t[ée] civile(?! professionnelle)", ("RNE C 012",)),
    ("sa", r"soci[ée]t[ée] anonyme|خفية الاسم|public limited|joint[- ]stock", ("RNE C 004",)),
    ("gie", r"groupement d.int[ée]r[êe]t [ée]conomique|\bgie\b", ("RNE C 005",)),
    ("foreign_branch", r"succursale|branch of a foreign|فرع شركة أجنبية", ("RNE C 007",)),
    ("foreign_association", r"(?:association|جمعية).{0,30}(?:[ée]trang[eè]re|foreign|أجنبية)|filiale d.une association",
     ("RNE C 011.1", "RNE C 011.2")),
    ("association_network", r"r[ée]seau d.associations|network of associations|شبكة جمعيات", ("RNE C 009",)),
    ("association", r"association|جمعية|\bjam3ia\b|\bjem3ia\b", ("RNE C 010.1", "RNE C 010.2")),
    ("cooperative", r"coop[ée]rative|تعاضدية|تعاونية", ("RNE C 025",)),
    ("natural_person", r"personne physique|natural person|شخص طبيعي|sole proprietor|entreprise individuelle",
     ("RNE C 001", "RNE C 002", "RNE C 003")),
]
# "SA" is only recognised in capitals in the original message ("sa société" is a French possessive).
SA_ACRONYM = re.compile(r"(?<![A-Za-z])S\.?A\.?(?![A-Za-z])")
REGISTRATION = (r"immatricul|enregistr|cr[ée]er|cr[ée]ation|constitu|fonder|register|registration|incorporat|"
                r"start (?:a|my) (?:company|business)|open (?:a|my) (?:company|business)|set up|تسجيل|تأسيس|بعث|"
                r"\bn?[7h]el\b|na3mel (?:chirka|société|sarl|suarl)|نعمل شركة|نحل شركة")
COMPANY = r"entreprise|soci[ée]t[ée]|\bcompany\b|\bbusiness\b|شركة|مؤسسة|\bchirka\b|\bcharika\b|\bsharika\b|\bsharka\b"
OTHER_PROCEDURES = r"modif|radiation|cessation|transfert|dissolution|liquidation|تنقيح|تشطيب|حل الشركة|تصفية"

QUESTION = {
    "en": "To point you to the right registration procedure, which legal form is it: natural person (trader, artisan or "
          "liberal profession), SARL / SUARL (or another partnership), société anonyme, association, or another form "
          "(GIE, cooperative, branch of a foreign company…)?",
    "fr": "Pour vous indiquer la bonne procédure d'immatriculation, précisez la forme juridique : personne physique "
          "(commerçant, artisan ou profession libérale), SARL / SUARL (ou autre société de personnes), société anonyme, "
          "association, ou autre forme (GIE, coopérative, succursale d'une société étrangère…) ?",
    "ar": "لتحديد إجراء التسجيل المناسب، ما هو الشكل القانوني: شخص طبيعي (تاجر أو حرفي أو مهنة حرة)، شركة ذات مسؤولية "
          "محدودة (SARL / SUARL أو شركة أشخاص أخرى)، شركة خفية الاسم، جمعية، أو شكل آخر (مجمع ذو مصلحة اقتصادية، تعاضدية، "
          "فرع شركة أجنبية…)؟",
    "derja": "باش نعطيك الإجراء الصحيح متاع التسجيل، قلّي شنوة الشكل القانوني: شخص طبيعي (تاجر، حرفي ولا مهنة حرة)، "
             "SARL / SUARL (ولا شركة أشخاص أخرى)، شركة خفية الاسم، جمعية، ولا شكل آخر (GIE، تعاضدية، فرع شركة أجنبية…)؟",
}


def detect_legal_form(text: str) -> str | None:
    q = text.lower()
    for key, pattern, _ in LEGAL_FORMS:
        if re.search(pattern, q):
            return key
    return "sa" if SA_ACRONYM.search(text) else None


def codes_for(key: str) -> tuple[str, ...]:
    return next(codes for k, _, codes in LEGAL_FORMS if k == key)


def is_registration_question(text: str, intent: str | None) -> bool:
    """A question whose answer depends on the legal form: registering/creating, or fees, deadlines, documents of
    registration. Other RNE procedures (modification, radiation…) and legal-text questions are not included."""
    q = text.lower()
    if re.search(OTHER_PROCEDURES, q):
        return False
    return bool(re.search(REGISTRATION, q)) or intent in {"fees", "processing_time", "required_documents"}
