"""Conservative legal replies: source selection and unabridged, located quotations.

No legal rules or answer values are encoded here. Article bodies are read from the
unchanged official extraction. A quotation is not a finding of legal applicability.
"""
import math
import re

from agents import i18n
from agents.corpus import norm
from agents.schemas import AnswerResult


SUBJECTS = {
    'rne-arrete-2026-35': (r'2026[- /]35|13 janvier 2026|(?:acc[eè]s|access|obten|consult|authorit|autorit|publi[qc]|information|نفاذ|اطلاع).{0,100}(?:b[eé]n[eé]ficiaire|beneficial|المستفيد)|(?:b[eé]n[eé]ficiaire|beneficial|المستفيد).{0,100}(?:acc[eè]s|access|information|publi[qc]|معلومات)', 'accès informations bénéficiaire effectif arrêté 13 janvier 2026'),
    'rne-law-2018-52-ar': (r'2018[- /]52|52.{0,12}2018', 'loi 2018-52 السجل الوطني للمؤسسات'),
    'rne-decree-law-2022-18-fr': (r'2022[- /]18|remise.{0,30}p[eé]nalit', 'décret-loi 2022-18 remise pénalités'),
    'rne-decree-2022-298-fees-fr': (r'2022[- /]298|298.{0,12}2022|redevance.{0,60}tableau|tableau.{0,60}redevance', 'décret 2022-298 redevances'),
    'rne-decree-name-reservation': (r'r[eé]servation|name reservation|trade name|company.name|حجز.{0,20}(?:تسمية|اسم|شارة)|2019[- /]53|\b(?:7ajz|hajz)\b.{0,25}(?:esm|ism|tasmi|chara)', 'réservation dénomination sociale nom commercial حجز التسمية'),
    'rne-decree-beneficial-owners': (r'b[eé]n[eé]ficiaire.{0,10}effectif|beneficial.owner|المستفيد الحقيقي|المستفيدون الحقيقيون|مستفيد(?:ا|ون|ين)?\s+حقيقي(?:ا|ون|ين)?|(?:mou?stafid|mustafid)\w*\s+(?:7a9i9i|ha9i9i|haqiqi|hakiki)|2019[- /]54|54.{0,12}2019', 'bénéficiaire effectif المستفيد الحقيقي'),
}
NOTICE = {
    'en': 'Official source excerpts in their original language. These are selected provisions, not an exhaustive legal opinion. No conclusion beyond the quoted text is verified; current applicability and your individual case require confirmation.',
    'fr': 'Extraits officiels dans leur langue originale. Il s’agit de dispositions sélectionnées, pas d’un avis juridique exhaustif. Aucune conclusion au-delà du texte cité n’est vérifiée ; confirmez son applicabilité actuelle et votre cas particulier.',
    'ar': 'مقتطفات رسمية بلغتها الأصلية. هذه أحكام مختارة وليست رأيا قانونيا شاملا. لا نثبت استنتاجا خارج النص المقتبس؛ يلزم التأكد من سريانه الحالي ومن انطباقه على حالتك.',
    'derja': 'هاذم مقتطفات رسمية بلغتها الأصلية، موش رأي قانوني شامل. ما نثبتوش استنتاج خارج النص؛ ثبّت في سريانو توّا وفي انطباقو على حالتك عند الإدارة.',
}
CLARIFY = {
    'en': 'Which exact procedure, service or legal provision do you mean? Please describe the situation without personal identifiers; I cannot infer that this text applies to your case.',
    'fr': 'De quelle procédure, prestation ou disposition précise parles-tu ? Décris la situation sans identifiants personnels ; je ne peux pas déduire que ce texte s’applique à ton cas.',
    'ar': 'ما الإجراء أو الخدمة أو الحكم القانوني المقصود بالتحديد؟ صف الحالة دون معرفات شخصية؛ لا يمكنني افتراض انطباق هذا النص على حالتك.',
    'derja': 'على أي إجراء ولا خدمة ولا فصل بالضبط تحكي؟ فسّر الحالة من غير معطيات شخصية؛ ما نجمش نفترض النص هذا ينطبق على حالتك.',
}
ARTICLE = re.compile(r'(?:^|\s)(?:Art\.\s*(\d+)\s*[-–]|Article\s+(premier)\s*[-–]|ال\s*فص\s*ل\s*(الأو(?:\s*ل)?|الاول|\d+)\s*(?:[-–ـ]|(?=\S)))', re.I)
HEADING = re.compile(r'^(?:Art\.\s*(\d+)|Article\s+(premier)|الفصل\s*(الأول|الاول|\d+))\s*$', re.I)
# Penalties for the register are set by Law 2018-52; checked after the decree-law on the *remission* of
# late penalties, so "remise des pénalités" keeps pointing to Decree-law 2022-18.
REGISTER = r'RNE|registre|register|السجل الوطني|سجل المؤسسات'
PENALTY = r'penalt|sanction|punish|\bfines?\b|amende|p[ée]nalit|emprisonn|prison|عقوب|يعاقب|خطية|السجن|غرامة|\b(?:khtiya|5tiya|ghrama)\b'
# Lateness: Law 2018-52 art. 51 sets the late penalty ("غرامة تأخير" after the legal deadlines); the criminal
# sanctions of arts. 53-57 must not outrank it for a question that is explicitly about being late.
LATE = r'\blate\b|retard|tardi|after the deadline|past the deadline|d[ée]lai d[ée]pass|تأخير|التأخير|بعد الآجال|\b(?:nfout|fat|fet) el ajal\b'
LAW_THEMES = (rf'(?:{PENALTY}).{{0,80}}(?:{REGISTER})|(?:{REGISTER}).{{0,80}}(?:{PENALTY})'
              r'|false declaration|fausse d[ée]claration|d[ée]claration (?:fausse|mensong[eè]re)|تصريح مخالف للحقيقة|بيان كاذب')
# Cross-lingual search vocabulary for locating the relevant article of an act written in another language.
# These are search terms only (no legal content): a concept found in the question adds the equivalent
# wording used in the official texts to the article scoring.
CONCEPTS = [
    (rf'^(?![\s\S]*(?:{LATE}))[\s\S]*(?:{PENALTY})', ['يعاقب', 'بخطية', 'بالسجن', 'عقوبة', 'amende', 'emprisonnement']),
    (LATE, ['غرامة تأخير', 'الآجال القانونية', 'retard']),
    (r'false|fausse|faux|mensong|inexact|untrue|كاذب|مخالف للحقيقة', ['مخالف للحقيقة', 'كاذب', 'fausse']),
    (r'd[ée]clar|statement|تصريح', ['تصريح', 'déclaration']),
    (r'deadline|time limit|d[ée]lai|within|أجل|آجال|ظرف', ['أجل', 'آجال', 'ظرف', 'délai']),
    (r'registration|register|immatricul|inscri|تسجيل|ترسيم', ['تسجيل', 'immatriculation']),
    (r'trader|merchant|commer[çc]ant|تاجر', ['التاجر', 'commerçant']),
    (r'presum|pr[ée]somption|قرينة', ['قرينة', 'présomption']),
    (r'deregist|radiation|شطب', ['التشطيب', 'radiation']),
    (r'access|acc[eè]s|consult|نفاذ|اطلاع', ['النفاذ', 'اطلاع', 'accès']),
    (r'exchange|[ée]change|interop|تبادل|تشبيك', ['التبادل', 'تشبيك', 'interopérabilité']),
    (r'payment|paiement|pay|recouvr|خلاص|استخلاص', ['paiement', 'recouvrées', 'خلاص']),
    (r'reduc|r[ée]duit|discount|تخفيض', ['réduites', 'تخفيض']),
    (r'refund|rembours|استرجاع', ['remboursé', 'remboursés', 'استرجاع']),
    (r'tax|taxes|ttc|أداء', ['taxes', 'أداءات']),
    (r'repeal|abrog|إلغاء', ['abrogées', 'تلغى']),
    (r'beneficial owner|b[ée]n[ée]ficiaire effectif|المستفيد', ['المستفيد الحقيقي', 'bénéficiaire effectif']),
    (r'confidential|confidenti|سرية', ['سرية', 'confidentialité']),
    # Printed instructions of the official forms (French or English questions about Arabic text).
    (r'langue|language|لغة', ['اللغة العربية', 'langue']),
    (r'manquant|missing|incompl|ناقص', ['ناقص', 'كاملة']),
    (r'contraire|contrary|r[ée]alit|reality|false|fausse|mensong|للواقع', ['مخالفة للواقع']),
    (r'joint|attach|pi[eè]ces|documents? requis|required documents?|الوثائق', ['الوثائق المطلوبة', 'تنقصه']),
    (r'e-?mail|courriel|gsm|mobile|t[ée]l[ée]phone|phone|البريد|الهاتف', ['البريد الالكتروني', 'الهاتف الجوال']),
    (r'rejet|reject|refus|رفض', ['لرفض', 'لاغيا']),
]
FORMS = {
    'rne-form-f001-natural-person-registration': r'F[\s_-]*0*01(?!\d)|personne[\s_]+physique|natural person|شخص طبيعي',
    'rne-form-f002-legal-entity-registration': r'F[\s_-]*0*02(?!\d)|personne[\s_]+mo[rt]ale|legal entity|شخص معنوي',
}
FORM_REFERENCE = r'formulaire|imprim[ée]|\bform\b|مطبوعة|استمارة|RNE[\s_-]*F[\s_-]*0*0[12]|\bF[\s_-]*0*0[12]\b'
FORM_CONTENT_QUESTION = r'que dit|quelle|quel|selon|what|which|says?|according|ماذا|ما\b|هل|\?|؟|^\s*(?:et|and|w|و)\b|contien|contenu|contain'
# A generic question about what the form contains (answered with the printed overview of the form).
FORM_GENERIC = (r'contien|contenu|contain|content|what(?:\'s| is) (?:in|on)|qu.y a|champs|fields|sections|rubriques|'
                r'خانات|محتوى|يحتوي|تحتوي|تتضمن|شنوة فيه|شنوة فيها|\bfih\b|\bfiha\b|^\s*(?:et|and|w|و)\b')
# Download / link of an official form.
FORM_DOWNLOAD = (r'(?=.*(?:t[ée]l[ée]charg|telecharg|download|تحميل|نحمل|نحمّل|\bnhabet\b|\bn7abet\b|\blien\b|\blink\b|'
                 r'رابط|\burl\b))(?=.*(?:formulaire|imprim[ée]|\bform\b|استمارة|إستمارة|مطبوعة|\bF[\s_-]*0*0[12]\b))')
TABLE = re.compile(r'(?:tableau|table|جدول)\s*(?:n\s*°|no\.?|number|رقم|عدد)?\s*(\d+)', re.I)
TABLE_TOPICS = r'r[ée]duc|reduc|discount|تخفيض|rembours|refund|استرجاع|paiement|payment|modalit|recouvr|ttc|\btaxes?\b|abrog|repeal'
# Words that identify an act or a question form rather than the requested provision.
GENERIC = set('''que quoi quel quelle quels quelles prévoit prevoit dit dire selon pour dans avec sont sur
what which does say says provide provides according about under with from that this text official
ماذا ينص يتعلق حسب الذي التي هذا هذه
décret decret présidentiel presidentiel arrêté arrete loi décret-loi law decree order article articles
rne registre entreprises national tunisie tunisian'''.split())


def identify_subject(text):
    # Explicit act identifiers override thematic matches and previous context.
    for pattern, doc in [(r'2026[- /]35|13 janvier 2026', 'rne-arrete-2026-35'),
                         (r'2018[- /]52|52.{0,12}2018', 'rne-law-2018-52-ar'),
                         (r'2022[- /]18', 'rne-decree-law-2022-18-fr'),
                         (r'2022[- /]298|298.{0,12}2022', 'rne-decree-2022-298-fees-fr'),
                         (r'2019[- /]53', 'rne-decree-name-reservation'),
                         (r'2019[- /]54|54.{0,12}2019', 'rne-decree-beneficial-owners')]:
        if re.search(pattern, text, re.I):
            return doc
    thematic = next((doc for doc, (pattern, _) in SUBJECTS.items() if re.search(pattern, text, re.I)), None)
    if thematic in {None, 'rne-law-2018-52-ar'} and re.search(LAW_THEMES, text, re.I):
        return 'rne-law-2018-52-ar'
    return thematic


def subject_query(doc):
    return SUBJECTS[doc][1]


def _number(match):
    value = next(x for x in match.groups() if x is not None)
    return 1 if not value.isdigit() else int(value)


def articles(blocks):
    """Locate body starts, skipping heading duplicates and preceding/following acts."""
    result, current, started = [], None, False
    for block in blocks:
        text = block['text']
        if HEADING.fullmatch(text.strip()):
            continue
        if current and re.match(r'^(?:MINISTERE |Par (?:arrêté|décret)|بمقتضى أمر|أمر حكومي عدد)', text):
            break
        matches = [m for m in ARTICLE.finditer(text) if m.group(3) is None or text[:m.start()].strip() in {'', 'ل'}
                   # A new Arabic article may also start mid-block after a full stop, but only as the next number
                   # in sequence; this excludes cross-references such as "من الفصل27".
                   or (current and text[:m.start()].rstrip().endswith(('.', ':', '؛'))
                       and m.group(3).isdigit() and int(m.group(3)) == current['number'] + 1)]
        if matches:
            for pos, match in enumerate(matches):
                number = _number(match)
                if number == 1:
                    if started:
                        if current:
                            result.append(current)
                        return result
                    started = True
                if not started:
                    continue
                if current:
                    # Text before a mid-block article start ends the previous article.
                    head = text[:match.start()].strip() if pos == 0 else ''
                    if head not in {'', 'ل'}:
                        current['parts'].append(head)
                    result.append(current)
                stop = matches[pos + 1].start() if pos + 1 < len(matches) else len(text)
                current = {'number': number, 'page': block.get('page'), 'parts': [text[match.start():stop].strip()]}
        elif current:
            # Adjacent gazette acts are not part of the selected article.
            if re.match(r'^(?:MINISTERE |Par (?:arrêté|décret)|بمقتضى أمر|أمر حكومي عدد)', text):
                break
            if 'Journal Officiel' not in text:
                current['parts'].append(text)
    if current:
        result.append(current)
    return result


def requested_article(text):
    """Explicit article number in the question ("article 5", "art. 5", "الفصل 5"), else None."""
    match = re.search(r'(?:\barticle|\bart\.?|الفصل)\s*(\d+)\b', text, re.I)
    return int(match[1]) if match else None


def table_section(sections, number):
    """The printed table n°N, cut from the article that contains it (tables are not articles)."""
    for section in sections:
        body = '\n'.join(section['parts'])
        start = re.search(rf'Tableau\s*n\s*°\s*{number}\b', body, re.I)
        if start:
            nxt = re.search(r'Tableau\s*n\s*°\s*\d+', body[start.end():], re.I)
            end = start.end() + nxt.start() if nxt else len(body)
            return [{**section, 'parts': [body[start.start():end].strip()], 'table': number}]
    return []


def rank_sections(query, sections, subject, passages=()):
    """Select up to three articles by IDF-weighted evidence for the informative words of the question.

    Words naming the act itself (number, type, title) are ignored: they occur in signatures and repeal
    clauses and previously pulled those articles to the top. A question with no informative word left
    ("what does decree X provide?") receives the act's first, main provision.
    """
    texts = [norm(' '.join(s['parts'])) for s in sections]
    title = norm(subject_query(subject))
    words = {w for w in re.findall(r'\w+', norm(query)) if len(w) > 3 and not w.isdigit()
             and w not in GENERIC and w not in title}
    for pattern, expansion in CONCEPTS:
        if re.search(pattern, query, re.I):
            words |= {norm(e) for e in expansion}
    n = len(sections)
    idf = {w: math.log((n + 1) / (1 + sum(w in t for t in texts))) for w in words}
    scores = []
    for s, text in zip(sections, texts):
        score = sum(idf[w] for w in words if w in text)
        # Retrieved passages of the same act only break ties between articles that already have evidence
        # for the question; they must not turn an unrelated article into a candidate.
        if score > 0:
            score += sum(0.5 for p in passages if p.citation.doc_id == subject
                         and any(norm(part) in norm(p.text) for part in s['parts'] if len(part) > 45))
        scores.append(score)
    best = max(scores, default=0)
    if best <= 0:
        return [s for s in sections if s['number'] == 1][:1] or sections[:1]
    ranked = sorted(zip(scores, range(n)), key=lambda x: (-x[0], x[1]))
    return [sections[i] for sc, i in ranked[:3] if sc >= 0.5 * best]


def identify_form(text):
    """An official RNE form named in a question about its printed content, else None."""
    if not re.search(FORM_REFERENCE, text, re.I) or not re.search(FORM_CONTENT_QUESTION, text, re.I):
        return None
    return next((doc for doc, pattern in FORMS.items() if re.search(pattern, text, re.I)), None)


_FORM_NOISE = re.compile(r'@|www\.|\+216|نهج|\brue\b|^\s*\d+\s*/\s*\d+\s*$|عدد الصفحات|نسخة|:\s*مرجع|^تص\w*ح بتسجيل', re.I)
_FIELD_LABEL = re.compile(r'^(.*?)\s*:\s*[.\s/]{4,}')


def form_overview(req, corpus, form, specific=False):
    """Printed content of an official form, quoted verbatim: title lines, the labels of the fields to fill in and the
    printed instructions/options. The extraction is the complete one-page official form."""
    from agents.checklist_builder import sources_footer
    blocks = corpus.blocks(form)
    citation = corpus.citation(form)
    if not blocks or not citation:
        return None
    lang = req.route.language
    titles = [b['text'] for b in blocks if re.search(r'DÉCLARATION|RNE F 00', b['text'])]
    labels = []
    for b in blocks:
        m = _FIELD_LABEL.match(b['text'])
        if '....' in b['text'] and m and m.group(1).strip() and m.group(1).strip() not in labels:
            labels.append(m.group(1).strip())
    printed = [b['text'] for b in blocks if '....' not in b['text'] and b['text'] not in titles
               and len(b['text']) >= 20 and not _FORM_NOISE.search(b['text'])]
    lines = [i18n.t('form_section_unavailable', lang)] if specific else []
    lines += [i18n.t('form_overview', lang), *[f'• {t}' for t in titles],
              '', f"{i18n.t('form_fields', lang)}:", *[f'• {label}' for label in labels],
              '', f"{i18n.t('form_printed_text', lang)}:", *[f'• {t}' for t in printed]]
    return AnswerResult(text='\n'.join(lines + sources_footer(lang, [citation])), found=True,
                        method='passages_fallback', citations=[citation],
                        verification={'legal': {'method': 'verbatim_form_overview', 'articles': [],
                                                'semantic_conclusion_verified': False}})


def download_reply(req, corpus):
    """Download link of an official form, only from the verified corpus manifest (a record with a stored file);
    otherwise state that no verified link is available. Never a guessed URL."""
    if not re.search(FORM_DOWNLOAD, req.query.lower()):
        return None
    from agents.checklist_builder import sources_footer
    lang, category = req.route.language, req.route.procedure_category
    forms = [r for r in corpus.records().values() if r.document_type.value == 'official_form']
    named = [r for r in forms if r.doc_id in FORMS and re.search(FORMS[r.doc_id], req.query, re.I)]
    wanted = named or [r for r in forms if r.procedure_category.value == category]
    if not wanted:
        return AnswerResult(text=i18n.t('form_download_none', lang), found=False, method='none')
    lines, cites = [], []
    for rec in sorted(wanted, key=lambda r: r.doc_id):
        if rec.file_path:
            lines.append(f"{i18n.t('form_download_available', lang)}: {rec.title}\n{rec.url}")
            c = corpus.citation(rec.doc_id)
            if c:
                cites.append(c)
        else:
            lines.append(i18n.t('form_download_unavailable', lang))
    return AnswerResult(text='\n\n'.join(lines) + ('\n' + '\n'.join(sources_footer(lang, cites)) if cites else ''),
                        found=bool(cites), method='passages_fallback' if cites else 'none', citations=cites)


def form_reply(req, corpus, form):
    """Quote the printed instruction block(s) of an official form that answer the question (no generation).

    Blank fields (dot leaders) and headers are excluded; blocks are ranked like articles. No block with
    evidence for the question -> insufficient evidence, never a guess."""
    blocks = [b for b in corpus.blocks(form) if '....' not in b['text'] and len(b['text']) > 60]
    if not blocks:
        return None
    sections = [{'number': i + 1, 'page': b.get('page'), 'parts': [b['text']]} for i, b in enumerate(blocks)]
    texts = [norm(b['text']) for b in blocks]
    words = set()
    for pattern, expansion in CONCEPTS:
        if re.search(pattern, req.query, re.I):
            words |= {norm(e) for e in expansion}
    scores = [sum(w in t for w in words) for t in texts]
    if not words or max(scores) == 0:
        # Nothing printed on the form matches a specific question: give the form's printed overview (verbatim),
        # stating the limitation when the question was specific. Never a guess.
        specific = bool(words) or not re.search(FORM_GENERIC, req.query, re.I)
        return form_overview(req, corpus, form, specific=specific) or AnswerResult(
            text=i18n.t('insufficient_evidence', req.route.language), found=False, method='none')
    best = max(scores)
    selected = [s for s, sc in zip(sections, scores) if sc == best][:2]
    from agents.checklist_builder import sources_footer
    citation = corpus.citation(form, page=selected[0]['page'])
    if not citation:
        return None
    lines = [NOTICE[req.route.language]]
    for section in selected:
        lines += ['', f"[1] (p. {section['page']})", section['parts'][0]]
    return AnswerResult(text='\n'.join(lines + sources_footer(req.route.language, [citation])), found=True,
                        method='passages_fallback', citations=[citation],
                        verification={'legal': {'method': 'verbatim_form_instructions', 'articles': [],
                                                'semantic_conclusion_verified': False}})


LANG_NAME = {'fr': {'ar': 'arabe', 'fr': 'français'}, 'en': {'ar': 'Arabic', 'fr': 'French'},
             'ar': {'ar': 'العربية', 'fr': 'الفرنسية'}, 'derja': {'ar': 'العربية', 'fr': 'الفرنسية'}}
HEADER = {
    'fr': "Source : {act} — {arts}. Le texte officiel est en {lang} et il est cité tel quel ; aucune traduction "
          "officielle n'est fournie.",
    'en': "Source: {act} — {arts}. The official text is in {lang} and is quoted as is; no official translation is "
          "provided.",
    'ar': "المصدر: {act} — {arts}. النص الرسمي باللغة {lang} ويُنقل كما هو دون ترجمة رسمية.",
    'derja': "المصدر: {act} — {arts}. النص الرسمي باللغة {lang} ونقلوه كيما هو، من غير ترجمة رسمية.",
}
ART_WORD = {'fr': ('article', 'articles'), 'en': ('article', 'articles'), 'ar': ('الفصل', 'الفصول'), 'derja': ('الفصل', 'الفصول')}
TABLE_WORD = {'fr': 'tableau n°{n}', 'en': 'table no. {n}', 'ar': 'الجدول عدد {n}', 'derja': 'الجدول عدد {n}'}
KEY_LABEL = {'fr': 'Passage le plus pertinent (formulation officielle) :', 'en': 'Most relevant passage (official wording):',
             'ar': 'المقطع الأكثر صلة (الصياغة الرسمية):', 'derja': 'المقطع الأقرب لسؤالك (الصياغة الرسمية):'}
FULL_LABEL = {'fr': 'Texte officiel :', 'en': 'Official text:', 'ar': 'النص الرسمي:', 'derja': 'النص الرسمي:'}
MORE_LABEL = {'fr': 'Autres articles du même texte, disponibles sur demande (« article N ») : {arts}',
              'en': 'Other articles of the same text, available on request ("article N"): {arts}',
              'ar': 'فصول أخرى من نفس النص متاحة عند الطلب («الفصل N»): {arts}',
              'derja': 'فصول أخرى من نفس النص، اطلبها («الفصل N»): {arts}'}
FULL_TEXT_BUDGET = 2600  # characters of complete articles shown before the remaining ones are listed by number


def _question_words(query, title=''):
    words = {w for w in re.findall(r'\w+', norm(query)) if len(w) > 3 and not w.isdigit()
             and w not in GENERIC and w not in title}
    for pattern, expansion in CONCEPTS:
        if re.search(pattern, query, re.I):
            words |= {norm(e) for e in expansion}
    return words


def key_passage(query, sections, title='', limit=420):
    """The official sentence that shares most informative words with the question (verbatim, or None)."""
    words = _question_words(query, title)
    if not words:
        return None
    best, best_score = None, 0
    for s in sections:
        for sentence in re.split(r'(?<=[.;؛:])\s+|\n', '\n'.join(s['parts'])):
            sentence = sentence.strip()
            if len(sentence) < 25:
                continue
            score = sum(w in norm(sentence) for w in words)
            if score > best_score:
                best, best_score = sentence, score
    if best is None:
        return None
    return best if len(best) <= limit else best[:limit].rsplit(' ', 1)[0] + ' …'


def render_legal(req, corpus, subject, selected, citation, budget=True):
    """Header in the user's language, the most relevant official sentence, then the complete official text.

    Nothing is translated or paraphrased: the explanation names the act, the article(s) and the language of the
    official text; every legal statement shown is a verbatim quotation."""
    from agents.checklist_builder import sources_footer
    lang = req.route.language
    act = citation.official_reference or citation.title
    one, many = ART_WORD[lang]
    shown, used = [], 0
    for section in selected:
        size = len('\n'.join(section['parts']))
        if budget and shown and used + size > FULL_TEXT_BUDGET:
            continue
        shown.append(section)
        used += size
    nums = [s['number'] for s in shown]
    if selected and selected[0].get('table'):
        arts = f"{one} {nums[0]}, " + TABLE_WORD[lang].format(n=selected[0]['table'])
    else:
        arts = f"{one if len(nums) == 1 else many} {', '.join(map(str, nums))}"
    doc_lang = LANG_NAME[lang].get(citation.language or '', citation.language or '')
    lines = [HEADER[lang].format(act=act, arts=arts, lang=doc_lang)]
    title = norm(subject_query(subject)) if subject in SUBJECTS else ''
    key = key_passage(req.query, shown, title)
    if key and (len(shown) > 1 or sum(len(' '.join(s['parts'])) for s in shown) > 600):
        lines += ['', KEY_LABEL[lang], f'« {key} »']
    lines += ['', FULL_LABEL[lang]]
    for section in shown:
        label = f"§ {section['number']}" + (f" — Tableau n°{section['table']}" if section.get('table') else '')
        lines += ['', f"[1] {label} (p. {section['page']})", '\n'.join(section['parts'])]
    rest = [s['number'] for s in selected if s not in shown]
    if rest:
        lines += ['', MORE_LABEL[lang].format(arts=', '.join(f'§ {n}' for n in rest))]
    lines += ['', NOTICE[lang]]
    return '\n'.join(lines + sources_footer(lang, [citation])), [s['number'] for s in shown]


def order_by_relevance(query, sections, subject):
    """Short acts keep all provisions, most relevant first (stable when the question has no informative word)."""
    texts = [norm(' '.join(s['parts'])) for s in sections]
    words = _question_words(query, norm(subject_query(subject)))
    if not words:
        return sections
    n = len(sections)
    idf = {w: math.log((n + 1) / (1 + sum(w in t for t in texts))) for w in words}
    scores = [sum(idf[w] for w in words if w in t) for t in texts]
    return [s for _, _, s in sorted(zip(scores, range(n), sections), key=lambda x: (-x[0], x[1]))]


# --------------------------------------------------------------------------- RNE formalities table: scope
TABLE_DOC = 'rne-formalities-procedure-table'
TABLE_SCOPE_QUESTION = (r'(?:scope|port[ée]e|champ|couvre|covers?|contient|contains?|d[ée]crit|describes?|نطاق|يتضمن|يشمل)'
                        r'.{0,160}(?:formalit|tableau des proc|procedure table|جدول الإجراءات)'
                        r'|(?:formalit|procedure table|جدول الإجراءات).{0,160}(?:scope|port[ée]e|champ|couvre|covers?|نطاق)')
SCOPE_TEXT = {
    'fr': ("Le document officiel « {title} » ({org}) est un tableau de {rows} procédures du Registre national des "
           "entreprises. Chaque ligne donne, dans la formulation officielle : le code de procédure, la nature du "
           "service, le genre et le type d'entreprise, la procédure, la redevance demandée et le délai.\n"
           "Répartition par nature du service (libellés officiels) :\n{services}\n"
           "Genre d'entreprise : {kinds}. Familles de codes : {codes}.\n"
           "Ce tableau ne contient pas de liste des pièces justificatives ; son applicabilité actuelle et son "
           "application à votre cas ne sont pas vérifiées. Pour une ligne précise, indiquez le code (ex. RNE C 001)."),
    'en': ("The official document “{title}” ({org}) is a table of {rows} procedures of the National Business "
           "Register. Each row gives, in the official wording: the procedure code, the nature of the service, the "
           "entity kind and type, the procedure, the fee requested and the deadline.\n"
           "Rows by nature of the service (official French labels):\n{services}\n"
           "Entity kind: {kinds}. Code families: {codes}.\n"
           "The table contains no list of supporting documents; its current applicability and its application to "
           "your case are not verified. For a specific row, give the code (e.g. RNE C 001)."),
    'ar': ("الوثيقة الرسمية «{title}» ({org}) جدول يضم {rows} إجراء خاصا بالسجل الوطني للمؤسسات. يتضمن كل سطر، "
           "بالصياغة الرسمية: رمز الإجراء، طبيعة الخدمة، صنف ونوع المؤسسة، الإجراء، المعلوم المطلوب والأجل.\n"
           "التوزيع حسب طبيعة الخدمة (التسميات الرسمية بالفرنسية):\n{services}\n"
           "صنف المؤسسة: {kinds}. أصناف الرموز: {codes}.\n"
           "لا يتضمن الجدول قائمة بالوثائق المطلوبة، ولم يتم التحقق من سريانه الحالي ولا من انطباقه على حالتك. "
           "لسطر معين، اذكر الرمز (مثلا RNE C 001)."),
}
SCOPE_TEXT['derja'] = SCOPE_TEXT['ar']


def table_scope_reply(req, corpus):
    """Deterministic description of the formalities table computed from the official rows (no generation)."""
    rows = [b['text'] for b in corpus.blocks(TABLE_DOC) if b['text'].startswith('Code procédure:')]
    citation = corpus.citation(TABLE_DOC)
    if not rows or not citation:
        return None
    from collections import Counter
    from agents.checklist_builder import sources_footer

    def field(name):
        return Counter(m.group(1).strip() for r in rows if (m := re.search(name + r':\s*(.*)', r)))
    services = '\n'.join(f'• {label} ({n})' for label, n in field('Nature du service').most_common())
    kinds = ', '.join(f'{label} ({n})' for label, n in field("Genre d'Entreprise").most_common())
    codes = ', '.join(f'RNE {k} ({n})' for k, n in Counter(re.search(r'RNE\s*([CIM])', r).group(1) for r in rows).most_common())
    lang = req.route.language
    text = SCOPE_TEXT[lang].format(title=citation.title, org=citation.source_organization, rows=len(rows),
                                   services=services, kinds=kinds, codes=codes)
    return AnswerResult(text='\n'.join([text] + sources_footer(lang, [citation])), found=True, method='passages_fallback',
                        citations=[citation], verification={'legal': {'method': 'table_scope_from_official_rows',
                                                                      'articles': [], 'semantic_conclusion_verified': False}})


def legal_reply(req, corpus):
    if re.search(TABLE_SCOPE_QUESTION, req.query, re.I) and req.route.procedure_category in {'business_registration', 'general'}:
        result = table_scope_reply(req, corpus)
        if result is not None:
            return result
    form = identify_form(req.query)
    if form and req.route.procedure_category in {'business_registration', 'general'}:
        return form_reply(req, corpus, form)
    if req.route.procedure_category not in {'business_registration', 'general'}:
        return None
    subject = identify_subject(req.query) or (req.route.context.legal_subject if req.route.context else None)
    if not subject:
        return None
    if req.route.context and not identify_subject(req.query):
        generic = re.search(r'ne correspond pas|does not (?:match|apply)|لا ينطبق', req.query, re.I)
        ambiguous = subject in {'rne-law-2018-52-ar', 'rne-decree-2022-298-fees-fr'} and re.search(r'^\s*(?:et |and |و)', req.query, re.I) and not re.search(r'\d', req.query)
        if generic or ambiguous:
            from agents.checklist_builder import sources_footer
            citation = corpus.citation(subject)
            cites = [citation] if citation else []
            return AnswerResult(text='\n'.join([CLARIFY[req.route.language]] + sources_footer(req.route.language, cites)), found=False, method='none', citations=cites)
    blocks = corpus.blocks(subject)
    sections = articles(blocks)
    if not sections:
        return AnswerResult(text=i18n.t('insufficient_evidence', req.route.language), found=False, method='none')
    requested = requested_article(req.query)
    # A table reference asks for the table's content unless the question is about another provision that
    # merely mentions the table (e.g. the 50 % reduction of Art. 4 "for the procedures of table n° 1").
    table = TABLE.search(req.query) if not re.search(TABLE_TOPICS, req.query, re.I) else None
    whole_act = False
    if requested is not None:
        selected = [s for s in sections if s['number'] == requested]
    elif table:
        selected = table_section(sections, int(table[1]))
    elif subject in {'rne-arrete-2026-35', 'rne-decree-beneficial-owners', 'rne-decree-name-reservation', 'rne-decree-law-2022-18-fr'}:
        # Short texts: all substantive provisions remain available, the most relevant ones first; only this case
        # is trimmed to a display budget (the rest are listed by number).
        selected, whole_act = order_by_relevance(req.query, sections, subject), True
    else:
        selected = rank_sections(req.query, sections, subject, req.passages)
    if not selected:
        return AnswerResult(text=i18n.t('insufficient_evidence', req.route.language), found=False, method='none')
    citation = corpus.citation(subject, page=selected[0]['page'])
    if not citation:
        return None
    text, shown = render_legal(req, corpus, subject, selected, citation, budget=whole_act)
    return AnswerResult(text=text, found=True, method='passages_fallback', citations=[citation],
                        verification={'legal': {'method': 'verbatim_source_articles', 'articles': shown,
                                                'semantic_conclusion_verified': False}})
