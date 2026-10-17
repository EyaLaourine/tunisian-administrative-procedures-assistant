"""Conservative legal replies: source selection and unabridged, located quotations.

No legal rules or answer values are encoded here. Article bodies are read from the
unchanged official extraction. A quotation is not a finding of legal applicability.
"""
import re

from agents import i18n
from agents.corpus import norm
from agents.schemas import AnswerResult


SUBJECTS = {
    'rne-arrete-2026-35': (r'2026[- /]35|13 janvier 2026|(?:acc[eè]s|access|obten|consult|authorit|autorit|publi[qc]|information|نفاذ|اطلاع).{0,100}(?:b[eé]n[eé]ficiaire|beneficial|المستفيد)|(?:b[eé]n[eé]ficiaire|beneficial|المستفيد).{0,100}(?:acc[eè]s|access|information|publi[qc]|معلومات)', 'accès informations bénéficiaire effectif arrêté 13 janvier 2026'),
    'rne-law-2018-52-ar': (r'2018[- /]52|52.{0,12}2018', 'loi 2018-52 السجل الوطني للمؤسسات'),
    'rne-decree-law-2022-18-fr': (r'2022[- /]18|remise.{0,30}p[eé]nalit', 'décret-loi 2022-18 remise pénalités'),
    'rne-decree-2022-298-fees-fr': (r'2022[- /]298|298.{0,12}2022|redevance.{0,60}tableau|tableau.{0,60}redevance', 'décret 2022-298 redevances'),
    'rne-decree-name-reservation': (r'r[eé]servation|name reservation|trade name|company.name|حجز.{0,20}(?:تسمية|اسم|شارة)|2019[- /]53', 'réservation dénomination sociale nom commercial حجز التسمية'),
    'rne-decree-beneficial-owners': (r'b[eé]n[eé]ficiaire.{0,10}effectif|beneficial.owner|المستفيد الحقيقي|المستفيدون الحقيقيون|2019[- /]54|54.{0,12}2019', 'bénéficiaire effectif المستفيد الحقيقي'),
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
ARTICLE = re.compile(r'(?:^|\s)(?:Art\.\s*(\d+)\s*[-–]|Article\s+(premier)\s*[-–]|الفص\s*ل\s*(الأو(?:\s*ل)?|الاول|\d+)\s*(?:[-–ـ]|(?=\S)))', re.I)
HEADING = re.compile(r'^(?:Art\.\s*(\d+)|Article\s+(premier)|الفصل\s*(الأول|الاول|\d+))\s*$', re.I)


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
    return next((doc for doc, (pattern, _) in SUBJECTS.items() if re.search(pattern, text, re.I)), None)


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
        matches = [m for m in ARTICLE.finditer(text) if m.group(3) is None or text[:m.start()].strip() in {'', 'ل'}]
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


def legal_reply(req, corpus):
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
    requested = re.search(r'(?:article|art\.?|الفصل)\s*(\d+)\b', req.query, re.I)
    if requested:
        selected = [s for s in sections if s['number'] == int(requested[1])]
    elif subject in {'rne-arrete-2026-35', 'rne-decree-beneficial-owners', 'rne-decree-name-reservation', 'rne-decree-law-2022-18-fr'}:
        # Short texts: retain all substantive provisions, including list qualifications.
        selected = sections
    else:
        terms = {w for w in re.findall(r'\w+', norm(req.query)) if len(w) > 3}
        def score(s):
            text = norm(' '.join(s['parts']))
            overlap = sum(w in text for w in terms)
            # Retrieved body overlap resolves cross-language queries without generating law.
            overlap += sum(5 for p in req.passages if p.citation.doc_id == subject
                           and any(norm(part) in norm(p.text) for part in s['parts'] if len(part) > 45))
            return overlap
        selected = sorted(sections, key=score, reverse=True)[:3]
    if not selected:
        return AnswerResult(text=i18n.t('insufficient_evidence', req.route.language), found=False, method='none')
    from agents.checklist_builder import sources_footer
    citation = corpus.citation(subject, page=selected[0]['page'])
    if not citation:
        return None
    lines = [NOTICE[req.route.language]]
    for section in selected:
        lines += ['', f"[1] § {section['number']} (p. {section['page']})", '\n'.join(section['parts'])]
    return AnswerResult(text='\n'.join(lines + sources_footer(req.route.language, [citation])), found=True,
                        method='passages_fallback', citations=[citation], verification={'legal': {'method': 'unabridged_source_articles', 'articles': [s['number'] for s in selected], 'semantic_conclusion_verified': False}})
