"""Build the grounded evaluation set: data/evaluation/eval_set.jsonl.

Questions are user questions written for evaluation. Ground truth is NOT written by hand: every
evidence span below must occur verbatim in the extracted official document it names. The script
verifies each span against data/processed/extracted/<doc_id>.json, records the page and the full
official block as the reference extract, and copies the source URL from the manifest. Items whose
evidence cannot be found are marked UNVERIFIED and excluded from metrics.

Answerability:
  answerable   - the corpus states the answer (evidence groups given)
  conflicting  - official sources state different values (one evidence group per version)
  unsupported  - the corpus contains no verified answer; the assistant must not provide one
  ambiguous    - underspecified request; document-level relevance only, or none
  out_of_scope - not an administrative procedure covered by the assistant

Usage: .venv/Scripts/python scripts/build_eval_set.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ingestion.manifest import Manifest  # noqa: E402
from rag.evaluation import norm  # noqa: E402

PFR, PAR = "interior-passport-guide-fr", "interior-passport-guide-ar"
IDFR = "interior-national-id-guide-fr"
TABLE = "rne-formalities-procedure-table"
FEES, LAW, DL18 = "rne-decree-2022-298-fees-fr", "rne-law-2018-52-ar", "rne-decree-law-2022-18-fr"
RESERV, BENEF, ARR = "rne-decree-name-reservation", "rne-decree-beneficial-owners", "rne-arrete-2026-35"
F001, F002 = "rne-form-f001-natural-person-registration", "rne-form-f002-legal-entity-registration"

# Reusable evidence groups (alternatives are equivalent passages in different official documents).
G_RENEW = [(PFR, "Joindre l'ancien passeport en cas de renouvellement"), (PAR, "إضافة الجواز القديم في حالة تجديد")]
G_FORM = [(PFR, "Un imprimé d’obtention d'un passeport ordinaire lisible à la machine"),
          (PAR, "تعمير إستمارة الحصول على جواز سفر عادي مقروء آليا")]
G_DELAY = [(PFR, "Dans les 15 jours à compter de la date de dépôt du dossier"), (PAR, "خلال 15 يوما من تاريخ تقديم الطلب")]
G_NAME6M = [(RESERV, "صالحة لمدة ستة أشهر قابلة للتجديد مرة واحدة")]
G_BO20 = [(BENEF, "أو تفوق 20 % م ن رأس المال")]
G_C012 = [(TABLE, "Code procédure: RNE C 012")]

# (id, question, language, category, intent, answerability, [groups], note)
ITEMS = [
    # ---------------------------------------------------------------- passport
    ("P01", "Quelles pièces fournir pour une première demande de passeport ?", "fr", "passport", "required_documents", "answerable", [G_FORM], ""),
    ("P02", "What documents are needed to renew a Tunisian passport?", "en", "passport", "required_documents", "answerable", [G_RENEW], ""),
    ("P03", "ما هي الوثائق المطلوبة لتجديد جواز السفر؟", "ar", "passport", "required_documents", "answerable", [G_RENEW], ""),
    ("P04", "شنوة الأوراق اللازمة باش نجدد الباسبور؟", "derja", "passport", "required_documents", "answerable", [G_RENEW], ""),
    ("P05", "chnowa el wra9 eli lezmin bech nejjedd el passbor?", "derja", "passport", "required_documents", "answerable", [G_RENEW], "Latin-script Derja"),
    ("P06", "Quel est le montant du timbre fiscal pour un passeport en Tunisie ?", "fr", "passport", "fees", "conflicting",
     [[(PFR, "De 60 dinars pour les autres")], [(PAR, "80 دينارا بالنسبة للبقية")]],
     "Residents in Tunisia: FR page 20/60 TND, AR page 25/80 TND."),
    ("P07", "Is the passport stamp duty for students 20 or 25 dinars?", "en", "passport", "fees", "conflicting",
     [[(PFR, "De 20 dinars pour les élèves, étudiants et enfants de moins de 6 ans")],
      [(PAR, "25 دنانير بالنسبة للتلاميذ و الطلبة والأطفال دون 6 سنوات")]], "Same FR/AR conflict."),
    ("P08", "How much is the passport stamp duty for Tunisians living abroad?", "en", "passport", "fees", "answerable",
     [[(PFR, "De 80 dinars pour les autres"), (PAR, "ما يعادل 80 دينارا تونسيا بالعملة الأجنبية للبقية")]], "FR and AR agree for residents abroad."),
    ("P09", "Où déposer le dossier de passeport quand on réside à l'étranger ?", "fr", "passport", "submission_place", "answerable",
     [[(PFR, "Ambassade ou consulat ou représentation diplomatique de la Tunisie"), (PAR, "السفارة أو القنصلية")]], ""),
    ("P10", "Quel est le délai d'obtention d'un passeport ?", "fr", "passport", "processing_time", "answerable", [G_DELAY], ""),
    ("P11", "J'ai perdu mon passeport, quelles pièces dois-je fournir ?", "fr", "passport", "required_documents", "answerable",
     [[(PFR, "Attestation de déclaration de perte du passeport"), (PAR, "شهادة ضياع جواز السفر")]], ""),
    ("P12", "What is the stamp duty for a duplicate passport after loss?", "en", "passport", "fees", "answerable",
     [[(PFR, "Quittance de paiement du droit de timbre fiscal dû (150 dinars)"), (PAR, "وصل خلاص معلوم الطابع الجبائي المستوجب (150 دينارا)")]], ""),
    ("P13", "Quelles sont les caractéristiques des photos pour le passeport ?", "fr", "passport", "required_documents", "answerable",
     [[(PFR, "format 3.5/4.5 cm"), (PAR, "أن يكون حجم الصورة 3.5/4.5 صم تقريبا")]], ""),
    ("P14", "ما هي شروط الحصول على جواز السفر؟", "ar", "passport", "eligibility", "answerable",
     [[(PAR, "حاملا للجنسية التونسية"), (PFR, "Etre de nationalité tunisienne")]], ""),
    ("P15", "Quelles pièces pour le document de voyage du pèlerinage ?", "fr", "passport", "required_documents", "answerable",
     [[(PFR, "Copie de la carte nationale d'identité."), (PAR, "نسخة من بطاقة التعريف الوطنية")]], "Hajj travel document scenario."),
    ("P16", "9adech ya5ou wa9t el passbor?", "derja", "passport", "processing_time", "answerable", [G_DELAY], "Latin-script Derja"),
    ("P17", "Can a minor get a passport? What extra document is required?", "en", "passport", "required_documents", "answerable",
     [[(PFR, "Autorisation du tuteur pour les mineurs"), (PAR, "ترخيص الولي بالنسبة للقصر")]], ""),
    # ---------------------------------------------------------------- national ID card
    ("N01", "Quelles pièces pour obtenir la carte d'identité nationale pour la première fois ?", "fr", "national_id", "required_documents", "answerable",
     [[(IDFR, "Extrait de naissance établi des registres originaux d'état civil datant de 3 mois au plus")]], ""),
    ("N02", "At what age must I get a national ID card?", "en", "national_id", "eligibility", "answerable",
     [[(IDFR, "Atteindre l'âge légal (18 ans)")]], ""),
    ("N03", "Que faut-il pour changer la carte d'identité après un mariage ?", "fr", "national_id", "required_documents", "answerable",
     [[(IDFR, "Extrait de naissance ou copie de l'acte de mariage pour la femme mariée")]], ""),
    ("N04", "Combien coûte le timbre pour remplacer une carte d'identité perdue ?", "fr", "national_id", "fees", "answerable",
     [[(IDFR, "Timbre fiscal de 25 dinars.")]], ""),
    # ---------------------------------------------------------------- birth certificate (no admissible source)
    ("B01", "Comment obtenir un extrait de naissance ?", "fr", "birth_certificate", "procedure_info", "unsupported", [],
     "idaraty.tn excluded (robots.txt AI opt-out); no birth-certificate procedure in the corpus."),
    ("B02", "كيف أستخرج مضمون ولادة؟", "ar", "birth_certificate", "procedure_info", "unsupported", [], "As B01."),
    ("B03", "How much does a birth certificate cost?", "en", "birth_certificate", "fees", "unsupported", [], "As B01."),
    ("B04", "kifech nekhou madhmoun wleda?", "derja", "birth_certificate", "procedure_info", "unsupported", [], "As B01."),
    # ---------------------------------------------------------------- RNE: formalities table, exact codes
    ("R01", "Combien coûte l'immatriculation d'une SARL ?", "fr", "business_registration", "fees", "answerable", [G_C012], ""),
    ("R02", "Quels sont les frais d'immatriculation d'une SUARL ?", "fr", "business_registration", "fees", "answerable", [G_C012],
     "SARL and SUARL share code RNE C 012."),
    ("R03", "What is the registration fee for a public limited company (SA)?", "en", "business_registration", "fees", "answerable",
     [[(TABLE, "Code procédure: RNE C 004")]], ""),
    ("R04", "Quel est le délai pour immatriculer une SARL ?", "fr", "business_registration", "processing_time", "answerable",
     [[(TABLE, "Trente jours à compter de la date de signature des statuts")]], ""),
    ("R05", "How much does it cost to register as a sole trader (commerçant)?", "en", "business_registration", "fees", "answerable",
     [[(TABLE, "Code procédure: RNE C 001")]], ""),
    ("R06", "Combien coûte l'immatriculation d'un artisan au RNE ?", "fr", "business_registration", "fees", "answerable",
     [[(TABLE, "Code procédure: RNE C 002")]], ""),
    ("R07", "À quoi correspond le code RNE M 004.03 ?", "fr", "business_registration", "procedure_info", "answerable",
     [[(TABLE, "Code procédure: RNE M 004.03")]], "Exact procedure code."),
    ("R08", "What is procedure code RNE C 025?", "en", "business_registration", "procedure_info", "answerable",
     [[(TABLE, "Code procédure: RNE C 025")]], "Exact procedure code."),
    ("R09", "Combien coûte le transfert du siège social d'une société ?", "fr", "business_registration", "fees", "answerable",
     [[(TABLE, "Code procédure: RNE M 004.03")]], ""),
    ("R10", "Combien coûte la radiation d'une société du registre ?", "fr", "business_registration", "fees", "answerable",
     [[(TABLE, "Code procédure: RNE M 004.36")]], ""),
    ("R11", "What is the fee for filing a company's financial statements with the RNE?", "en", "business_registration", "fees", "answerable",
     [[(TABLE, "Code procédure: RNE M 004.09")]], ""),
    ("R12", "قداش يكلف تسجيل شركة SARL؟", "derja", "business_registration", "fees", "answerable", [G_C012], ""),
    ("R13", "nheb nsajjel charika SUARL, 9adech el ma3loum?", "derja", "business_registration", "fees", "answerable", [G_C012], "Latin-script Derja"),
    # ---------------------------------------------------------------- RNE: fee decree 2022-298
    ("R14", "Quel est le montant de la redevance pour un extrait du registre de l'entreprise ?", "fr", "business_registration", "fees", "answerable",
     [[(FEES, "muni de la signature et du cachet électronique Extrait 10")]], ""),
    ("R15", "Y a-t-il une réduction des redevances du RNE pour les procédures faites en ligne ?", "fr", "business_registration", "fees", "answerable",
     [[(FEES, "Sont réduites de 50% les redevances afférentes aux procédures")]], ""),
    ("R16", "How can RNE fees be paid?", "en", "business_registration", "fees", "answerable",
     [[(FEES, "Virement bancaire ou postal au compte du Centre national du Registre des entreprises")]], ""),
    ("R17", "Can fees paid to the RNE be refunded?", "en", "business_registration", "fees", "answerable",
     [[(FEES, "Tout montant payé pour service rendu par le Centre national du Registre des entreprises ne peut être remboursé")]], ""),
    # ---------------------------------------------------------------- RNE: law 2018-52, decree-law 2022-18
    ("R18", "ما هي غرامة التأخير في التسجيل بالسجل الوطني للمؤسسات؟", "ar", "business_registration", "fees", "answerable",
     [[(LAW, "غرامة تأخير للمركز تحدد بنصف مبلغ المعلوم")]], "Law 2018-52 art. 51."),
    ("R19", "Quelle est la pénalité de retard pour une immatriculation tardive au RNE ?", "fr", "business_registration", "fees", "answerable",
     [[(LAW, "غرامة تأخير للمركز تحدد بنصف مبلغ المعلوم"), (DL18, "déterminées sur la base de la moitié du montant de la redevance due")]], ""),
    ("R20", "Que prévoit le décret-loi n° 2022-18 ?", "fr", "business_registration", "procedure_info", "answerable",
     [[(DL18, "une remise des pénalités de retard prévues par l’article 51 de la loi n° 2018-52")]], ""),
    ("R21", "Until when could companies benefit from the 2022 waiver of RNE late penalties?", "en", "business_registration", "procedure_info", "answerable",
     [[(DL18, "à compter du 1er avril 2022 jusqu’au 30 septembre 2022")]], ""),
    ("R22", "ما هي العقوبة على من تقاعس عن إتمام التسجيل بالسجل الوطني للمؤسسات؟", "ar", "business_registration", "procedure_info", "answerable",
     [[(LAW, "يعاقب بخطية من ألف دينار إلى خمسة آلاف دينار كل شخص تقاعس")]], "Law 2018-52 art. 53."),
    ("R23", "Dans quel délai peut-on contester une décision du Centre national du registre des entreprises ?", "fr", "business_registration", "processing_time", "answerable",
     [[(LAW, "يتم الطعن في قرارات المركز من كل ذي مصلحة في أجل سبعة أيام")]], "Law 2018-52 art. 44 (Arabic only)."),
    # ---------------------------------------------------------------- RNE: name reservation, beneficial owner
    ("R24", "كم تدوم صلاحية شهادة حجز التسمية الاجتماعية؟", "ar", "business_registration", "procedure_info", "answerable", [G_NAME6M], ""),
    ("R25", "Combien de temps est valable le certificat de réservation de la dénomination sociale ?", "fr", "business_registration", "procedure_info", "answerable", [G_NAME6M], ""),
    ("R26", "قداش تقعد صالحة شهادة حجز الاسم التجاري؟", "derja", "business_registration", "procedure_info", "answerable", [G_NAME6M], ""),
    ("R27", "When is the trade name reservation certificate issued?", "en", "business_registration", "processing_time", "answerable",
     [[(RESERV, "في نفس يوم تقديم المطلب")]], ""),
    ("R28", "من يعتبر مستفيدا حقيقيا من الشخص المعنوي؟", "ar", "business_registration", "procedure_info", "answerable", [G_BO20], ""),
    ("R29", "What shareholding threshold makes someone a beneficial owner?", "en", "business_registration", "procedure_info", "answerable", [G_BO20], ""),
    ("R30", "Dans quel délai le RNE statue-t-il sur une demande d'informations sur le bénéficiaire effectif ?", "fr", "business_registration", "processing_time", "answerable",
     [[(ARR, "dans un délai maximum de deux (2) jours")]], ""),
    ("R31", "Quelles informations sur le bénéficiaire effectif le public peut-il obtenir ?", "fr", "business_registration", "procedure_info", "answerable",
     [[(ARR, "le nom et prénom, - la nationalité, - le pays de résidence")]], ""),
    # ---------------------------------------------------------------- RNE: forms
    ("R32", "Quel formulaire remplir pour l'immatriculation d'une personne morale ?", "fr", "business_registration", "form_help", "answerable",
     [[(F002, "Représantant Légal")]], ""),
    ("R33", "Which form do I use to register as a natural person with the RNE?", "en", "business_registration", "form_help", "answerable",
     [[(F001, "DÉCLARATION D’IMMATRICULATION D’UNE PERSONNE PHYSIQUE")]], ""),
    # ---------------------------------------------------------------- RNE: unsupported
    ("R34", "Quelles pièces fournir pour créer une SARL ?", "fr", "business_registration", "required_documents", "unsupported", [],
     "No official required-documents checklist found on the RNE site (registry: rne-c012-c004-checklist-pdfs not_found)."),
    ("R35", "What documents are required to register an SUARL?", "en", "business_registration", "required_documents", "unsupported", [], "As R34."),
    ("R36", "Quel est le montant de la redevance du code RNE C 014 ?", "fr", "business_registration", "fees", "unsupported", [],
     "Code RNE C 014 does not exist in the official table (registry: rne-c014-beneficial-owner-form not_found)."),
    # ---------------------------------------------------------------- ambiguous
    ("A01", "passeport", "fr", "passport", "procedure_info", "ambiguous", [[(PFR, None), (PAR, None)]], "Single keyword."),
    ("A02", "How much does it cost?", "en", None, None, "ambiguous", [], "No procedure named."),
    ("A03", "nheb na3mel charika", "derja", "business_registration", "procedure_info", "ambiguous", [[(TABLE, None)]], "Company type not specified."),
    # ---------------------------------------------------------------- out of scope
    ("O01", "Quelle est la météo à Tunis demain ?", "fr", "none", "out_of_scope", "out_of_scope", [], ""),
    ("O02", "Recommend a good restaurant in Sousse", "en", "none", "out_of_scope", "out_of_scope", [], ""),
    ("O03", "ما هي عاصمة اليابان؟", "ar", "none", "out_of_scope", "out_of_scope", [], ""),
    ("O04", "Comment obtenir un permis de conduire ?", "fr", "none", "out_of_scope", "unsupported", [], "Procedure not covered by the corpus."),
    ("O05", "How do I apply for a Tunisian visa as a foreigner?", "en", "none", "out_of_scope", "unsupported", [], "Procedure not covered by the corpus."),
    # ---------------------------------------------------------------- parallel multilingual subset
    # The same verified fact asked in every query language (see PARALLEL below), so that per-language
    # retrieval quality is compared on identical information needs.
    ("M01", "Quelles pièces fournir pour renouveler un passeport ?", "fr", "passport", "required_documents", "answerable", [G_RENEW], ""),
    ("M02", "How long does it take to get a passport?", "en", "passport", "processing_time", "answerable", [G_DELAY], ""),
    ("M03", "ما هو أجل الحصول على جواز السفر؟", "ar", "passport", "processing_time", "answerable", [G_DELAY], ""),
    ("M04", "قداش ياخو وقت باش نخرج الباسبور؟", "derja", "passport", "processing_time", "answerable", [G_DELAY], ""),
    ("M05", "How much does it cost to register an SARL?", "en", "business_registration", "fees", "answerable", [G_C012], ""),
    ("M06", "ما هو معلوم تسجيل شركة ذات مسؤولية محدودة بالسجل الوطني للمؤسسات؟", "ar", "business_registration", "fees", "answerable", [G_C012], ""),
    ("M07", "How long is a trade name reservation certificate valid?", "en", "business_registration", "procedure_info", "answerable", [G_NAME6M], ""),
    ("M08", "9adech tab9a s7i7a chhedet 7ajz el esm?", "derja", "business_registration", "procedure_info", "answerable", [G_NAME6M], "Latin-script Derja"),
    ("M09", "Quel seuil de participation définit le bénéficiaire effectif ?", "fr", "business_registration", "procedure_info", "answerable", [G_BO20], ""),
    ("M10", "chkoun yet7seb moustafid 7a9i9i fel charika?", "derja", "business_registration", "procedure_info", "answerable", [G_BO20], "Latin-script Derja"),
    ("M11", "What is the late registration penalty at the RNE?", "en", "business_registration", "fees", "answerable",
     [[(LAW, "غرامة تأخير للمركز تحدد بنصف مبلغ المعلوم"), (DL18, "déterminées sur la base de la moitié du montant de la redevance due")]], ""),
    ("M12", "9adech el khtiya ki nfout el ajal mta3 tasjil fel RNE?", "derja", "business_registration", "fees", "answerable",
     [[(LAW, "غرامة تأخير للمركز تحدد بنصف مبلغ المعلوم"), (DL18, "déterminées sur la base de la moitié du montant de la redevance due")]], "Latin-script Derja"),
    ("M13", "Where do I submit a passport application if I live abroad?", "en", "passport", "submission_place", "answerable",
     [[(PFR, "Ambassade ou consulat ou représentation diplomatique de la Tunisie"), (PAR, "السفارة أو القنصلية")]], ""),
    ("M14", "أين أودع ملف جواز السفر إذا كنت مقيما بالخارج؟", "ar", "passport", "submission_place", "answerable",
     [[(PFR, "Ambassade ou consulat ou représentation diplomatique de la Tunisie"), (PAR, "السفارة أو القنصلية")]], ""),
    ("M15", "win nhot dossier el passbor ki nkoun 3ayech barra?", "derja", "passport", "submission_place", "answerable",
     [[(PFR, "Ambassade ou consulat ou représentation diplomatique de la Tunisie"), (PAR, "السفارة أو القنصلية")]], "Latin-script Derja"),
]

# Held-out validation set (written 2026-10-16, after all retrieval and routing tuning on ITEMS).
# It uses official facts that do not appear in ITEMS and is never used to choose or tune components:
# it is only measured, before and after changes made on the development set.
HELDOUT = [
    ("H01", "What proof is required for a passport if I live abroad?", "en", "passport", "required_documents", "answerable",
     [[(PFR, "Tout document prouvant la résidence réglementaire à l'étranger"), (PAR, "ما يفيد الإقامة بصفة قانونية بالخارج")]], ""),
    ("H02", "How long does it take to replace a lost passport?", "en", "passport", "processing_time", "answerable",
     [[(PFR, "Après l'accomplissement de l'enquête et des procédures nécessaires"), (PAR, "بعد استكمال التحريات وإتمام الإجراءات اللازمة")]], ""),
    ("H03", "En combien de temps obtient-on le document de voyage pour le pèlerinage ?", "fr", "passport", "processing_time", "answerable",
     [[(PFR, "Immédiatement ou dans les 24 heures à compter de la date du dépôt du dossier"), (PAR, "حينيا أو خلال 24 ساعة من تقديم الملف")]], ""),
    ("H04", "Quelles pièces pour renouveler la carte d'identité nationale ?", "fr", "national_id", "required_documents", "answerable",
     [[(IDFR, "Copie de la carte à renouveler avec présentation de l'originale")]], ""),
    ("H05", "Do I need a residence certificate for my first national ID card?", "en", "national_id", "required_documents", "answerable",
     [[(IDFR, "Attestation de résidence,")]], ""),
    ("H06", "dhaya3tli el karta, chnowa lezmni?", "derja", "national_id", "required_documents", "answerable",
     [[(IDFR, "Attestation de déclaration de perte,")]], "Latin-script Derja"),
    ("H07", "أين أودع ملف بطاقة التعريف الوطنية؟", "ar", "national_id", "submission_place", "answerable",
     [[(IDFR, "Poste de la police ou de la garde nationale du lieu de résidence du demandeur")]], "Answer exists only in French."),
    ("H08", "What is the fee to register a permanent establishment with the RNE?", "en", "business_registration", "fees", "answerable",
     [[(TABLE, "Code procédure: RNE C 006")]], ""),
    ("H09", "Combien coûte l'enregistrement d'une cession de parts sociales ?", "fr", "business_registration", "fees", "answerable",
     [[(TABLE, "Code procédure: RNE M 004.12")]], ""),
    ("H10", "Quel est le montant pour l'inscription d'un nantissement au registre ?", "fr", "business_registration", "fees", "answerable",
     [[(TABLE, "Code procédure: RNE I 001"), (TABLE, "Code procédure: RNE I 002")]], ""),
    ("H11", "How much does remote consultation of the beneficial owners register cost?", "en", "business_registration", "fees", "answerable",
     [[(FEES, "Consultation à distance du registre des bénéficiaires effectifs Identifiant unique 5")]], ""),
    ("H12", "Les redevances du RNE sont-elles toutes taxes comprises ?", "fr", "business_registration", "fees", "answerable",
     [[(FEES, "s'entendent en toutes taxes comprises")]], ""),
    ("H13", "ماذا يحدث في صورة العود في عدم إتمام التسجيل بالسجل الوطني للمؤسسات؟", "ar", "business_registration", "procedure_info", "answerable",
     [[(LAW, "وفي صورة العود تضاعف الخطية")]], ""),
    ("H14", "What is the penalty for making a false declaration to the National Business Register?", "en", "business_registration", "procedure_info", "answerable",
     [[(LAW, "يعاقب بالسجن مدة خمس سنوات وبخطية قدرها خمسون ألف دينار")]], "Answer exists only in Arabic."),
    ("H15", "Le RNE publie-t-il la liste des dénominations réservées ?", "fr", "business_registration", "procedure_info", "answerable",
     [[(RESERV, "ينشر المركز الوطني لسجل المؤسسات بصفة يومية قائمة")]], "Answer exists only in Arabic."),
    ("H16", "How do the competent authorities access beneficial owner information at the RNE?", "en", "business_registration", "procedure_info", "answerable",
     [[(ARR, "met, en temps réel, à la disposition des autorités compétentes")]], ""),
    ("H17", "Comment renouveler une carte grise ?", "fr", "none", "out_of_scope", "unsupported", [], "Vehicle registration: not in the corpus."),
    ("H18", "كيف أحصل على بطاقة عدد 3؟", "ar", "none", "out_of_scope", "unsupported", [], "Criminal record extract: not in the corpus."),
    ("H19", "kifech nekhou chhedet sokna?", "derja", "none", "out_of_scope", "unsupported", [],
     "Residence certificate: only mentioned as a supporting document; how to obtain it is not in the corpus."),
    ("H20", "What is the RNE fee for procedure code RNE C 099?", "en", "business_registration", "fees", "unsupported", [],
     "Code RNE C 099 does not exist in the official table."),
]

G_ID_RENEW = [(IDFR, "Copie de la carte à renouveler avec présentation de l'originale")]
G_LOSS = [(PFR, "Attestation de déclaration de perte du passeport"), (PAR, "شهادة ضياع جواز السفر")]

# Regression set for the two failure types discovered on the held-out set (H17: topic confusion,
# H14: unsupported number). Written 2026-10-16 before the evidence verifier was implemented. Topic items
# pair unsupported procedures with answerable "twins" phrased the same way, so that both false
# acceptances and false refusals are measured. R-N1 repeats H14 and RT1 repeats H17 on purpose.
REGRESSION = [
    ("RT1", "Comment renouveler une carte grise ?", "fr", "none", "out_of_scope", "unsupported", [], "= H17; vehicle registration."),
    ("RT2", "Quelles pièces pour obtenir un permis de conduire ?", "fr", "none", "out_of_scope", "unsupported", [], "Driving licence."),
    ("RT3", "How do I renew my driving licence in Tunisia?", "en", "none", "out_of_scope", "unsupported", [], "Driving licence."),
    ("RT4", "كيف أجدد رخصة السياقة؟", "ar", "none", "out_of_scope", "unsupported", [], "Driving licence."),
    ("RT5", "Comment obtenir une carte de séjour pour un étranger ?", "fr", "none", "out_of_scope", "unsupported", [], "Residence card for foreigners."),
    ("RT6", "What documents do I need for a vehicle registration certificate?", "en", "none", "out_of_scope", "unsupported", [], "Vehicle registration."),
    ("RT7", "Comment obtenir un extrait de casier judiciaire ?", "fr", "none", "out_of_scope", "unsupported", [], "Criminal record."),
    ("RP1", "Comment renouveler la carte d'identité nationale ?", "fr", "national_id", "required_documents", "answerable", [G_ID_RENEW], "Twin of RT1."),
    ("RP2", "How do I renew my passport in Tunisia?", "en", "passport", "required_documents", "answerable", [G_RENEW], "Twin of RT3."),
    ("RP3", "كيف أجدد بطاقة التعريف الوطنية؟", "ar", "national_id", "required_documents", "answerable", [G_ID_RENEW], "Twin of RT4; French-only evidence."),
    ("RP4", "Que faut-il pour un duplicata de passeport après une perte ?", "fr", "passport", "required_documents", "answerable", [G_LOSS], ""),
    ("RN1", "What is the penalty for making a false declaration to the National Business Register?", "en", "business_registration", "procedure_info", "answerable",
     [[(LAW, "يعاقب بالسجن مدة خمس سنوات وبخطية قدرها خمسون ألف دينار")]], "= H14; amount written in Arabic words."),
    ("RN2", "What fine applies to someone who fails to complete RNE registration?", "en", "business_registration", "fees", "answerable",
     [[(LAW, "يعاقب بخطية من ألف دينار إلى خمسة آلاف دينار كل شخص تقاعس")]], "Amounts written in Arabic words."),
    ("RN3", "Quelle amende pour une déclaration incomplète au registre national des entreprises ?", "fr", "business_registration", "fees", "answerable",
     [[(LAW, "تعمد الإدلاء ببيانات منقوصة")]], "Law 2018-52 art. 54."),
    ("RN4", "How long is the deadline to appeal a decision of the RNE centre?", "en", "business_registration", "processing_time", "answerable",
     [[(LAW, "في أجل سبعة أيام")]], "Law 2018-52 art. 44; number written in words."),
]

# Untouched test set: written 2026-10-16 before the evidence verifier was implemented, evaluated once at
# the end and never used to design or tune anything.
TEST = [
    ("T01", "Quel est le délai d'obtention de la carte d'identité nationale pour la première fois ?", "fr", "national_id", "processing_time", "answerable",
     [[(IDFR, "Dans les 15 jours à partir de la date de dépôt de la demande")]], ""),
    ("T02", "Is a blood group certificate mandatory for the national ID card?", "en", "national_id", "required_documents", "answerable",
     [[(IDFR, "Certificat indiquant le groupe sanguin (facultatif).")]], ""),
    ("T03", "ما هي شروط تغيير جواز السفر؟", "ar", "passport", "eligibility", "answerable",
     [[(PAR, "حصول تغيير في أحد عناصر الهوية"), (PFR, "Changement d'un élément de l'identité")]], ""),
    ("T04", "9adech yekhou wa9t el passbor ki nkoun 3ayech barra?", "derja", "passport", "processing_time", "answerable",
     [[(PAR, "خلال 15 يوما من تاريخ تقديم الطلب"), (PFR, "Dans les 15 jours à compter de la date de dépôt de la demande")]], "Latin-script Derja"),
    ("T05", "Combien coûte la transformation de la forme juridique d'une société ?", "fr", "business_registration", "fees", "answerable",
     [[(TABLE, "Code procédure: RNE M 004.13")]], ""),
    ("T06", "What is the RNE fee for opening a branch of a company?", "en", "business_registration", "fees", "answerable",
     [[(TABLE, "Code procédure: RNE M 004.04"), (TABLE, "Code procédure: RNE M 004.05")]], ""),
    ("T07", "Quel est le tarif d'une copie conforme des états financiers déposés au registre ?", "fr", "business_registration", "fees", "answerable",
     [[(FEES, "Copie conforme à l’original des états financiers et des documents comptables")]], ""),
    ("T08", "Who can consult the documents of the beneficial owners register?", "en", "business_registration", "procedure_info", "answerable",
     [[(FEES, "exclusivement réservée aux personnes prévues par l’article 107")]], ""),
    ("T09", "ما هي البيانات التي تتضمنها شهادة حجز التسمية الاجتماعية؟", "ar", "business_registration", "procedure_info", "answerable",
     [[(RESERV, "تتضمن شهادة الحجز وجوبا البيانات التالية")]], ""),
    ("T10", "Can entities subject to customer due diligence obtain beneficial owner information from the RNE?", "en", "business_registration", "procedure_info", "answerable",
     [[(ARR, "assujetties à l’obligation de diligence envers leurs clients")]], ""),
    ("T11", "Comment obtenir une attestation de travail ?", "fr", "none", "out_of_scope", "unsupported", [],
     "Mentioned only as a supporting document; how to obtain it is not in the corpus."),
    ("T12", "How do I register a trademark in Tunisia?", "en", "none", "out_of_scope", "unsupported", [], ""),
    ("T13", "كيف أحصل على رخصة بناء؟", "ar", "none", "out_of_scope", "unsupported", [], "Building permit."),
    ("T14", "kifech nsajjel wildi fel bladiya?", "derja", "none", "out_of_scope", "unsupported", [], "Birth registration at the municipality."),
]

# Second untouched test set: written 2026-10-16 after the first verifier version had been evaluated and
# before the deterministic topic rule was implemented. Its questions avoid the procedure keywords, so they
# exercise the LLM-routed path that the topic verifier guards. Evaluated once, never used for tuning.
TEST2 = [
    ("U01", "Que fixe l'arrêté du 13 janvier 2026 ?", "fr", "business_registration", "procedure_info", "answerable",
     [[(ARR, "fixant la procédure d’obtention des informations relatives au bénéficiaire effectif")]], ""),
    ("U02", "Quelles mentions doivent obligatoirement figurer au registre selon la loi 2018-52 ?", "fr", "business_registration", "procedure_info", "answerable",
     [[(LAW, "يقع التنصيص بالسجل وجوبا على")]], "Answer only in Arabic."),
    ("U03", "متى يجب تقديم مطلب التشطيب بعد التوقف النهائي عن النشاط؟", "ar", "business_registration", "processing_time", "answerable",
     [[(LAW, "في أجل أقصاه شهر من تاريخ التوقف النهائي عن نشاطه")]], ""),
    ("U04", "Le paiement peut-il se faire par mandat postal ?", "fr", "business_registration", "fees", "answerable",
     [[(FEES, "Mandat postal au nom du Centre national du Registre des entreprises")]], ""),
    ("U05", "Can amounts paid in excess be refunded by the centre?", "en", "business_registration", "fees", "answerable",
     [[(FEES, "Les montants indûment perçus ou le trop-perçu des redevances, peuvent être remboursés")]], ""),
    ("U06", "chnowa yhdef el 9anoun 52 mta3 2018?", "derja", "business_registration", "procedure_info", "answerable",
     [[(LAW, "تدعيم شفافية المعاملات الاقتصادية")]], "Latin-script Derja"),
    ("U07", "Comment obtenir une patente de taxi ?", "fr", "none", "out_of_scope", "unsupported", [], "Taxi licence."),
    ("U08", "Comment renouveler une carte d'handicapé ?", "fr", "none", "out_of_scope", "unsupported", [], "Disability card."),
    ("U09", "كيف أحصل على شهادة الإقامة؟", "ar", "none", "out_of_scope", "unsupported", [],
     "Residence certificate: its words occur in the corpus (as a supporting document) but the procedure does not."),
    ("U10", "Quelles pièces pour une demande de bourse universitaire ?", "fr", "none", "out_of_scope", "unsupported", [],
     "University grant: 'bourse' and 'universitaire' occur in the corpus in other senses."),
    ("U11", "How do I get a tax identification number?", "en", "none", "out_of_scope", "unsupported", [], ""),
    ("U12", "kifech nekhou permis de chasse?", "derja", "none", "out_of_scope", "unsupported", [], "Hunting permit."),
]

# Parallel groups: one information need, asked in several languages (ids of the items above).
PARALLEL = {
    "renew_documents": ["M01", "P02", "P03", "P04", "P05"],
    "passport_delay": ["P10", "M02", "M03", "M04", "P16"],
    "sarl_fee": ["R01", "M05", "M06", "R12", "R13"],
    "name_reservation_validity": ["R25", "M07", "R24", "R26", "M08"],
    "beneficial_owner_threshold": ["M09", "R29", "R28", "M10"],
    "late_penalty": ["R19", "M11", "R18", "M12"],
    "abroad_submission_place": ["P09", "M13", "M14", "M15"],
    "birth_certificate_unsupported": ["B01", "B03", "B02", "B04"],
}
PARALLEL_OF = {qid: name for name, ids in PARALLEL.items() for qid in ids}


def build(items, filename: str, split: str, manifest, blocks) -> None:
    out, problems = [], []
    for qid, question, lang, category, intent, answerability, groups, note in items:
        ev_groups, verified = [], True
        for group in groups:
            alts = []
            for doc_id, evidence in group:
                rec = manifest.get(doc_id)
                alt = {"doc_id": doc_id, "evidence": evidence, "source_url": rec.url if rec else None,
                       "official_reference": rec.official_reference if rec else None, "page": None, "reference_extract": None}
                if evidence is not None:
                    hit = next((b for b in blocks.get(doc_id, []) if norm(evidence) in norm(b["text"])), None)
                    if hit is None:
                        verified = False
                        problems.append(f"{qid}: evidence not found in {doc_id}: {evidence!r}")
                    else:
                        alt["page"] = hit.get("page")
                        alt["reference_extract"] = hit["text"]  # verbatim official block
                alts.append(alt)
            ev_groups.append(alts)
        status = "UNVERIFIED" if not verified else (
            "no_answer_in_corpus" if not groups else
            "verified_evidence" if all(a["evidence"] for g in ev_groups for a in g) else "document_level_only")
        out.append({
            "id": qid, "question": question, "language": lang, "expected_category": category,
            "expected_intent": intent, "answerability": answerability, "evidence_groups": ev_groups,
            "verification_status": status, "human_review": "pending", "note": note,
            "parallel_group": PARALLEL_OF.get(qid), "split": split,
            "script": "latin" if lang == "derja" and not any("؀" <= c <= "ۿ" for c in question) else None,
        })
    path = ROOT / "data" / "evaluation" / filename
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n", encoding="utf-8")
    by_status = {}
    for r in out:
        by_status[r["verification_status"]] = by_status.get(r["verification_status"], 0) + 1
    print(f"wrote {len(out)} items to {path.relative_to(ROOT)}: {by_status}")
    for p in problems:
        print("PROBLEM", p)


def main() -> None:
    manifest = Manifest(ROOT / "data" / "raw" / "manifest.json").records
    blocks = {f.stem: json.loads(f.read_text(encoding="utf-8"))
              for f in (ROOT / "data" / "processed" / "extracted").glob("*.json")}
    build(ITEMS, "eval_set.jsonl", "dev", manifest, blocks)
    build(HELDOUT, "heldout_set.jsonl", "heldout", manifest, blocks)
    build(REGRESSION, "regression_set.jsonl", "regression", manifest, blocks)
    build(TEST, "test_set.jsonl", "test", manifest, blocks)
    build(TEST2, "test2_set.jsonl", "test2", manifest, blocks)


if __name__ == "__main__":
    main()
