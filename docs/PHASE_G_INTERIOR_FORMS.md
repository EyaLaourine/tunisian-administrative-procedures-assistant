# Phase G: Interior CIN and passport application forms (01.pdf, 02.pdf)

Status: implemented and validated on branch `fix/phase-g` (based on the undeployed `fix/phase-f`).
**Not deployed.** Production (backend `rc-20261018-e`) was not modified.

## 1. The two files

| | 01.pdf | 02.pdf |
|---|---|---|
| sha256 | `1ccece129f681dc936c65ea22921bc83e69760d2607d58a71fb6bb9731d2fe63` | `7e667ead43869ad17d8a9ac5b881dd3bf27afce9e8d3cdae5a5e8341d598168d` |
| Size, pages | 40,619 bytes, 2 pages (A4) | 48,909 bytes, 2 pages (A4) |
| PDF metadata | title "01 - CIN.pdf", Word 2007 -> Acrobat Distiller 9.0, created 2014-01-03 | title "02 - passeport.pdf", same tools, created 2014-01-03 |
| Printed title | مطلب … بطاقة التعريف الوطنيـة (لأول مرّة / ضياع / تعويض) | مطلب جواز سفر عادي (لأول مرّة / تمديد / تجديد / تعويض) |
| Printed reference | IL.01-12/2013, وزارة الداخلية – الإدارة العامة للأمن الوطني | IL.02-12/2013, same header |
| Content | Blank form (dot leaders, boxes); no form widgets | Blank form; Arabic labels with French translations |
| Text layer | Yes: 170 + 117 = 287 words (Arabic presentation forms, normalised by NFKC) | Yes: 303 + 120 = 423 words |

Layout (from the printed text):

- **CIN, page 1**:
  - Applicant part: y 192–450, covering identity, birth, mother, spouse, profession, address, governorate, previous ID, blood group, donor and signature ("التوقيع وجوبي").
  - Administration: "بيانـات خاصة بالإدارة" from y 475 (fingerprint, file entry, deposit receipt).
  - Page 2: administration only.
- **Passport, page 1**:
  - Applicant part: y 220–640, covering CIN number, names, birth, profession, height, eye colour, sex, other nationalities, address boxes, marital status, spouse, and place/date ("حرر بـ … في"). The signature is mandatory: "(**) التوقيع وجوبي داخل الخانة".
  - Administration: "خــاص بالإدارة" from y 662 (old/new passport references, deposit receipt).
  - Page 2: "بيانات خاصة بالإدارة" only.
- On both forms `(*)` means "tick the right box" ("توضع علامة X على المربع الصحيح"). **Neither form prints any field as optional.**

### Provenance

- The official site `https://services.interieur.gov.tn/` lists, under "مطبوعات على الخط":
  - `uploads/imprimes/01.pdf` as "بطاقة التعريف الوطنية";
  - `uploads/imprimes/02.pdf` as "جواز السفر".
- `robots.txt` allows `/` but disallows `/uploads/imprimes/01.pdf` and `/uploads/imprimes/02.pdf`, so the crawler never fetched them and must not. The files were not fetched in this phase either.
- **Not verifiable:** byte identity of the user's copies with the server files, because fetching them is disallowed. The printed header, reference numbers and file names match the official listing.
- Registry metadata therefore stays `language: unknown`, `publication_date: null` and `applicability: unverified`. The manifest records `retrieval_method: manual` (`ingestion.manual_import`, the tool intended for robots-blocked printable forms).

## 2. Root cause of the rejections

The production log has two entries:
- `16:03:29`: `form_check method=text_layer words=287`, not recognised;
- `16:03:41`: `words=423`, not recognised.

The word counts are exactly those of 01.pdf and 02.pdf.

1. **No template existed for either form.** `FormHelper.templates()` (`agents/form_helper.py`) only builds templates from manifest records with `document_type: official_form` **and a stored PDF**. In production:
   - `interior-passport-application-form` is registered but has `file_path: null`, with error "robots.txt disallows this user agent";
   - the CIN form was **not registered at all**;
   - so only RNE F-001 and F-002 were candidates.
2. Against those two templates the production code scores:
   - 01.pdf: F-001 0.231, F-002 0.148;
   - 02.pdf: F-001 0.462, F-002 0.296.

   Both are below `MIN_MATCH = 0.5`, so the reply was `form_unknown`. 02.pdf came close to F-001 only through the shared bilingual labels (Prénom, Nom, …).
3. **Not causes:**
   - Text extraction works: text layer present, and presentation forms are normalised by `norm_token` (NFKC).
   - MIME type and size were accepted.

Problems found on the way (these would have appeared once templates existed):

- **Administration fields would have been reported missing:**
  - CIN: 7 of 21 derived fields;
  - passport: 14 of 28 (deposit receipts, centre, registration number, page 2).
- **Scanned copies would still have failed.** Tesseract `--psm 4` reads a page as one column and drops whole Arabic label columns on these two-column forms. Scans scored 0.18–0.40.
- **Several derived labels merged neighbouring printed text** (e.g. "عنوان السكنى الفصيلة الدموية"). Checkbox/box items (date of birth, sex, marital status, blood group, donor, CIN number, passport address boxes) and the signature are not dot leaders, so the check cannot see them.
- **Latent bug:** `check_ink` compared every field against the first page, including page-2 fields. It is now limited to page-1 fields; the others are `not_found`.

## 3. Changes (`fix/phase-g`)

| File | Change |
|---|---|
| `config/sources.yaml` | New `interior-national-id-application-form` (`uploads/imprimes/01.pdf`, title as listed, `official_form`, `national_id`, language unknown, date null). |
| `data/raw/…/1ccece129f68_01.pdf`, `…/7e667ead4386_02.pdf`, `manifest.json` | Both official files stored by `ingestion.manual_import`. |
| `agents/form_roles.py` (new) | Field roles: `required`, `optional`, `conditional`, `administration`. See below. |
| `agents/form_helper.py` | Roles carried on each field; reply and OCR changes. See below. |
| `agents/schemas.py` | `FormField.role`; `FormCheckResult.if_applicable`. `missing` now means empty **required applicant** fields. |
| `agents/i18n.py` | `form_unknown` takes `{forms}`; new keys `form_if_applicable`, `form_required_complete`, `form_not_checked`, `form_admin_skipped`; `FORM_NAMES` (FR/EN/AR/Derja). |
| `tests/test_phase_g_forms.py` (new), `tests/test_phase_f.py` | 24 Phase G tests. The two D5 download tests now expect the verified links (both files are now in the verified corpus). |

**`agents/form_roles.py`:**
- **Administration** = every field after a printed "خاص/خاصة بالإدارة" (or "réservé à l'administration") heading, on that page and the following pages. The heading is matched on the whole line, because a tatweel splits "خــاص" into several extracted words.
- **Per-file rules**, pinned by sha256 and guarded by the expected derived label (a mismatch falls back to the generic rule): the printed label shown to the user, plus conditional/optional roles.

**`agents/form_helper.py`:**
- **Roles:** they are carried on every field.
- **Reply contents:**
  - empty required fields;
  - empty conditional fields, under "if applicable";
  - printed items the check cannot see (boxes, checkboxes, signature);
  - the number of administration fields ignored.
- **Unrecognised uploads:** the reply names every supported form.
- **OCR fallback:** a sparse-text pass (`--psm 11`, first page) runs only when the psm 4 reading matches no form or cannot be aligned on Latin anchors. Alignment may then use Arabic anchor words.
- **Line fallback:** printed words never count as entered values.

### Field roles

Only the signature is printed as mandatory. No field is printed as optional or conditional. The conditional roles below follow from the meaning of the printed labels (and the CIN "لأول مرّة" option); they are not printed rules.

| Form | Required (applicant) | Conditional ("if applicable") | Optional | Administration-only |
|---|---|---|---|---|
| CIN | اللقب, الإسم, إسم الأب, إسم الجد, تاريخ الولادة — مكانها, إسم الأم, إسم الأم — لقبها, المهنة, عنوان السكنى, الولاية (10) | إسم الزوج(ة), لقبه(ها) (married applicants); الهوية القديمة (none on a first application) | unlabelled 2nd address line (1) | 7: حرر الملف في, عدد, deposit receipt (لصاحبه(ها), سجل تحت عدد بتاريخ المركز), page 2 |
| Passport | Prénom / الإسم, Prénom du père, Prénom du grand-père, Nom de famille, Nom et prénom de la mère, مكان الولادة — ولايتها, Profession, حرر بـ … في, القامة, لون العينين (10) | spouse first name, surname, nationality; جنسيات أخرى (only holders of other nationalities) | – | 14: deposit receipt (y ≥ 774), page 2 |
| Not checked (shown to the user) | CIN: تاريخ الولادة, الجنس, الحالة العائلية, الفصيلة الدموية, متبرع, التوقيع. Passport: CIN number, تاريخ الولادة, الجنس, Adresse/العنوان, الحالة العائلية, التوقيع | | | |

**Interpretations (labelled as such, not printed rules):**
- "حرر بـ … في" (passport) is treated as the applicant's place and date: it sits in the applicant part above the administration heading.
- The CIN row at y 359 (x 320–561) is an unlabelled continuation of the address line (confirmed on the rendered page).

**RNE F-001/F-002 are unchanged:**
- they have no administration heading and no per-file rules, so every field stays `required`;
- the dossier validator keeps its quoted "all fields" requirement.

## 4. Test results

**Unit suite** (`pytest -m "not integration"`, worktree): **1399 passed, 7 skipped, 0 failed.**
- Skips:
  - 5 pre-existing private-backup tests;
  - 2 Phase G OCR tests, which need tesseract and were run in the image.
- In the candidate image (tesseract 5.5.0): `tests/test_phase_g_forms.py` + `tests/test_form_helper_and_answer.py` = **32 passed**, OCR included.

**Copies tested** (all synthetic completed copies use the neutral word "Placeholder"):

| Case | CIN | Passport |
|---|---|---|
| User's original 01.pdf / 02.pdf (blank, text layer) | recognised, score 1.0; 10 required listed, 3 if applicable, 7 admin ignored | recognised, score 1.0; 10 required, 4 if applicable, 14 admin ignored |
| Required fields filled | missing 0; conditional listed | missing 0; conditional listed |
| Every applicant field filled | missing 0, if-applicable 0; admin fields stay empty and are not reported | same |
| Half the required fields filled | exactly the other half reported | same |
| Only administration fields filled | all 10 required reported | same |
| CIN vs passport confusion | none (each completed copy -> its own form) | none |

**Scanned copies** (OCR, candidate image):
- Blank, required-filled and fully-filled copies were each rendered as a grey PNG and as an image-only PDF (JPEG q85), at 150, 200 and 300 dpi: 36 cases per form family.

| Result | CIN | Passport |
|---|---|---|
| Recognised as the right form | 18/18 (scores 0.515–0.818) | 18/18 (0.508–0.698) |
| Blank scans: all 10 required reported, no false "filled" | 6/6 | 6/6 |
| Completed scans: exact result | 10/12 | 12/12 |
| Errors | 150 dpi JPEG PDF: 3 wide rows (اللقب, الإسم, المهنة) falsely "look empty" (conservative direction) | – |

- Lossless 300 dpi PNG-in-PDF uploads (17 MB) are refused by the existing 10 MB limit, with the localised size message.
- **RNE scans:** the same 36 RNE cases give **identical results** on the Phase F image and on the Phase G code. That includes the pre-existing false "looks empty" results on short single-word entries (2–5 fields), a limitation of the ink threshold that this phase did not change.
- **Before this phase**, the same Interior scans scored 0.18–0.40 and were never recognised.

**Isolated end to end** (network `lang-iso`; disposable Qdrant restored from the Phase A snapshot; candidate backend; disposable n8n with the unchanged WF02/WF03; Telegram API mocked):
- Results are in section 6.

## 5. Limitations

- **Recognition margin:** scanned passport copies scored as low as 0.508 against the 0.5 threshold. Darker, skewed or low-resolution photos may still be rejected; the reply then lists the supported forms.
- **What the check sees:** only dot-leader fields. Boxes, checkboxes and the signature are listed for the user to check. Handwriting is judged only by ink, never read.
- **Interpretations:** conditional roles and the passport "حرر بـ … في" role are interpretations of the printed labels (section 3).
- **Search index:** the two forms are not in the Qdrant index. No indexing was run (`/index/run` is never called). Form recognition and the download link only need the manifest.
- **Provenance:** byte identity with the server files cannot be verified without fetching them (disallowed by robots.txt).

## 6. Isolated end-to-end results

Candidate backend image `rc-20261018-g` = `sha256:4d79b517a890…` (commit `3d84557`), 2026-10-18 18:01–18:06Z, plus a rerun
of the Phase F/G session after fixing a test fixture:

| Suite | Result |
|---|---|
| Coverage (all capabilities) | 60/60 turns |
| Conversational | 22/22 |
| Language (FR/AR/Derja/EN, AUTO) | 26/26 |
| Phase F real-session replay + Phase G uploads | 30/30 (first run 28/29: a PNG fixture sent as a Telegram *photo* was refused by the bridge's JPEG signature check, which is correct, since Telegram photos are always JPEG; the fixture was regenerated as JPEG) |
| Defect probes | 16/16 |
| WF02 retrieval with valid official citations | 5/5, median 500 ms |

Phase G turns through the bridge -> n8n WF03 -> backend:
- **Blank official files:**
  - 01.pdf: recognised, 10 required, 3 if applicable, "7 champs réservés à l'administration ont été ignorés", no administration label shown;
  - 02.pdf: same pattern with 10 / 4 / 14.
- **Completed copies:**
  - required-only CIN copy: no missing fields;
  - fully completed passport: no missing fields, no "if applicable" list.
- **Scans (OCR):**
  - scanned completed CIN (JPEG PDF): no missing fields, 9.8 s;
  - photographed blank passport (JPEG): recognised, 3.8 s;
  - photographed completed CIN: no missing fields, 3.3 s.
- **RNE:** F-001 is still recognised.
- **Downloads:** download questions for the passport and CIN forms return the verified official links.
- **Unrecognised file:** the reply names all four supported forms.

Backend log of the candidate:
- 825 lines;
- no placeholder text, no form labels and no base64 content (privacy rule);
- no errors.

The isolated containers and network were removed afterwards. Production containers were never touched.

## 7. Deployment proposal (requires approval)

The production backend bind-mounts `./data` and `./config` from the production checkout.

1. Back up `data/raw/manifest.json` and `config/sources.yaml` of the production checkout.
2. Bring in the registry entry and the stored files, either:
   - **(a)** run `python -m ingestion.manual_import` for both doc_ids with the user's two files, **or**
   - **(b)** copy the two `data/raw/interior-*-application-form/` folders and the two manifest records from `fix/phase-g`.
3. Recreate the backend from image `tunisian-admin-assistant-backend:rc-20261018-g`. This image **also contains the undeployed Phase F changes**, so approving it deploys F and G together.
4. Verify:
   - `/health`;
   - the blank 01.pdf/02.pdf through the bot (recognised; administration fields ignored);
   - RNE F-001 still recognised.
5. **Rollback:** restore both files and recreate the backend with `rc-20261018-e`.

No n8n workflow, bridge, Qdrant or prompt change is needed.
