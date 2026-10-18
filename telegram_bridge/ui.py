"""Localized interface text. Official source quotations are never translated here."""
TEXT = {
'en': {
'welcome': 'Welcome! I help with passports, birth certificates (coverage limited), business registration, document checklists and official form checks. Guidance uses available official sources and does not replace the competent administration.',
'help': 'Choose a procedure or ask a question. Commands: /start /help /language /procedures /passport /birth_certificate /business /checklist /form_check /privacy /cancel. For a checklist, describe first application or renewal, residence and relevant circumstances without identifying yourself.',
'choose': 'Choose a procedure:', 'language': 'Auto (default): I answer in the language of each message. You can also set a preferred language:',
'form': 'Send a PDF, JPEG or PNG, or a Telegram photo (up to {mb} MB). Use a redacted copy where possible. I flag potentially missing fields on supported official forms; this is not official approval or a legal validity check.',
'privacy': 'Uploads are processed temporarily in memory, never indexed into the public knowledge base and never saved by this assistant. Telegram also processes messages under its own policies. Session preferences expire after 30 minutes. Avoid sending identity numbers or other unnecessary personal details.',
'cancel': 'Interaction cancelled. Session preferences cleared.', 'selected': 'Preferred language saved. Menus use it, and so do very short messages; a question written in another language is still answered in that language. Choose Auto to remove the preference.',
'checklist': 'Which procedure? Include first application or renewal and whether you live in Tunisia or abroad. Do not send identity details.',
'passport': 'Passport', 'birth_certificate': 'Birth certificate', 'business': 'Business registration'},
'fr': {
'welcome': 'Bienvenue ! Passeports, actes de naissance (couverture limitée), création d’entreprise, listes de pièces et vérification de formulaires officiels. Ces indications reposent sur les sources officielles disponibles et ne remplacent pas l’administration compétente.',
'help': 'Choisissez une démarche ou posez une question. Commandes : /start /help /language /procedures /passport /birth_certificate /business /checklist /form_check /privacy /cancel. Précisez votre situation sans données personnelles.',
'choose': 'Choisissez une démarche :', 'language': 'Auto (par défaut) : je réponds dans la langue de chaque message. Vous pouvez aussi choisir une langue préférée :',
'form': 'Envoyez un PDF, JPEG, PNG ou une photo Telegram (maximum {mb} Mo), de préférence anonymisé. Les champs potentiellement manquants sont signalés sur les formulaires reconnus. Ce contrôle ne constitue ni approbation officielle ni validation juridique.',
'privacy': 'Les fichiers sont traités temporairement en mémoire, sans enregistrement ni ajout à la base publique. Telegram traite également les messages selon ses règles. Les préférences expirent après 30 minutes. Évitez les numéros d’identité et les données personnelles inutiles.',
'cancel': 'Interaction annulée. Préférences effacées.', 'selected': 'Langue préférée enregistrée. Elle sert aux menus et aux messages très courts ; une question écrite dans une autre langue reçoit toujours une réponse dans cette langue. Choisissez Auto pour revenir au mode automatique.',
'checklist': 'Quelle démarche ? Précisez première demande ou renouvellement et résidence en Tunisie ou à l’étranger, sans données d’identité.',
'passport': 'Passeport', 'birth_certificate': 'Acte de naissance', 'business': 'Création d’entreprise'},
'ar': {
'welcome': 'مرحبا! أساعد في إجراءات جواز السفر ومضمون الولادة (تغطية محدودة) وتسجيل المؤسسات وقوائم الوثائق وفحص المطبوعات الرسمية. الإرشادات حسب المصادر الرسمية المتاحة ولا تعوض الإدارة المختصة.',
'help': 'اختر إجراء أو اطرح سؤالك. الأوامر: /start /help /language /procedures /passport /birth_certificate /business /checklist /form_check /privacy /cancel. وضح حالتك دون بيانات شخصية.',
'choose': 'اختر الإجراء:', 'language': 'Auto (افتراضي): أجيب بلغة كل رسالة. يمكنك أيضا اختيار لغة مفضلة:',
'form': 'أرسل PDF أو JPEG أو PNG أو صورة Telegram (حتى {mb} ميغابايت). يفضل إخفاء البيانات الشخصية. ننبه إلى الحقول المحتمل نقصها في المطبوعات المعروفة فقط. الفحص ليس موافقة رسمية أو إثباتا للصلاحية القانونية.',
'privacy': 'تعالج الملفات مؤقتا في الذاكرة ولا تحفظ ولا تضاف إلى قاعدة المعرفة العامة. تعالج Telegram الرسائل حسب سياستها أيضا. تحذف تفضيلات الجلسة بعد 30 دقيقة. تجنب أرقام الهوية والبيانات غير الضرورية.',
'cancel': 'تم إلغاء التفاعل ومسح التفضيلات.', 'selected': 'تم حفظ اللغة المفضلة. تستعمل في القوائم وفي الرسائل القصيرة جدا، أما السؤال المكتوب بلغة أخرى فتكون الإجابة عنه بلغته. اختر Auto للرجوع إلى الوضع التلقائي.',
'checklist': 'ما الإجراء؟ وضح طلب أول مرة أو تجديد والإقامة في تونس أو بالخارج، دون بيانات الهوية.',
'passport': 'جواز السفر', 'birth_certificate': 'مضمون ولادة', 'business': 'تسجيل مؤسسة'},
'derja': {
'welcome': 'عسلامة! نعاونك في الباسبور ومضمون الولادة (التغطية محدودة) وتسجيل الشركات وقائمة الأوراق وتفقد المطبوعات الرسمية. المعلومات حسب المصادر الرسمية المتوفرة وما تعوضش الإدارة المعنية.',
'help': 'اختار إجراء ولا اسأل بالعربي ولا باللاتيني. الأوامر: /start /help /language /procedures /passport /birth_certificate /business /checklist /form_check /privacy /cancel.',
'choose': 'اختار الإجراء:', 'language': 'Auto (بالأساس): نجاوبك باللغة اللي تكتب بيها كل ميساج. تنجم زادة تختار لغة تحبها:',
'form': 'ابعث PDF ولا JPEG ولا PNG ولا تصويرة Telegram (حتى {mb} ميغابايت). غطي المعطيات الشخصية كي تنجم. نتفقدوا الخانات اللي يمكن ناقصة في المطبوعات المعروفة. هذا موش قبول رسمي ولا إثبات قانوني.',
'privacy': 'الملفات تتعالج وقتيا في الذاكرة، ما تتخزنش وما تدخلش لقاعدة المعرفة العامة. Telegram زادة تعالج الرسائل حسب سياستها. تفضيلات الجلسة تتمسح بعد 30 دقيقة. ما تبعثش أرقام الهوية ولا معطيات موش لازمة.',
'cancel': 'تلغى التفاعل وتمسحت التفضيلات.', 'selected': 'سجّلت اللغة اللي تحبها. نستعملها في القوائم وفي الميساجات القصيرة برشا، أما كان تكتب سؤال بلغة أخرى نجاوبك بيها. اختار Auto باش ترجع للوضع الأوتوماتيكي.',
'checklist': 'شنوة الإجراء؟ أول مرة ولا تجديد؟ ساكن في تونس ولا البرّا؟ ما تبعثش معطيات الهوية.',
'passport': 'باسبور', 'birth_certificate': 'مضمون ولادة', 'business': 'تسجيل شركة'}
}
COMMANDS = ['start','help','language','procedures','passport','birth_certificate','business','checklist','form_check','dossier_check','privacy','cancel']
PROCEDURES = {'passport': 'passport', 'birth_certificate': 'birth certificate', 'business': 'business registration'}

# Interface labels and status guidance contain no administrative requirements.
EXTRA = {
    "en": {
        "main": "Main menu", "back": "Back", "new": "New question", "browse": "Procedures",
        "languages": "Language", "forms": "Check a form", "ask": "Ask a new question. Previous procedure context is cleared; your language stays selected.",
        "manual": "Manual verification required. This check flags potential omissions only; it cannot certify readability, correctness or legal validity.",
        "unreadable": "The file could not be read reliably. Try a clear, straight photo or a readable PDF; do not assume its fields are empty.",
        "unsupported_form": "This form was not recognised as a supported official template. No field-completeness conclusion can be made.",
        "missing_fields": "Potentially missing fields: {count}. Review the field labels in the result above.",
        "no_missing": "No potentially missing fields were reported. This does not verify the information entered.",
        "long": "Please keep your question within 2,000 characters.",
    },
    "fr": {
        "main": "Menu principal", "back": "Retour", "new": "Nouvelle question", "browse": "Démarches",
        "languages": "Langue", "forms": "Vérifier un formulaire", "ask": "Posez une nouvelle question. Le contexte de démarche est effacé ; la langue choisie est conservée.",
        "manual": "Vérification manuelle nécessaire. Ce contrôle signale des omissions possibles ; il ne certifie ni lisibilité, ni exactitude, ni validité juridique.",
        "unreadable": "Le fichier n’a pas pu être lu correctement. Essayez une photo nette et droite ou un PDF lisible. Cela ne signifie pas que les champs sont vides.",
        "unsupported_form": "Ce formulaire ne correspond pas à un modèle officiel pris en charge. Aucune conclusion sur les champs ne peut être établie.",
        "missing_fields": "Champs potentiellement manquants : {count}. Consultez les libellés dans le résultat ci-dessus.",
        "no_missing": "Aucun champ potentiellement manquant signalé. Les informations saisies ne sont pas validées.",
        "long": "Limitez votre question à 2 000 caractères.",
    },
    "ar": {
        "main": "القائمة الرئيسية", "back": "رجوع", "new": "سؤال جديد", "browse": "الإجراءات",
        "languages": "اللغة", "forms": "فحص مطبوعة", "ask": "اطرح سؤالا جديدا. تم مسح سياق الإجراء مع الاحتفاظ باللغة المختارة.",
        "manual": "تلزم مراجعة يدوية. الفحص ينبه إلى نقص محتمل فقط ولا يثبت وضوح الكتابة أو صحة المعلومات أو الصلاحية القانونية.",
        "unreadable": "تعذرت قراءة الملف بشكل موثوق. أرسل صورة واضحة ومستقيمة أو PDF مقروءا. هذا لا يعني أن الحقول فارغة.",
        "unsupported_form": "لم يتم التعرف على نموذج رسمي مدعوم. لا يمكن الحكم على اكتمال الحقول.",
        "missing_fields": "عدد الحقول المحتمل نقصها: {count}. راجع أسماء الحقول في النتيجة أعلاه.",
        "no_missing": "لم يبلغ عن حقول ناقصة محتملة. هذا لا يثبت صحة المعلومات المكتوبة.",
        "long": "يرجى ألا يتجاوز السؤال 2000 حرف.",
    },
    "derja": {
        "main": "القائمة الرئيسية", "back": "رجوع", "new": "سؤال جديد", "browse": "الإجراءات",
        "languages": "اللغة", "forms": "تفقد مطبوعة", "ask": "اسأل سؤال جديد. تمسح سياق الإجراء واللغة اللي اخترتها تبقى.",
        "manual": "يلزم تفقد يدوي. الفحص ينبه لنقص ممكن برك، ما يثبتش وضوح الكتابة ولا صحة المعلومات ولا الصلاحية القانونية.",
        "unreadable": "ما نجمتش نقرا الملف بوضوح. ابعث تصويرة واضحة ومستقيمة ولا PDF مقروء. هذا ما يعنيش الخانات فارغة.",
        "unsupported_form": "المطبوعة موش من النماذج الرسمية اللي نعرفوها. ما ننجموش نحكموا على اكتمال الخانات.",
        "missing_fields": "خانات يمكن ناقصة: {count}. راجع أسامي الخانات في النتيجة الفوق.",
        "no_missing": "ما تبلّغتش خانات يمكن ناقصة. هذا ما يثبتش صحة المعلومات المكتوبة.",
        "long": "خلي السؤال ما يفوتش 2000 حرف.",
    },
}
for language, strings in EXTRA.items():
    TEXT[language].update(strings)

AUTO_SELECTED = {
    "en": "Automatic language: I answer in the language of each message.",
    "fr": "Langue automatique : je réponds dans la langue de chaque message.",
    "ar": "اللغة التلقائية: أجيب بلغة كل رسالة.",
    "derja": "اللغة أوتوماتيكية: نجاوبك باللغة اللي تكتب بيها كل ميساج.",
}
for language, note in AUTO_SELECTED.items():
    TEXT[language]["auto_selected"] = note


def button(label, data):
    return {"text": label, "callback_data": data}


def keyboard(lang):
    rows = [[button(TEXT[lang][p], "procedure:" + p)] for p in PROCEDURES]
    return {"inline_keyboard": rows + [[button(TEXT[lang]["back"], "menu:main")]]}


def main_keyboard(lang):
    return {"inline_keyboard": [
        [button(TEXT[lang]["browse"], "menu:procedures"), button(TEXT[lang]["languages"], "menu:language")],
        [button(TEXT[lang]["forms"], "menu:form_check"), button(TEXT[lang]["dossier_title"], "menu:dossier_check")],
        [button(TEXT[lang]["new"], "menu:new")],
    ]}


def navigation(lang):
    return {"inline_keyboard": [[button(TEXT[lang]["main"], "menu:main"), button(TEXT[lang]["new"], "menu:new")]]}


def language_keyboard(lang="en"):
    rows = [[button(title, "language:" + code)] for code, title in
            [("auto", "Auto 🌐"), ("en", "English"), ("fr", "Français"), ("ar", "العربية"), ("derja", "تونسي / Derja")]]
    return {"inline_keyboard": rows + [[button(TEXT[lang]["back"], "menu:main")]]}

BUSY = {
    "en": "A request is still running. Please wait, use /cancel, or start a new question from the menu.",
    "fr": "Une demande est en cours. Patientez, utilisez /cancel ou choisissez une nouvelle question dans le menu.",
    "ar": "يوجد طلب قيد المعالجة. انتظر أو استخدم /cancel أو اختر سؤالا جديدا من القائمة.",
    "derja": "فما طلب قاعد يتعالج. استنى ولا استعمل /cancel ولا اختار سؤال جديد من القائمة.",
}

# Dossier labels describe analysis categories, never administrative requirements.
DOSSIER_TEXT = {
    "en": {
        "dossier_title": "Dossier Validation",
        "dossier_check": "Dossier Validation: send a PDF, JPEG, PNG or Telegram photo (up to {mb} MB), preferably redacted. This upload mode stays selected until Form Check, New question or /cancel. Informational only; it does not certify legal completeness or official approval.",
        "dossier_filled": "Filled fields", "dossier_missing": "Missing fields",
        "dossier_unreadable": "Unreadable fields", "dossier_unverifiable": "Fields that cannot be verified",
        "dossier_supported": "Officially supported requirements",
        "dossier_unverified": "Requirements that cannot be verified",
        "dossier_unknown": "Not assessed / not reported",
        "dossier_none": "None reported (not a completeness certification)",
        "dossier_disclaimer": "Dossier validation is informational. It does not certify legal completeness or official approval. Manual verification by the competent administration remains necessary.",
    },
    "fr": {
        "dossier_title": "Validation du dossier",
        "dossier_check": "Validation du dossier : envoyez un PDF, JPEG, PNG ou une photo Telegram (maximum {mb} Mo), de préférence anonymisé. Ce mode reste actif jusqu’au contrôle de formulaire, à une nouvelle question ou à /cancel. Informatif uniquement ; aucune certification de complétude juridique ni approbation officielle.",
        "dossier_filled": "Champs remplis", "dossier_missing": "Champs manquants",
        "dossier_unreadable": "Champs illisibles", "dossier_unverifiable": "Champs non vérifiables",
        "dossier_supported": "Exigences étayées par des sources officielles",
        "dossier_unverified": "Exigences non vérifiables",
        "dossier_unknown": "Non évalué / non communiqué",
        "dossier_none": "Aucune signalée (ne certifie pas la complétude)",
        "dossier_disclaimer": "La validation du dossier est informative. Elle ne certifie ni la complétude juridique ni une approbation officielle. Une vérification manuelle par l’administration compétente reste nécessaire.",
    },
    "ar": {
        "dossier_title": "التحقق من الملف",
        "dossier_check": "التحقق من الملف: أرسل PDF أو JPEG أو PNG أو صورة Telegram (حتى {mb} ميغابايت)، ويفضل إخفاء البيانات الشخصية. يبقى هذا الوضع مختارا حتى فحص مطبوعة أو سؤال جديد أو /cancel. الفحص إعلامي فقط ولا يثبت الاكتمال القانوني أو الموافقة الرسمية.",
        "dossier_filled": "الحقول المعمرة", "dossier_missing": "الحقول الناقصة",
        "dossier_unreadable": "الحقول غير المقروءة", "dossier_unverifiable": "الحقول التي لا يمكن التحقق منها",
        "dossier_supported": "المتطلبات المدعومة بمصادر رسمية",
        "dossier_unverified": "المتطلبات التي لا يمكن التحقق منها",
        "dossier_unknown": "لم يتم تقييمها أو الإبلاغ عنها",
        "dossier_none": "لم يبلغ عن أي منها (ليس إثباتا للاكتمال)",
        "dossier_disclaimer": "التحقق من الملف إعلامي فقط ولا يثبت الاكتمال القانوني أو الموافقة الرسمية. تبقى المراجعة اليدوية من الإدارة المختصة ضرورية.",
    },
    "derja": {
        "dossier_title": "تفقد الملف",
        "dossier_check": "تفقد الملف: ابعث PDF ولا JPEG ولا PNG ولا تصويرة Telegram (حتى {mb} ميغابايت)، وغطي المعطيات الشخصية كي تنجم. الوضع يبقى مختار حتى تفقد مطبوعة ولا سؤال جديد ولا /cancel. التفقد للإعلام برك، موش شهادة اكتمال قانوني ولا موافقة رسمية.",
        "dossier_filled": "الخانات المعمرة", "dossier_missing": "الخانات الناقصة",
        "dossier_unreadable": "الخانات اللي ما تتقراش", "dossier_unverifiable": "الخانات اللي ما ننجموش نتثبتوا منها",
        "dossier_supported": "المتطلبات اللي عندها مصادر رسمية",
        "dossier_unverified": "المتطلبات اللي ما ننجموش نتثبتوا منها",
        "dossier_unknown": "ما تفقدناهاش ولا ما تبلّغتش",
        "dossier_none": "ما تبلّغ حتى واحد (موش شهادة اكتمال)",
        "dossier_disclaimer": "تفقد الملف للإعلام برك. ما يثبتش الاكتمال القانوني ولا الموافقة الرسمية. يلزم تفقد يدوي من الإدارة المعنية.",
    },
}
for language, strings in DOSSIER_TEXT.items():
    TEXT[language].update(strings)
    TEXT[language]["help"] += " /dossier_check — " + strings["dossier_title"]

DIALOGUE_PRIVACY = {
    "en": "For conversation follow-ups, only the procedure, application type, residence category and declared document types/counts are held in memory for up to 30 minutes. No identity values or message history are retained. /cancel clears this context.",
    "fr": "Pour les relances, seuls la démarche, le type de demande, la catégorie de résidence et les types/quantités de pièces déclarées sont gardés en mémoire jusqu’à 30 minutes. Aucun identifiant personnel ni historique de messages n’est conservé. /cancel efface ce contexte.",
    "ar": "للمتابعة تحفظ مؤقتا في الذاكرة لمدة تصل إلى 30 دقيقة فقط فئة الإجراء ونوع الطلب وفئة الإقامة وأنواع الوثائق وأعدادها المصرح بها. لا تحفظ أرقام الهوية أو سجل الرسائل. يمسح /cancel هذا السياق.",
    "derja": "باش نتابع معاك، نخليو في الذاكرة حتى 30 دقيقة كان الإجراء ونوع الطلب وفئة السكن وأنواع وعدد الأوراق اللي قلت عندك. ما نخزنوش أرقام الهوية ولا تاريخ الرسائل. /cancel يمسح السياق.",
}
for language, note in DIALOGUE_PRIVACY.items():
    TEXT[language]["privacy"] += "\n\n" + note
