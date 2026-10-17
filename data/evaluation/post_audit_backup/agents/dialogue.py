"""Conversation facts and grounded checklist personalization. No administrative facts are generated."""
import json
import re
import unicodedata

from pydantic import BaseModel, Field, ValidationError

from agents.schemas import DeclaredItem, DialogueContext, ItemKey

UI = {
 'en': {'application':'Is this a first application, renewal, or replacement after loss/theft?', 'residence':'Do you live in Tunisia or abroad?',
        'ack':'I have noted the documents you say you already have.', 'declared':'Declared as available (not verified)',
        'remaining':'Still to prepare or confirm — official wording', 'review':'Declarations do not verify quantity, specifications, authenticity or legal completeness. Some items below apply only to the circumstances stated in the official text.',
        'unknown':'The available official sources do not provide a document checklist for this case; I cannot establish what is missing.',
        'verify':'Available but quantity/specifications still need confirmation'},
 'fr': {'application':'Est-ce une première demande, un renouvellement ou un remplacement après perte/vol ?', 'residence':'Tu résides en Tunisie ou à l’étranger ?',
        'ack':'J’ai noté les pièces que tu déclares déjà avoir.', 'declared':'Déjà déclaré disponible (non vérifié)',
        'remaining':'Reste à préparer ou à confirmer — texte officiel', 'review':'Une déclaration ne vérifie ni la quantité, ni les caractéristiques, ni l’authenticité, ni la complétude juridique. Certaines pièces ci-dessous dépendent des circonstances précisées dans le texte officiel.',
        'unknown':'Les sources officielles disponibles ne donnent pas de liste de pièces pour ce cas ; je ne peux pas établir ce qui manque.',
        'verify':'Disponible selon ta déclaration, mais quantité/caractéristiques à confirmer'},
 'ar': {'application':'هل هو طلب أول مرة أم تجديد أم تعويض بعد ضياع أو سرقة؟', 'residence':'هل تقيم في تونس أم بالخارج؟',
        'ack':'سجلت الوثائق التي صرحت بأنك تملكها.', 'declared':'صرحت بأنها متوفرة (لم يتم التحقق منها)',
        'remaining':'ما بقي للتحضير أو التأكيد — النص الرسمي', 'review':'التصريح لا يثبت العدد أو المواصفات أو الأصالة أو اكتمال الملف قانونيا. بعض الوثائق أدناه تخص الحالات المبينة في النص الرسمي فقط.',
        'unknown':'المصادر الرسمية المتاحة لا تقدم قائمة وثائق لهذه الحالة، لذلك لا يمكنني تحديد ما ينقص.', 'verify':'متوفرة حسب تصريحك لكن العدد أو المواصفات تحتاج إلى تأكيد'},
 'derja': {'application':'أول مرة تعمل باسبور، تجديد، ولا تعويض بعد ضياع أو سرقة؟', 'residence':'تسكن في تونس ولا البرّا؟',
        'ack':'سجلت الأوراق اللي قلت عندك منهم.', 'declared':'قلت عندك منها (ما تثبتناش فيها)',
        'remaining':'اللي مازال تحضّرو ولا تثبّت فيه — النص الرسمي', 'review':'كي تقول عندك ورقة، هذا ما يثبتش العدد ولا المواصفات ولا صحتها ولا اكتمال الملف قانونيا. بعض الأوراق لتالي تلزم كان في الحالات المكتوبة في النص الرسمي.',
        'unknown':'المصادر الرسمية اللي عنا ما فيهاش قائمة أوراق للحالة هاذي، ما نجمش نحدّد شنوة ناقص.', 'verify':'قلت متوفرة أما يلزم تثبّت في العدد والمواصفات'},
}

# These patterns describe language and document labels, not requirements or legal amounts.
LABELS = {
 'photos': r'photos?|photographs?|pictures?|صور|sou?war|tsawer|تصاور',
 'identity_card_copy': r'(?:copie|copy|نسخة).{0,35}(?:identit|identity|التعريف)',
 'application_form': r'formulaire|application form|استمارة|إستمارة|imprimé',
 'old_passport': r'ancien passeport|old passport|الجواز القديم|جواز السفر القديم',
 'residence_proof': r'(?:prouv|proof|إثبات).{0,40}(?:résidence|residen|الإقامة)',
 'school_proof': r'scolari|enrollment|ما يفيد الدراسة',
 'payment_receipt': r'quittance|receipt|وصل خلاص',
 'birth_certificate': r'extrait de naissance|birth certificate|مضمون ولادة',
 'guardian_authorization': r'autorisation.{0,15}tuteur|authorization.{0,20}guardian|ترخيص الولي',
}
APPLICATIONS = {
 'first_time': r'premi[eè]re (?:demande|fois)|first (?:application|time)|awel marra|أول مرة|اول مرة|لأول مرة',
 'renewal': r'renouvel|renew|تجديد|نجدد|nejjedd|jadded',
 'loss': r'\b(?:perdu|perte|lost|stolen|dha3|tsre9)\b|ضياع|ضاع|سرقة',
 'modification': r'changement|modification|تغيير|nbaddel',
 'pilgrimage': r'pilgrimage|p[èe]lerinage|\bhajj\b|الحج',
}
POSSESSION = r"\b(?:j'ai|jai|je dispose|i have|i already have|already have|3andi|andi|got)\b|عندي|لدي|عندى"
NEGATIVE = r"\b(?:don't have|do not have|no longer have|j'ai pas|n'ai pas|ma3andich|maandich)\b|ما عنديش|ليس لدي|ماعنديش"
REMAINING = r'manq|reste|remaining|still need|what else|missing|ne9s|na9s|neks|ناقص|نقص|ينقص|ناقصني'


def normalize(text):
    text = unicodedata.normalize('NFKC', text).lower().replace('’', "'")
    return re.sub(r'[\u064b-\u0652\u0640]', '', text)


class EvidenceFact(BaseModel):
    value: str
    evidence: str = Field(min_length=1, max_length=200)


class EvidenceItem(BaseModel):
    key: ItemKey
    quantity: int | None = Field(default=None, ge=0, le=100)
    available: bool
    evidence: str = Field(min_length=1, max_length=200)


class Extraction(BaseModel):
    application: EvidenceFact | None = None
    residence: EvidenceFact | None = None
    items: list[EvidenceItem] = Field(default_factory=list, max_length=9)


def understand(text, state, llm=None, prompts=None):
    """Extract explicit facts. Optional model output is accepted only with literal message evidence."""
    state = state.model_copy(deep=True)
    q = normalize(text)
    updates = {}
    app = None
    for key,pattern in APPLICATIONS.items():
        match = re.search(pattern,q)
        if match and not re.search(r"(?:not|pas|sans|موش|مش)\s*$",q[max(0,match.start()-15):match.start()]):
            app = key
            break
    residence = ('tunisia' if re.search(r'en tunisie|in tunisia|fi tou?nes|fi tunis|في تونس|بالتراب التونسي', q)
                 else 'abroad' if re.search(r"[ée]tranger|abroad|barra|5arej|kharej|بالخارج|الخارج|البرّا|البرا", q) else None)
    clauses = re.split(r'[,;.!؟\n]|\bbut\b|\bmais\b|\bama\b| لكن | أما ',q)
    for clause in clauses:
        possession = re.search(POSSESSION, clause) is not None
        negative = re.search(NEGATIVE, clause) is not None
        for key, pattern in LABELS.items():
            if re.search(pattern, clause) and (possession or negative):
                quantity = None
                if key == 'photos':
                    match = re.search(r'(\d{1,3})\s*(?:photos?|photographs?|pictures?|sou?war|tsawer|صور|تصاور)', clause)
                    if match and int(match[1]) <= 100:
                        quantity = int(match[1])
                updates[key] = None if negative else DeclaredItem(key=key, quantity=quantity)
    # Use the local model only when deterministic language rules cannot extract any stated fact.
    # Unknown statements remain unknown on model failure; no requirement is ever model-generated.
    fact_cue = re.search(r"already|collected|gathered|my |déjà|deja|rassembl|poss[eè]d|j'ai|i have|i live|je vis|je suis|عندي|لدي|اسكن|أسكن",q)
    if not app and not residence and not updates and fact_cue and llm is not None and prompts is not None:
        try:
            raw = llm.run(prompts.get('dialogue_understanding'), message=text)
            data = json.loads(raw.text)
            if not isinstance(data,dict):
                raise ValueError('Invalid extraction object')
            valid_items = []
            for value in (data.get('items') or [])[:9]:
                try:
                    valid_items.append(EvidenceItem.model_validate(value))
                except ValidationError:
                    continue  # One invalid model record must not discard separately grounded facts.
            extracted = Extraction(items=valid_items)
            for name in ('application','residence'):
                if data.get(name):
                    try:
                        setattr(extracted,name,EvidenceFact.model_validate(data[name]))
                    except ValidationError:
                        pass
            for name, allowed in [('application', set(APPLICATIONS)), ('residence', {'tunisia','abroad'})]:
                fact = getattr(extracted, name)
                if fact and fact.value in allowed and normalize(fact.evidence) in q:
                    if name == 'application':
                        if fact.value in APPLICATIONS and not re.search(APPLICATIONS[fact.value],normalize(fact.evidence)):
                            continue
                        app = fact.value
                    else:
                        residence = fact.value
            for item in extracted.items:
                evidence = normalize(item.evidence)
                if evidence not in q:
                    continue
                count = item.quantity
                if count is not None and count not in [int(x) for x in re.findall(r'\b\d+\b', evidence)]:
                    count = None
                if count is not None and item.key == 'photos' and not re.search(r'\b0?' + str(count) + r'\s*(?:photos?|photographs?|pictures?|sou?war|tsawer|صور|تصاور)',evidence):
                    count = None
                # Negation always wins over a model's possession claim.
                available = item.available and re.search(NEGATIVE, evidence) is None
                updates[item.key] = DeclaredItem(key=item.key,quantity=count) if available else None
        except Exception as exc:
            # Do not log model outputs, excerpts, user messages or exception contents.
            import logging
            logging.getLogger(__name__).warning('dialogue_understanding_unavailable', extra={'fields':{'error':type(exc).__name__}})
    if q.strip(' .?!') in {'tunisie','tunisia','tounes','tunis','تونس'}:
        residence = 'tunisia'
    if app:
        state.hints = [h for h in state.hints if h not in APPLICATIONS] + [app]
    if residence:
        state.residence = residence
    state.hints = [h for h in state.hints if h != 'abroad'] + (['abroad'] if state.residence == 'abroad' else [])
    items = {item.key:item for item in state.declared_items}
    for key, value in updates.items():
        if value is None:
            items.pop(key,None)
        else:
            items[key] = value
    state.declared_items = list(items.values())
    return state, bool(updates) or bool(re.search(REMAINING,q)), bool(app or residence or updates)


def clarify(state, language):
    ui = UI[language]
    questions = []
    if not any(h in APPLICATIONS for h in state.hints):
        questions.append(ui['application'])
    if state.residence is None:
        questions.append(ui['residence'])
    if questions and state.declared_items:
        questions.insert(0,ui['ack'])
    return '\n\n'.join(questions) if questions else None


def canonical_query(state, intent):
    labels = {'passport':'passeport passport جواز السفر', 'national_id':"carte d'identité national identity card", 'business_registration':'business registration RNE'}
    hints = {'first_time':'première fois first time', 'renewal':'renouvellement renewal', 'loss':'perte lost',
             'modification':'changement modification', 'pilgrimage':'pèlerinage pilgrimage'}
    goal = {'fees':'frais fees', 'processing_time':'délai processing time', 'submission_place':'lieu de dépôt where to submit',
            'eligibility':'conditions eligibility'}.get(intent,'pièces à fournir required documents')
    return ' '.join([goal,labels.get(state.category,state.category or ''),*(hints[h] for h in state.hints if h in hints),
                     'résident à l’étranger abroad' if state.residence=='abroad' else 'résident en Tunisie'])


def personalize(result, state, language):
    """Render only existing verbatim document items, grouped by unverified declarations."""
    from agents.checklist_builder import sources_footer
    ui = UI[language]
    sections = [s for s in result.sections if s.kind == 'documents']
    if not sections:
        result.text = ui['unknown'] + '\n\n' + result.text
        return result
    declared = {item.key:item for item in state.declared_items}
    ready, remaining, uncertain = [], [], []
    for section in sections:
        originals, rendered = section.items, section.translated_items or section.items
        photo_group = False
        for original, line in zip(originals,rendered):
            normalized = normalize(original)
            key = next((k for k,p in LABELS.items() if re.search(p,normalized)),None)
            # Specification lines immediately after the photo heading stay with that same requirement.
            photo_detail = photo_group and bool(re.search(r'fond|format|خلفية|حجم',normalized))
            if not photo_detail:
                photo_group = key == 'photos'
            if 'first_time' in state.hints and key == 'old_passport':
                continue  # The official item is explicitly about a previous passport.
            item = declared.get(key) if key else None
            if photo_detail and 'photos' in declared:
                uncertain.append(line)
                continue
            if item:
                if key == 'photos':
                    numbers = re.findall(r'\b\d+\b',normalized)
                    required = int(numbers[0]) if numbers else None
                    if required is None or item.quantity != required:
                        uncertain.append(line)
                        continue
                ready.append(line)
            else:
                remaining.append(line)
    out = [result.scenario or '',ui['ack']]
    for heading, lines in [(ui['declared'],ready),(ui['verify'],uncertain),(ui['remaining'],remaining)]:
        if lines:
            out += ['',heading + ':',*['• '+line for line in lines]]
    out += ['',ui['review']]
    from agents import i18n
    if result.translation and result.translation.get('validated'):
        out += ['',i18n.t('machine_translation',language,source=i18n.SOURCE_LANGUAGE_LABEL.get(result.source_language,result.source_language))]
    for warning in result.warnings:
        out += ['',warning]
    result.text = '\n'.join(out + sources_footer(language,result.citations))
    return result


def route_dialogue(router, req):
    from agents.intent_router import _rule_category, _rule_intent, _normalize, _hits, GREETING_KEYWORDS, next_agent_for
    from agents.schemas import RouteDecision
    state = req.context.model_copy(deep=True)
    text = _normalize(req.text)
    explicit = _rule_category(text)
    direct_intent = _rule_intent(text)
    if not explicit and _hits(text,GREETING_KEYWORDS) and len(text.split()) <= 6:
        return None
    if explicit and explicit != state.category:
        # Possession of a supporting birth certificate does not switch an existing passport procedure.
        inventory = re.search(POSSESSION,normalize(req.text)) or re.search(NEGATIVE,normalize(req.text))
        if not (explicit in {'birth_certificate','national_id'} and state.category and inventory):
            state = DialogueContext(category=explicit)
    if not state.category or state.category not in {'passport','national_id','business_registration'}:
        return None
    state, remaining, facts = understand(req.text,state,router.llm,router.prompts)
    contextual = bool(re.search(r'^(et |and |what about|w |و|وماذا|وإذا)',text))
    if not explicit and not direct_intent and not remaining and not facts and not contextual:
        return None
    intent = ('remaining_documents' if remaining else direct_intent or state.pending_intent or (state.last_intent if contextual or facts else None) or 'procedure_info')
    # Completing a clarification resumes the pending personalized request rather than replacing it.
    if facts and not direct_intent and state.pending_intent:
        intent = 'remaining_documents' if state.declared_items else state.pending_intent
    if state.declared_items and intent == 'required_documents':
        intent = 'remaining_documents'
    state.pending_intent = intent
    language = req.language
    if language is None:
        from agents.language import detect_language
        language = detect_language(req.text)
    question = clarify(state,language) if state.category == 'passport' else None
    if question:
        return RouteDecision(language=language,intent=intent,procedure_category=state.category,hints=state.hints,
                             next_agent='reply',reply=question,method='rules',context=state)
    if intent == 'form_help':
        return None
    nxt = next_agent_for(state.category, 'required_documents' if intent=='remaining_documents' else intent)
    if state.category == 'business_registration' and intent in {'fees','processing_time'}:
        from agents.intent_router import TABLE_SIGNALS, RNE_CODE
        if not _hits(text,TABLE_SIGNALS) and not RNE_CODE.search(req.text):
            nxt = 'answer' 
    focus = any(re.search(pattern,normalize(req.text)) for pattern in LABELS.values())
    if intent == 'procedure_info' or (focus and not remaining):
        nxt = 'answer'
        intent = 'procedure_info'
    state.pending_intent = None
    state.last_intent = intent
    query = canonical_query(state,intent)
    if intent == 'procedure_info':
        query = req.text + '\n' + query
    return RouteDecision(language=language,intent=intent,procedure_category=state.category,hints=state.hints,
                         next_agent=nxt,method='rules',context=state,retrieval_query=query[:2000])
