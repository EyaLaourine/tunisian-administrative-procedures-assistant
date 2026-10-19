"""User-facing interface strings in the four supported languages.

These are fixed interface labels and notices only. Administrative content (documents, fees,
deadlines) always comes from official passages, never from this file.
"""

STRINGS: dict[str, dict[str, str]] = {
    "documents": {
        "en": "Required documents", "fr": "Pièces à fournir",
        "ar": "الوثائق المطلوبة", "derja": "الأوراق اللي لازمك تحضّرها",
    },
    "conditions": {
        "en": "Conditions", "fr": "Conditions",
        "ar": "الشروط", "derja": "الشروط",
    },
    "place": {
        "en": "Where to submit", "fr": "Lieu de dépôt",
        "ar": "مكان إيداع الملف", "derja": "وين تحطّ الملف",
    },
    "delay": {
        "en": "Processing time", "fr": "Délais",
        "ar": "الآجال", "derja": "قدّاش ياخو وقت",
    },
    "fees": {
        "en": "Fees", "fr": "Frais",
        "ar": "المعاليم", "derja": "قدّاش تخلّص",
    },
    "other": {
        "en": "Other information", "fr": "Autres informations",
        "ar": "معلومات أخرى", "derja": "معلومات أخرى",
    },
    "sources": {
        "en": "Official sources", "fr": "Sources officielles",
        "ar": "المصادر الرسمية", "derja": "المصادر الرسمية",
    },
    "disclaimer": {
        "en": "Information quoted from official sources; not legal advice. Their current validity has not been verified: please confirm with the competent administration.",
        "fr": "Informations citées de sources officielles ; ceci n'est pas un avis juridique. Leur validité actuelle n'a pas été vérifiée : confirmez auprès de l'administration compétente.",
        "ar": "معلومات منقولة من مصادر رسمية وليست استشارة قانونية. لم يتم التحقق من سريانها حاليا، يرجى التأكد لدى الإدارة المعنية.",
        "derja": "المعلومات هاذي منقولة من مصادر رسمية، وموش استشارة قانونية. ما تثبّتناش إذا مازالت سارية توّا، ثبّت في الإدارة المعنية.",
    },
    "application_translation": {
        "en": "Application translation of the official {source} text; it is not an official Arabic version. The source text prevails.",
        "fr": "Traduction applicative du texte officiel ({source}) ; ce n'est pas une version arabe officielle. Le texte source fait foi.",
        "ar": "ترجمة أعدها التطبيق للنص الرسمي ({source}) وليست نسخة عربية رسمية؛ النص الأصلي هو المعتمد.",
        "derja": "هاذي ترجمة من التطبيق بالعربية الفصحى للنص الرسمي ({source})، موش نسخة عربية رسمية؛ النص الأصلي هو المعتمد.",
    },
    "translation_unavailable": {
        "en": "Translation is unavailable or failed validation; the original official text ({source}) is shown explicitly.",
        "fr": "Traduction indisponible ou non validée ; le texte officiel original ({source}) est conservé explicitement.",
        "ar": "الترجمة غير متاحة أو لم تجتز التثبت؛ يُعرض النص الرسمي بلغته الأصلية ({source}).",
        "derja": "الترجمة موش متوفرة ولا ما تعدّاتش التثبت؛ نوريك النص الرسمي باللغة الأصلية ({source}).",
    },
    "machine_translation": {
        "en": "Automatic translation of the official {source} text; the official text prevails.",
        "fr": "Traduction automatique du texte officiel ({source}) ; le texte officiel fait foi.",
        "ar": "ترجمة آلية للنص الرسمي ({source})؛ النص الرسمي هو المعتمد.",
        "derja": "ترجمة أوتوماتيكية للنص الرسمي ({source})؛ النص الرسمي هو اللي يتعمل بيه.",
    },
    "official_msa": {
        "en": "The official text is quoted as published, in Modern Standard Arabic.",
        "fr": "Le texte officiel est cité tel quel, en arabe standard.",
        "ar": "النص الرسمي منقول كما نُشر.",
        "derja": "النص الرسمي مكتوب بالعربية الفصحى، نقلناه كيما هو باش ما يتبدلّش معناه.",
    },
    "original_language": {
        "en": "Quoted in the original language of the official document ({source}).",
        "fr": "Cité dans la langue originale du document officiel ({source}).",
        "ar": "منقول بلغة الوثيقة الرسمية الأصلية ({source}).",
        "derja": "منقول باللغة متاع الوثيقة الرسمية ({source}).",
    },
    "discrepancy": {
        "en": "Warning: the official {lang_a} and {lang_b} versions of this page state different amounts ({values_a} vs {values_b}). Confirm the current amount with the administration.",
        "fr": "Attention : les versions officielles {lang_a} et {lang_b} de cette page indiquent des montants différents ({values_a} contre {values_b}). Vérifiez le montant actuel auprès de l'administration.",
        "ar": "تنبيه: النسختان الرسميتان {lang_a} و{lang_b} لهذه الصفحة تذكران مبالغ مختلفة ({values_a} مقابل {values_b}). يرجى التأكد من المبلغ الحالي لدى الإدارة.",
        "derja": "ردّ بالك: النسخة الرسمية {lang_a} والنسخة {lang_b} فيهم مبالغ مختلفة ({values_a} و {values_b}). ثبّت في المبلغ الصحيح عند الإدارة.",
    },
    "no_checklist": {
        "en": "The official documents in my knowledge base do not contain a list of required documents for this procedure. Here is what the official sources do say:",
        "fr": "Les documents officiels de ma base ne contiennent pas de liste de pièces à fournir pour cette procédure. Voici ce que disent les sources officielles :",
        "ar": "الوثائق الرسمية المتوفرة لديّ لا تتضمن قائمة بالوثائق المطلوبة لهذا الإجراء. هذا ما تذكره المصادر الرسمية:",
        "derja": "الوثائق الرسمية اللي عندي ما فيهاش قائمة الأوراق اللازمة للإجراء هذا. هاو شنوّة تقول المصادر الرسمية:",
    },
    "rne_header": {
        "en": "National Business Register (RNE)", "fr": "Registre National des Entreprises (RNE)",
        "ar": "السجل الوطني للمؤسسات (RNE)", "derja": "السجل الوطني للمؤسسات (RNE)",
    },
    "rne_code": {"en": "Procedure code", "fr": "Code procédure", "ar": "رمز الإجراء", "derja": "كود الإجراء"},
    "rne_service": {"en": "Service", "fr": "Nature du service", "ar": "نوع الخدمة", "derja": "نوع الخدمة"},
    "rne_kind": {"en": "Entity category", "fr": "Genre d'Entreprise", "ar": "صنف المؤسسة", "derja": "صنف المؤسسة"},
    "rne_type": {"en": "Entity type", "fr": "Type d entreprise", "ar": "نوع المؤسسة", "derja": "نوع المؤسسة"},
    "rne_procedure": {"en": "Procedure", "fr": "Procédure", "ar": "الإجراء", "derja": "الإجراء"},
    "rne_fee": {"en": "Fee", "fr": "Redevance demandée", "ar": "المعلوم المستوجب", "derja": "قدّاش تخلّص"},
    "rne_deadline": {"en": "Deadline", "fr": "Délais", "ar": "الآجال", "derja": "الآجال"},
    "other_cases": {
        "en": "Other cases in the official guide", "fr": "Autres cas dans le guide officiel",
        "ar": "حالات أخرى في الدليل الرسمي", "derja": "حالات أخرى في الدليل الرسمي",
    },
    # ---- Smart Administrative Dossier Validator (interface text only; requirements are quoted officially)
    "dossier_title": {"en": "Dossier readiness report (assistance only)", "fr": "Rapport de préparation du dossier (aide uniquement)",
                      "ar": "تقرير جاهزية الملف (للمساعدة فقط)", "derja": "تقرير جاهزية الملف (للمساعدة برك)"},
    "dossier_filled": {"en": "Fields that appear filled", "fr": "Champs qui semblent remplis",
                       "ar": "خانات تبدو معمّرة", "derja": "خانات يظهر فيهم معمّرين"},
    "dossier_attention": {"en": "Fields requiring attention", "fr": "Champs à vérifier",
                          "ar": "خانات تتطلب الانتباه", "derja": "خانات لازمك تثبّت فيهم"},
    "dossier_mandatory": {"en": "mandatory according to the form", "fr": "obligatoire selon le formulaire",
                          "ar": "وجوبي حسب المطبوعة", "derja": "لازم حسب المطبوعة"},
    "dossier_unreadable": {"en": "could not be read", "fr": "illisible", "ar": "تعذرت قراءتها", "derja": "ما تقراتش"},
    "dossier_cannot_verify": {"en": "Sections this tool cannot check (signature, checkboxes)",
                              "fr": "Sections que cet outil ne peut pas vérifier (signature, cases à cocher)",
                              "ar": "أجزاء لا يمكن لهذه الأداة التثبت منها (الإمضاء، الخانات المربعة)",
                              "derja": "أجزاء ما نجمش نثبّت فيهم (الإمضاء، الكازيات)"},
    "dossier_requirements": {"en": "Official requirements", "fr": "Exigences officielles", "ar": "المتطلبات الرسمية", "derja": "الشروط الرسمية"},
    "dossier_not_verified_title": {"en": "Not verified by this tool", "fr": "Non vérifié par cet outil",
                                   "ar": "لم تتحقق منه هذه الأداة", "derja": "ما ثبّتتش فيه الأداة هاذي"},
    "dossier_status_supported_by_official_source": {"en": "official source", "fr": "source officielle", "ar": "مصدر رسمي", "derja": "مصدر رسمي"},
    "dossier_status_not_verified": {"en": "not verified", "fr": "non vérifié", "ar": "غير متحقق منه", "derja": "موش مثبّت"},
    "dossier_status_official_requirement_unavailable": {"en": "official list unavailable", "fr": "liste officielle indisponible",
                                                        "ar": "القائمة الرسمية غير متوفرة", "derja": "القائمة الرسمية موش موجودة"},
    "dossier_req_all_fields": {"en": "The official form asks that all data be completed; it states that any missing item leads to rejection.",
                               "fr": "Le formulaire officiel demande de remplir toutes les données ; il indique que toute donnée manquante entraîne le rejet.",
                               "ar": "تطلب المطبوعة الرسمية تعمير كل البيانات، وتنص على أن كل بيان ناقص موجب لرفض الطلب.",
                               "derja": "المطبوعة الرسمية تطلب تعمّر البيانات الكل، وتقول اللي كل بيان ناقص يتسبب في رفض المطلب."},
    "dossier_req_contact": {"en": "The official form states that the e-mail address and mobile number are mandatory.",
                            "fr": "Le formulaire officiel indique que l'e-mail et le numéro de mobile sont obligatoires.",
                            "ar": "تنص المطبوعة الرسمية على أن البريد الإلكتروني والهاتف الجوال وجوبيان.",
                            "derja": "المطبوعة الرسمية تقول اللي الإيمايل ونومرو البورتابل لازمين."},
    "dossier_req_documents_ok": {"en": "An official list of supporting documents exists for this procedure (see sources).",
                                 "fr": "Une liste officielle des pièces justificatives existe pour cette démarche (voir sources).",
                                 "ar": "توجد قائمة رسمية بالوثائق المطلوبة لهذا الإجراء (انظر المصادر).",
                                 "derja": "فما قائمة رسمية بالأوراق اللازمة للإجراء هذا (شوف المصادر)."},
    "dossier_req_documents_missing": {"en": "The form states that required supporting documents must be attached, but the available official sources do not list them: dossier completeness cannot be assessed.",
                                      "fr": "Le formulaire exige les pièces justificatives requises, mais les sources officielles disponibles ne les listent pas : la complétude du dossier ne peut pas être évaluée.",
                                      "ar": "تشترط المطبوعة إرفاق الوثائق المطلوبة، لكن المصادر الرسمية المتوفرة لا تذكر قائمتها: لا يمكن تقييم اكتمال الملف.",
                                      "derja": "المطبوعة تطلب الأوراق اللازمة، أما المصادر الرسمية اللي عندي ما فيهاش القائمة: ما نجمش نقيّم إذا الملف كامل."},
    "dossier_req_fee": {"en": "The official RNE table lists {n} registration procedures for this kind of entity, each with its fee and deadline; which one applies is not checked.",
                        "fr": "Le tableau officiel du RNE liste {n} procédures d'immatriculation pour ce type d'entreprise, chacune avec sa redevance et son délai ; celle qui s'applique n'est pas vérifiée.",
                        "ar": "يذكر الجدول الرسمي للسجل الوطني للمؤسسات {n} إجراءات تسجيل لهذا الصنف، لكل منها معلومها وأجلها؛ لم يتم التحقق من الإجراء المنطبق.",
                        "derja": "الجدول الرسمي فيه {n} إجراءات تسجيل للصنف هذا، كل واحد بمعلومو وأجلو؛ ما ثبّتناش أما واحد ينطبق."},
    "dossier_nv_documents": {"en": "Whether the supporting documents are attached", "fr": "La présence des pièces justificatives",
                             "ar": "إرفاق الوثائق المطلوبة", "derja": "إذا الأوراق اللازمة مرفوقين"},
    "dossier_nv_payment": {"en": "Payment of the fee", "fr": "Le paiement de la redevance", "ar": "خلاص المعلوم", "derja": "خلاص المعلوم"},
    "dossier_nv_signature": {"en": "Signature and date", "fr": "La signature et la date", "ar": "الإمضاء والتاريخ", "derja": "الإمضاء والتاريخ"},
    "dossier_nv_values": {"en": "Correctness of the values written in the fields", "fr": "L'exactitude des valeurs saisies",
                          "ar": "صحة البيانات المكتوبة", "derja": "صحة المعطيات المكتوبة"},
    "dossier_lim_unsupported": {"en": "Only the official RNE forms F-001 and F-002 are supported.",
                                "fr": "Seuls les formulaires officiels RNE F-001 et F-002 sont pris en charge.",
                                "ar": "المطبوعتان الرسميتان RNE F-001 و F-002 فقط مدعومتان.",
                                "derja": "كان المطبوعات الرسمية RNE F-001 و F-002 مدعومين."},
    "dossier_lim_no_rules": {"en": "Form fields were checked, but no dossier rules are configured for this form: dossier completeness cannot be evaluated.", "fr": "Les champs du formulaire ont été vérifiés, mais aucune règle de dossier n’est configurée : la complétude du dossier ne peut pas être évaluée.",
                             "ar": "تم تفقد خانات المطبوعة، لكن لا تتوفر قواعد للملف: لا يمكن تقييم اكتمال الملف.", "derja": "تفقدنا خانات المطبوعة، أما ما فماش قواعد للملف: ما ننجموش نقيّموا اكتمال الملف."},
    "dossier_lim_detection": {"en": "Field detection is automatic and was not tested on real handwriting or real photographs.",
                              "fr": "La détection des champs est automatique et n'a pas été testée sur de l'écriture manuscrite ou des photos réelles.",
                              "ar": "الكشف عن الخانات آلي ولم يُختبر على كتابة يدوية أو صور حقيقية.",
                              "derja": "الكشف على الخانات أوتوماتيكي وما تجرّبش على كتيبة باليد ولا تصاور حقيقية."},
    "dossier_lim_not_certification": {"en": "This is an assistance tool, not an official validation: only the administration decides whether a dossier is complete.",
                                      "fr": "Ceci est un outil d'aide, pas une validation officielle : seule l'administration décide si un dossier est complet.",
                                      "ar": "هذه أداة مساعدة وليست تصديقا رسميا: الإدارة وحدها تقرر اكتمال الملف.",
                                      "derja": "هاذي أداة مساعدة موش مصادقة رسمية: الإدارة برك تقرر إذا الملف كامل."},
    "dossier_sum_attention": {"en": "{missing} of {total} detected fields appear empty and {unreadable} could not be read.",
                              "fr": "{missing} des {total} champs détectés semblent vides et {unreadable} n'ont pas pu être lus.",
                              "ar": "{missing} من أصل {total} خانات مكتشفة تبدو فارغة و{unreadable} تعذرت قراءتها.",
                              "derja": "{missing} من {total} خانات يظهر فيهم فارغين و{unreadable} ما تقراوش."},
    "dossier_sum_filled": {"en": "All {total} detected fields appear filled.", "fr": "Les {total} champs détectés semblent remplis.",
                           "ar": "كل الخانات المكتشفة ({total}) تبدو معمّرة.", "derja": "الخانات الكل اللي لقيتهم ({total}) يظهر معمّرين."},
    "dossier_sum_no_checklist": {"en": "The official sources available do not list the required supporting documents, so dossier completeness cannot be assessed.",
                                 "fr": "Les sources officielles disponibles ne listent pas les pièces justificatives requises : la complétude du dossier ne peut pas être évaluée.",
                                 "ar": "لا تذكر المصادر الرسمية المتوفرة الوثائق المطلوبة، لذلك لا يمكن تقييم اكتمال الملف.",
                                 "derja": "المصادر الرسمية اللي عندي ما فيهاش الأوراق اللازمة، معناها ما نجمش نقيّم إذا الملف كامل."},
    "dossier_sum_checklist": {"en": "An official list of supporting documents exists; their presence is not checked by this tool.",
                              "fr": "Une liste officielle des pièces existe ; leur présence n'est pas vérifiée par cet outil.",
                              "ar": "توجد قائمة رسمية بالوثائق؛ لا تتحقق هذه الأداة من إرفاقها.",
                              "derja": "فما قائمة رسمية بالأوراق؛ الأداة هاذي ما تثبّتش إذا مرفوقين."},
    "dossier_sum_not_certified": {"en": "This report is not an official validation.", "fr": "Ce rapport n'est pas une validation officielle.",
                                  "ar": "هذا التقرير ليس تصديقا رسميا.", "derja": "التقرير هذا موش مصادقة رسمية."},
    "topic_mismatch": {
        "en": "The official documents I found are about a different procedure, so they cannot answer this question. I will not guess; please contact the competent administration.",
        "fr": "Les documents officiels trouvés concernent une autre démarche ; ils ne répondent donc pas à cette question. Je préfère ne pas deviner : veuillez contacter l'administration compétente.",
        "ar": "الوثائق الرسمية التي وجدتها تتعلق بإجراء آخر، لذلك لا تجيب عن هذا السؤال. لن أخمّن؛ يرجى الاتصال بالإدارة المعنية.",
        "derja": "الوثائق الرسمية اللي لقيتها على إجراء آخر، معناها ما تجاوبش على السؤال هذا. ما نحبش نخمّن، اتّصل بالإدارة المعنية.",
    },
    "unsupported_claim": {
        "en": "I could not verify the figures of the answer against the official sources, so I will not give it. Please consult the official text or the competent administration.",
        "fr": "Je n'ai pas pu vérifier les chiffres de la réponse dans les sources officielles ; je préfère ne pas la donner. Consultez le texte officiel ou l'administration compétente.",
        "ar": "لم أتمكن من التحقق من الأرقام الواردة في الإجابة من المصادر الرسمية، لذلك لن أقدمها. يرجى الرجوع إلى النص الرسمي أو الإدارة المعنية.",
        "derja": "ما نجمتش نثبّت في الأرقام متاع الجواب من المصادر الرسمية، ما نحبش نعطيهولك. ارجع للنص الرسمي ولا للإدارة المعنية.",
    },
    "insufficient_evidence": {
        "en": "I could not find official evidence that answers this question in my sources, so I will not guess. Please contact the competent administration.",
        "fr": "Je n'ai pas trouvé, dans mes sources officielles, d'éléments qui répondent à cette question ; je préfère ne pas deviner. Veuillez contacter l'administration compétente.",
        "ar": "لم أجد في مصادري الرسمية ما يجيب عن هذا السؤال، لذلك لن أخمّن. يرجى الاتصال بالإدارة المعنية.",
        "derja": "ما لقيتش في المصادر الرسمية اللي عندي حاجة تجاوب على السؤال هذا، وما نحبش نخمّن. اتّصل بالإدارة المعنية.",
    },
    "code_not_found": {
        "en": "The procedure code {code} does not appear in the official RNE formalities table.",
        "fr": "Le code de procédure {code} ne figure pas dans le tableau officiel des formalités du RNE.",
        "ar": "رمز الإجراء {code} غير موجود في الجدول الرسمي لإجراءات السجل الوطني للمؤسسات.",
        "derja": "الكود {code} موش موجود في الجدول الرسمي متاع إجراءات السجل الوطني للمؤسسات.",
    },
    "official_forms": {
        "en": "Official forms", "fr": "Formulaires officiels",
        "ar": "المطبوعات الرسمية", "derja": "المطبوعات الرسمية",
    },
    "not_found": {
        "en": "I could not find this information in the official documents I have. Please contact the competent administration.",
        "fr": "Je n'ai pas trouvé cette information dans les documents officiels dont je dispose. Veuillez contacter l'administration compétente.",
        "ar": "لم أجد هذه المعلومة في الوثائق الرسمية المتوفرة لديّ. يرجى الاتصال بالإدارة المعنية.",
        "derja": "ما لقيتش المعلومة هاذي في الوثائق الرسمية اللي عندي. اتّصل بالإدارة المعنية.",
    },
    "uncovered_category": {
        "en": "This procedure is not covered yet: no official source for it could be included in my knowledge base.",
        "fr": "Cette procédure n'est pas encore couverte : aucune source officielle n'a pu être intégrée à ma base.",
        "ar": "هذا الإجراء غير مشمول بعد: لم يتسنّ إدراج أي مصدر رسمي يخصه في قاعدة معارفي.",
        "derja": "الإجراء هذا مازال موش موجود عندي: ما نجمتش نزيد حتى مصدر رسمي عليه.",
    },
    "greeting": {
        "en": "Hello! I answer questions about Tunisian administrative procedures (passport, national ID card, company registration with the RNE) using official sources only. Ask your question, or send a photo/PDF of a form to check for missing fields.",
        "fr": "Bonjour ! Je réponds aux questions sur les démarches administratives tunisiennes (passeport, carte d'identité nationale, immatriculation au RNE) uniquement à partir de sources officielles. Posez votre question, ou envoyez une photo/un PDF de formulaire pour vérifier les champs manquants.",
        "ar": "مرحبا! أجيب عن الأسئلة المتعلقة بالإجراءات الإدارية التونسية (جواز السفر، بطاقة التعريف الوطنية، التسجيل بالسجل الوطني للمؤسسات) بالاعتماد على المصادر الرسمية فقط. اطرح سؤالك أو أرسل صورة/ملف PDF لمطبوعة للتثبت من الخانات الناقصة.",
        "derja": "عسلامة! نجاوبك على الإجراءات الإدارية في تونس (الباسبور، بطاقة التعريف، تسجيل شركة في السجل الوطني للمؤسسات) من المصادر الرسمية برك. اسأل سؤالك، ولا ابعثلي تصويرة ولا PDF متاع مطبوعة باش نثبّتلك شنوّة الخانات اللي ناقصة.",
    },
    "out_of_scope": {
        "en": "I can only help with Tunisian administrative procedures covered by my official sources (passport, national ID card, company registration with the RNE).",
        "fr": "Je ne peux aider que pour les démarches administratives tunisiennes couvertes par mes sources officielles (passeport, carte d'identité nationale, immatriculation au RNE).",
        "ar": "يمكنني المساعدة فقط في الإجراءات الإدارية التونسية التي تغطيها مصادري الرسمية (جواز السفر، بطاقة التعريف الوطنية، التسجيل بالسجل الوطني للمؤسسات).",
        "derja": "نجم نعاونك كان في الإجراءات الإدارية التونسية اللي عندي عليها مصادر رسمية (الباسبور، بطاقة التعريف، تسجيل شركة في السجل الوطني للمؤسسات).",
    },
    "form_identified": {
        "en": "Form recognised: {title}", "fr": "Formulaire reconnu : {title}",
        "ar": "تم التعرف على المطبوعة: {title}", "derja": "عرفت المطبوعة: {title}",
    },
    "form_unknown": {
        "en": "I could not match this file to an official form in my knowledge base, so I cannot check its fields. Supported forms: {forms}.",
        "fr": "Je n'ai pas pu associer ce fichier à un formulaire officiel de ma base ; je ne peux donc pas vérifier ses champs. Formulaires pris en charge : {forms}.",
        "ar": "لم أتمكن من مطابقة هذا الملف مع مطبوعة رسمية في قاعدة معارفي، لذا لا يمكنني التثبت من خاناتها. المطبوعات المدعومة: {forms}.",
        "derja": "ما نجمتش نعرف المطبوعة هاذي من المطبوعات الرسمية اللي عندي، معناها ما نجمش نثبّت في الخانات. المطبوعات اللي نعرفها: {forms}.",
    },
    "form_if_applicable": {
        "en": "Empty fields to fill in only if they apply to you", "fr": "Champs vides à remplir seulement s'ils vous concernent",
        "ar": "خانات فارغة تُعمَّر عند الاقتضاء فقط", "derja": "خانات فارغين تعمّرهم كان إذا يخصّوك",
    },
    "form_required_complete": {
        "en": "Every applicant field I located appears to be filled in.",
        "fr": "Tous les champs du demandeur localisés semblent remplis.",
        "ar": "كل خانات الطالب التي تم تحديدها تبدو معمّرة.", "derja": "الخانات متاعك الكل اللي لقيتهم يظهر معمّرين.",
    },
    "form_not_checked": {
        "en": "Not checked automatically (boxes, check boxes and signature); check them yourself",
        "fr": "Non vérifiés automatiquement (cases, cases à cocher et signature) ; à vérifier vous-même",
        "ar": "لا يتم التثبت منها آليا (الخانات المربعة والعلامات والإمضاء)؛ يرجى التثبت منها بنفسك",
        "derja": "ما نثبّتش فيهم أوتوماتيكيا (المربعات والعلامات والإمضاء)؛ ثبّت فيهم بروحك",
    },
    "form_admin_skipped": {
        "en": "{n} fields reserved for the administration were ignored.",
        "fr": "{n} champs réservés à l'administration ont été ignorés.",
        "ar": "تم تجاهل {n} خانة خاصة بالإدارة.", "derja": "خلّيت {n} خانات متاع الإدارة، ما تعمّرهمش.",
    },
    "form_missing": {
        "en": "Fields that look empty", "fr": "Champs qui semblent vides",
        "ar": "خانات تبدو فارغة", "derja": "خانات يظهر فيهم فارغين",
    },
    "form_unreadable": {
        "en": "Fields I could not locate (check them manually)", "fr": "Champs non localisés (à vérifier manuellement)",
        "ar": "خانات لم أتمكن من تحديدها (يرجى التثبت يدويا)", "derja": "خانات ما لقيتهمش (ثبّت فيهم بيدك)",
    },
    "form_complete": {
        "en": "Every field I located appears to be filled in.", "fr": "Tous les champs localisés semblent remplis.",
        "ar": "كل الخانات التي تم تحديدها تبدو معمّرة.", "derja": "الخانات الكل اللي لقيتهم يظهر معمّرين.",
    },
    "form_heuristic": {
        "en": "Automatic check ({method}); it may miss or misread handwriting. Nothing from your file is stored.",
        "fr": "Vérification automatique ({method}) ; l'écriture manuscrite peut être mal lue. Aucun contenu de votre fichier n'est conservé.",
        "ar": "تثبت آلي ({method})؛ قد لا تُقرأ الكتابة اليدوية بدقة. لا يتم حفظ أي محتوى من ملفك.",
        "derja": "تثبيت أوتوماتيكي ({method})؛ ينجم ما يقراش الكتيبة باليد مليح. ما نخبّي حتى حاجة من الملف متاعك.",
    },
    "form_error": {
        "en": "I could not read this file: {reason}", "fr": "Je n'ai pas pu lire ce fichier : {reason}",
        "ar": "تعذرت قراءة هذا الملف: {reason}", "derja": "ما نجمتش نقرا الملف هذا: {reason}",
    },
    "form_overview": {
        "en": "Printed content of the official form (quoted as printed):",
        "fr": "Contenu imprimé du formulaire officiel (cité tel quel) :",
        "ar": "المحتوى المطبوع للمطبوعة الرسمية (منقول كما هو):",
        "derja": "شنوة مكتوب في المطبوعة الرسمية (منقول كيما هو):",
    },
    "form_fields": {"en": "Fields to fill in", "fr": "Champs à remplir", "ar": "الخانات المطلوب تعميرها",
                    "derja": "الخانات اللي لازم تعمّرها"},
    "form_printed_text": {"en": "Printed instructions and options", "fr": "Mentions et options imprimées",
                          "ar": "التعليمات والخيارات المطبوعة", "derja": "التعليمات والخيارات المكتوبة"},
    "form_section_unavailable": {
        "en": "The indexed text of this official form does not contain a passage that answers that specific question; I will not guess. Here is what the form contains:",
        "fr": "Le texte indexé de ce formulaire officiel ne contient pas de passage qui réponde à cette question précise ; je préfère ne pas deviner. Voici ce que contient le formulaire :",
        "ar": "النص المفهرس لهذه المطبوعة الرسمية لا يتضمن فقرة تجيب عن هذا السؤال بالتحديد، ولن أخمن. هذا ما تحتويه المطبوعة:",
        "derja": "النص اللي عندي من المطبوعة هاذي ما فيهش جواب على السؤال هذا بالضبط، وما نحبش نخمّن. هاو شنوة فيها:",
    },
    "form_download_available": {"en": "Official download link", "fr": "Lien officiel de téléchargement",
                                "ar": "رابط التحميل الرسمي", "derja": "الرابط الرسمي باش تحمّلها"},
    "form_download_unavailable": {
        "en": "No verified download link for this form is available in my official sources: the official file could not be retrieved and verified. Please obtain the form from the competent administration.",
        "fr": "Aucun lien de téléchargement vérifié de ce formulaire n'est disponible dans mes sources officielles : le fichier officiel n'a pas pu être récupéré et vérifié. Procurez-vous le formulaire auprès de l'administration compétente.",
        "ar": "لا يتوفر في مصادري الرسمية رابط تحميل موثّق لهذه المطبوعة: لم يكن ممكنا جلب الملف الرسمي والتحقق منه. يرجى الحصول على المطبوعة من الإدارة المعنية.",
        "derja": "ما عنديش في المصادر الرسمية رابط تحميل مثبّت للمطبوعة هاذي: ما نجمناش نجيبو الملف الرسمي ونثبتو فيه. خوذ المطبوعة من الإدارة المعنية.",
    },
    "form_download_none": {
        "en": "My official sources do not contain a downloadable form for this procedure.",
        "fr": "Mes sources officielles ne contiennent pas de formulaire téléchargeable pour cette démarche.",
        "ar": "مصادري الرسمية لا تتضمن مطبوعة قابلة للتحميل لهذا الإجراء.",
        "derja": "المصادر الرسمية اللي عندي ما فيهاش مطبوعة تتحمّل للإجراء هذا.",
    },
    "reason_unreadable_pdf": {
        "en": "the PDF is damaged or unreadable", "fr": "le PDF est endommagé ou illisible",
        "ar": "ملف PDF تالف أو غير مقروء", "derja": "الـPDF مفسود ولا ما يتقراش",
    },
    "reason_invalid_upload": {
        "en": "the upload is invalid", "fr": "le fichier envoyé est invalide",
        "ar": "الملف المرسل غير صالح", "derja": "الملف اللي بعثتو موش صالح",
    },
    "reason_too_large": {
        "en": "the file is larger than {mb} MB", "fr": "le fichier dépasse {mb} Mo",
        "ar": "حجم الملف يتجاوز {mb} ميغابايت", "derja": "الملف أكبر من {mb} ميغا",
    },
    "reason_unsupported_type": {
        "en": "this file type is not supported (PDF, JPEG or PNG only)",
        "fr": "ce type de fichier n'est pas pris en charge (PDF, JPEG ou PNG uniquement)",
        "ar": "نوع الملف غير مدعوم (PDF أو JPEG أو PNG فقط)", "derja": "نوع الملف هذا موش مدعوم (PDF ولا JPEG ولا PNG برك)",
    },
    "reason_ocr_failed": {
        "en": "the text recognition failed on this image", "fr": "la reconnaissance du texte a échoué sur cette image",
        "ar": "فشل التعرف على النص في هذه الصورة", "derja": "ما نجمتش نقرا الكتيبة في التصويرة هاذي",
    },
    "reason_ocr_missing": {
        "en": "text recognition is not available on the server", "fr": "la reconnaissance de texte n'est pas disponible sur le serveur",
        "ar": "التعرف على النص غير متاح على الخادم", "derja": "قراية الكتيبة موش متوفرة في السرفور",
    },
    "reason_generic": {
        "en": "the file could not be processed", "fr": "le fichier n'a pas pu être traité",
        "ar": "تعذرت معالجة الملف", "derja": "ما نجمتش نعالج الملف",
    },
    "answer_fallback": {
        "en": "Here are the most relevant official passages:", "fr": "Voici les passages officiels les plus pertinents :",
        "ar": "هذه أكثر المقاطع الرسمية صلة بسؤالك:", "derja": "هاذوما أقرب المقاطع الرسمية لسؤالك:",
    },
}

SOURCE_LANGUAGE_LABEL = {"fr": "FR", "ar": "AR", "en": "EN", "mixed": "AR/FR", "unknown": "?"}


# Names of the official forms supported by the Form-Filling Helper (agents/form_helper.py).
FORM_NAMES = {
    "rne-form-f001-natural-person-registration": {
        "en": "RNE F-001 (registration of a natural person)", "fr": "RNE F-001 (immatriculation d'une personne physique)",
        "ar": "RNE F-001 (تسجيل شخص طبيعي)", "derja": "RNE F-001 (تسجيل شخص طبيعي)"},
    "rne-form-f002-legal-entity-registration": {
        "en": "RNE F-002 (registration of a legal entity)", "fr": "RNE F-002 (immatriculation d'une personne morale)",
        "ar": "RNE F-002 (تسجيل شخص معنوي)", "derja": "RNE F-002 (تسجيل شخص معنوي)"},
    "interior-national-id-application-form": {
        "en": "national identity card application (Ministry of the Interior)",
        "fr": "demande de carte d'identité nationale (ministère de l'Intérieur)",
        "ar": "مطلب بطاقة التعريف الوطنية (وزارة الداخلية)", "derja": "مطلب بطاقة التعريف الوطنية (وزارة الداخلية)"},
    "interior-passport-application-form": {
        "en": "ordinary passport application (Ministry of the Interior)",
        "fr": "demande de passeport ordinaire (ministère de l'Intérieur)",
        "ar": "مطلب جواز سفر عادي (وزارة الداخلية)", "derja": "مطلب جواز سفر عادي (وزارة الداخلية)"},
}


def form_name(doc_id: str, lang: str, fallback: str) -> str:
    names = FORM_NAMES.get(doc_id)
    return (names.get(lang) or names["fr"]) if names else fallback


def t(key: str, lang: str, **values: str) -> str:
    entry = STRINGS[key]
    text = entry.get(lang) or entry["fr"]
    return text.format(**values) if values else text
