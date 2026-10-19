"""Explicit Arabic translations of the indexed French CIN guide (not official Arabic quotations).

Exact source matching prevents reuse after source edits. No content enters the official corpus.
Administrative applicability is unchanged. Unmapped text falls back explicitly, not to an LLM.
"""
from agents.corpus import norm

PAIRS = {
"Changement:": "تغيير:",
"Obtention de la carte d’identité nationale pour la première fois": "الحصول على بطاقة التعريف الوطنية لأول مرة",
"Renouvellement de la carte d’identité par une carte d’identité nationale": "تجديد بطاقة التعريف ببطاقة تعريف وطنية",
"Changement de la carte d’identité nationale pour modification de données.": "تغيير بطاقة التعريف الوطنية بسبب تغيير المعطيات",
"Changement de la carte d’identité nationale pour cause de vol, de perte ou de détérioration.": "تغيير بطاقة التعريف الوطنية بسبب السرقة أو الضياع أو التلف",
"Remplir l'imprimé administratif et le signer": "تعمير المطبوعة الإدارية وإمضاؤها",
"Atteindre l'âge légal (18 ans),": "بلوغ السن القانونية (18 سنة)",
"Etre de nationalité tunisienne,": "حمل الجنسية التونسية",
"Imprimé administratif à remplir": "مطبوعة إدارية يتم تعميرها",
"Extrait de naissance établi des registres originaux d'état civil datant de 3 mois au plus,": "مضمون ولادة مستخرج من السجلات الأصلية للحالة المدنية لا يتجاوز تاريخ إصداره 3 أشهر",
"Attestation prouvant la nationalité tunisienne,": "شهادة تثبت الجنسية التونسية",
"Attestation de résidence,": "شهادة إقامة",
"Attestation de travail ou de présence scolaire ou universitaire,": "شهادة عمل أو شهادة حضور مدرسي أو جامعي",
"3 photos d'identité de l'intéressé du format 3⁄4 cm prises en face sur support arrière d'une couleur blanche ou claire et à l'échelle 1/10 montrant le visage et les yeux,": "3 صور شمسية للمعني بالأمر بحجم 3⁄4 صم، من الأمام وبخلفية بيضاء أو فاتحة وبمقياس 1/10، تُظهر الوجه والعينين",
"Quittance de paiement du droit de timbre fiscal dû,": "وصل خلاص معلوم الطابع الجبائي المستوجب",
"Deux exemplaires de la copie de la carte de résidence et de la carte consulaire pour les résidents à l'étranger,": "نسختان من بطاقة الإقامة والبطاقة القنصلية للمقيمين بالخارج",
"Autorisation du tuteur légal signée, légalisée et motivée pour l'obtention de la carte d'identité nationale (raison professionnelle, éducative, sportive ou physique) et ce pour les mineurs de moins de 18 ans,": "ترخيص من الولي القانوني ممضى ومعرّف بالإمضاء ومعلّل للحصول على بطاقة التعريف الوطنية (لسبب مهني أو تعليمي أو رياضي أو بدني)، بالنسبة للقصر دون 18 سنة",
"Certificat indiquant le groupe sanguin (facultatif).": "شهادة تبين فصيلة الدم (اختيارية)",
"Poste de la police ou de la garde nationale du lieu de résidence du demandeur": "مركز الشرطة أو الحرس الوطني بمكان إقامة الطالب",
"Dans les 15 jours à partir de la date de dépôt de la demande": "خلال 15 يوما من تاريخ إيداع المطلب",
"Chaque citoyen tunisien doit renouveler sa carte d'identité par une carte d'identité nationale": "يجب على كل مواطن تونسي تجديد بطاقة تعريفه ببطاقة تعريف وطنية",
"Extrait de naissance datant de 3 mois au plus,": "مضمون ولادة لا يتجاوز تاريخ إصداره 3 أشهر",
"Copie de la carte à renouveler avec présentation de l'originale qui doit être remise aux services compétents lors de l'obtention de la nouvelle carte,": "نسخة من البطاقة المراد تجديدها مع الاستظهار بالأصل الذي يجب تسليمه للمصالح المختصة عند الحصول على البطاقة الجديدة",
"Pièce prouvant le changement des éléments de l'état civil, de la résidence ou de la profession, le cas échéant,": "وثيقة تثبت تغيير معطيات الحالة المدنية أو الإقامة أو المهنة عند الاقتضاء",
"Quittance de paiement du droit de timbre fiscal dû.": "وصل خلاص معلوم الطابع الجبائي المستوجب",
"Dans les 15 jours à compter de la date de dépôt du dossier": "خلال 15 يوما من تاريخ إيداع الملف",
"de l'un des éléments de l'état civil inscrit sur la carte,": "تغيير أحد عناصر الحالة المدنية المسجلة بالبطاقة",
"du lieu de résidence,": "تغيير مكان الإقامة",
"de la profession ou des autres données inscrites sur la carte.": "تغيير المهنة أو غيرها من المعطيات المسجلة بالبطاقة",
"La carte à changer,": "البطاقة المراد تغييرها",
"L'attestation ou la pièce motivant le changement :": "الشهادة أو الوثيقة المبررة للتغيير:",
"Extrait de naissance indiquant le nouveau nom en cas de changement du nom de famille": "مضمون ولادة يبين اللقب الجديد في حالة تغيير اللقب العائلي",
"Extrait de naissance ou copie de l'acte de mariage pour la femme mariée,": "مضمون ولادة أو نسخة من عقد الزواج بالنسبة للمرأة المتزوجة",
"Une copie du jugement de divorce ou un extrait de naissance indiquant le divorce pour la femme divorcée,": "نسخة من حكم الطلاق أو مضمون ولادة ينص على الطلاق بالنسبة للمرأة المطلقة",
"Certificat de décès ou extrait de décès de l'époux (pour la veuve ),": "شهادة وفاة أو مضمون وفاة الزوج (بالنسبة للأرملة)",
"Attestation prouvant le lieu de résidence en cas de changement de résidence ,": "شهادة تثبت مكان الإقامة في حالة تغيير الإقامة",
"Attestation de travail indiquant la nouvelle profession en cas de changement de profession,": "شهادة عمل تبين المهنة الجديدة في حالة تغيير المهنة",
"Trois photos d'identité de l'intéressé de format 3/4 cm prises en face sur support arrière d'une couleur blanche ou claire et à l'échelle de 1/10 montrant le visage et les yeux,": "ثلاث صور شمسية للمعني بالأمر بحجم 3/4 صم، من الأمام وبخلفية بيضاء أو فاتحة وبمقياس 1/10، تُظهر الوجه والعينين",
"Perte de la carte d'identité nationale": "ضياع بطاقة التعريف الوطنية",
"Attestation de déclaration de perte,": "شهادة تصريح بالضياع",
"Trois photos d'identité de l'intéressé de format 3/4 cm prises en face sur support arrière d'une couleur blanche ou claire et à l'échelle de 1/10 montrant les le visage et les yeux,": "ثلاث صور شمسية للمعني بالأمر بحجم 3/4 صم، من الأمام وبخلفية بيضاء أو فاتحة وبمقياس 1/10، تُظهر الوجه والعينين",
"Timbre fiscal de 25 dinars.": "طابع جبائي بقيمة 25 دينارا",
}
ARABIC = {norm(source): target for source, target in PAIRS.items()}


def translate_cin(lines):
    """Atomic translation: unmatched/changed passages reject the whole batch."""
    translated = [ARABIC.get(norm(line)) for line in lines]
    return translated if all(translated) else None
