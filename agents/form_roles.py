"""Who fills each field of an official form template, read from the printed form itself.

Roles:
  required        the applicant fills it in (default for every derived field)
  optional        the applicant may leave it empty (e.g. an unlabelled continuation line)
  conditional     only applies to some applicants (e.g. spouse fields); reported as "if applicable"
  administration  filled by the administration; never reported as missing

Two sources, both deterministic:
  1. Generic: every field printed after an administration heading ("خاص بالإدارة",
     "réservé à l'administration") is administration-only, on that page and on the following pages.
  2. Per template: printed labels and roles for the fields of one exact official file (pinned by its
     sha256). An override is applied only if the field derived by `template_fields` still has the
     expected label; otherwise that template falls back to the generic rule.
"""
from __future__ import annotations

import dataclasses
import logging
import re

log = logging.getLogger(__name__)

ROLES = ("required", "optional", "conditional", "administration")

# Administration headings, normalised (agents.form_helper.norm_token) and without spaces: a tatweel
# can split a printed word into several extracted words ("خــاص" -> "خ", "ــ", "اص").
ADMIN_HEADINGS = ("خاصبالاداره", "خاصهبالاداره", "réservéàl'administration")


@dataclasses.dataclass(frozen=True)
class FieldRule:
    derived: str  # label produced by template_fields (guard)
    label: str  # label as printed on the form, shown to the user
    role: str = "required"


@dataclasses.dataclass(frozen=True)
class TemplateRules:
    sha256: str
    fields: dict[int, FieldRule]
    # Printed items the dot-leader check cannot see (boxes, check boxes, signature), quoted as printed.
    unchecked: tuple[str, ...] = ()


C, O, A = "conditional", "optional", "administration"

TEMPLATE_RULES: dict[str, TemplateRules] = {
    "rne-form-f001-natural-person-registration": TemplateRules(
        sha256="dbfa1f815312620a99519e84ff854d751f8784b970861082df686bf911296172",
        fields={},
        unchecked=("إمضاء المصرّ ح أو من ينوبه بتوكيل", "Type de Pièce d’identité / نوع بطاقة الهوية",
                   "Métier Libéral - مهنة حرّ ة Artisan - حرفيCommerçant -تاجر", "IDENTIFIANT UNIQUE -المعرّف الوحيد"),
    ),
    "rne-form-f002-legal-entity-registration": TemplateRules(
        sha256="f68cfaa0a715fd213c4e3a97b32a270d513eabcac2e868f98531d401a73ff06c",
        fields={},
        unchecked=("إمضاء الممثل القانوني أو من ينوبه بتوكيل", "Type de Pièce d’identité / نوع بطاقة الهوية",
                   "RIB -المعرف البنكي", "IDENTIFIANT UNIQUE -المعرّف الوحيد"),
    ),
    # مطلب بطاقة التعريف الوطنية (IL.01-12/2013). Applicant part: y 192-450 of page 1; "بيانـات خاصة
    # بالإدارة" starts at y 475 and page 2 is administration only.
    "interior-national-id-application-form": TemplateRules(
        sha256="1ccece129f681dc936c65ea22921bc83e69760d2607d58a71fb6bb9731d2fe63",
        fields={
            0: FieldRule("اللقب الجنس", "اللقب"),
            1: FieldRule("الإسم", "الإسم"),
            2: FieldRule("إسم الأب إسم الجد", "إسم الأب"),
            3: FieldRule("إسم الجد", "إسم الجد"),
            4: FieldRule("مكانها الحالة العائلية", "تاريخ الولادة — مكانها"),
            5: FieldRule("إسم الأم لقبها", "إسم الأم"),
            6: FieldRule("لقبها", "إسم الأم — لقبها"),
            7: FieldRule("إسم الزوج )ة( لقبه (ها )", "إسم الزوج(ة)", C),
            8: FieldRule("لقبه (ها )", "إسم الزوج(ة) — لقبه(ها)", C),
            9: FieldRule("المهنة", "المهنة"),
            10: FieldRule("عنوان السكنى الفصيلة الدموية", "عنوان السكنى"),
            11: FieldRule("الولاية", "عنوان السكنى (2)", O),  # unlabelled second address line
            12: FieldRule("الولاية", "الولاية"),
            13: FieldRule("الهوية القديمة", "الهوية القديمة", C),  # no previous card on a first application
        },
        unchecked=("تاريخ الولادة", "الجنس", "الحالة العائلية", "الفصيلة الدموية", "متبرع", "التوقيع"),
    ),
    # مطلب جواز سفر عادي (IL.02-12/2013). Applicant part: y 220-640 of page 1; "خــاص بالإدارة" starts
    # at y 662 (followed by the deposit receipt) and page 2 is administration only.
    "interior-passport-application-form": TemplateRules(
        sha256="7e667ead43869ad17d8a9ac5b881dd3bf27afce9e8d3cdae5a5e8341d598168d",
        fields={
            0: FieldRule("الإسم", "Prénom / الإسم"),
            1: FieldRule("إسم الأب", "Prénom du père / إسم الأب"),
            2: FieldRule("إسم الجد", "Prénom du grand-père / إسم الجد"),
            3: FieldRule("اللقب العائلي", "Nom de famille ou de jeune fille / اللقب العائلي"),
            4: FieldRule("إسم الأم ولقبها", "Nom et prénom de la mère / إسم الأم ولقبها"),
            5: FieldRule("مكان الولادة ولايتها تاريخ الولادة", "مكان الولادة — ولايتها"),
            6: FieldRule("Profession / المهنة", "Profession / المهنة"),
            7: FieldRule("إسم الزوج (ة)", "Prénom de l’Epoux(se) / إسم الزوج(ة)", C),
            8: FieldRule("لقب الزوج )ة(", "Nom de l’Epoux(se) / لقب الزوج(ة)", C),
            9: FieldRule("Nationalité de l’Epoux(se) / جنسيــة الزوج (ة)", "Nationalité de l’Epoux(se) / جنسية الزوج(ة)", C),
            10: FieldRule("حرر بـ فـي", "حرر بـ … في"),
            15: FieldRule("القامـــــة", "القامة"),
            16: FieldRule("لون العينين", "لون العينين"),
            17: FieldRule("جنسيـــات أخرى", "جنسيات أخرى", C),  # only applicants holding other nationalities
        },
        unchecked=("N° de la Carte d’Identité Nationale / رقم بطاقة التعريف الوطنية", "تاريخ الولادة", "الجنس",
                   "Adresse / العنوان", "الحالة العائلية", "التوقيع"),
    ),
}


def admin_start(words, norm) -> tuple[int, float] | None:
    """(page, y) of the first administration heading printed on the form, if any."""
    lines: dict[tuple, list] = {}
    for w in words:
        lines.setdefault(w.line, []).append(w)
    for key in sorted(lines, key=lambda k: (k[0], min(w.y0 for w in lines[k]))):
        ltr = [norm(w.text) for w in sorted(lines[key], key=lambda w: w.x0)]
        compact = ("".join(ltr), "".join(reversed(ltr)))  # Latin and Arabic reading order
        if any(h in c for h in ADMIN_HEADINGS for c in compact):
            ws = lines[key]
            return ws[0].page, min(w.y0 for w in ws)
    return None


def assign(doc_id: str, sha256: str | None, fields: list, words: list, norm) -> tuple[list, tuple[str, ...]]:
    """Returns (fields with role and printed label, printed items the check cannot see)."""
    start = admin_start(words, norm)
    out = []
    for f in fields:
        if start and (f.page, f.region[1]) >= (start[0], start[1] - 1):
            f = dataclasses.replace(f, role="administration")
        out.append(f)
    rules = TEMPLATE_RULES.get(doc_id)
    if rules is None or rules.sha256 != sha256:
        return out, ()
    if any(i >= len(out) or re.sub(r"\s+", " ", out[i].label) != r.derived for i, r in rules.fields.items()):
        log.warning("form_rules_mismatch", extra={"fields": {"doc_id": doc_id}})
        return out, ()
    for i, r in rules.fields.items():
        if out[i].role != "administration":
            out[i] = dataclasses.replace(out[i], label=r.label, role=r.role)
    return out, rules.unchecked
