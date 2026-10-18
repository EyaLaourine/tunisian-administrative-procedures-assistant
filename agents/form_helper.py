"""Form-Filling Helper agent: recognise an official form in an upload and list empty fields.

Privacy: the upload is processed in memory only. It is never written to disk, logged, or indexed
into the public knowledge base; only counts and identifiers appear in logs.

Field templates come from the official blank forms in data/raw/ (manifest document_type
`official_form`): every line containing a dot leader ("......") is a field, and the words on that
line form its label. Two checks are used:
  * digital PDFs: geometric — is there any non-label word inside the dot-leader area?
  * images / scans (OCR): line-based — does the matching line contain words beyond the label?
"""

import base64
import binascii
import logging
import re
import shutil
import subprocess
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

import cv2
import fitz
import numpy as np

from agents import i18n
from agents.corpus import Corpus
from agents.schemas import FormCheckRequest, FormCheckResult, FormField

log = logging.getLogger(__name__)

PDF_TYPES = {"application/pdf"}
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/tiff", "image/bmp"}
FILLER = re.compile(r"^[\s.…_·:/\-–—|]+$")
LEADER = re.compile(r"(?:\.{3,}|…{2,}|_{3,})")
ARABIC = re.compile(r"[\u0600-\u06ff]")
BIDI = re.compile(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]")  # OCR attaches direction marks
ARTIFACT_WIDTH_RATIO = 4.0
MIN_OCR_CONFIDENCE = 10.0
MIN_ANCHORS = 6  # words shared by the blank form and the OCR output, used to align them
RANSAC_THRESHOLD_POINTS = 4.0
INK_THRESHOLD = 128  # grayscale value below which a pixel counts as ink
INK_DELTA = 0.004  # extra ink share (vs. the blank form) that marks a field as filled
MIN_MATCH = 0.5  # share of template label tokens that must be present to recognise a form
MIN_LINE_MATCH = 0.5
MAX_LABEL_GAP = 30.0  # points between a dot leader and the text that labels it
MAX_OCR_PAGES = 3
OCR_DPI = 300
OCR_TIMEOUT_SECONDS = 120
MAX_DESKEW_DEGREES = 6.0


@dataclass
class Word:
    text: str
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    line: tuple  # line identifier (page, block, line)


@dataclass
class TemplateField:
    label: str
    label_tokens: frozenset[str]
    page: int
    region: tuple[float, float, float, float]  # union of the dot-leader boxes


def norm_token(token: str) -> str:
    t = BIDI.sub("", unicodedata.normalize("NFKC", token)).lower().replace("ـ", "")
    t = re.sub(r"[\u064b-\u0652]", "", t)
    t = re.sub("[أإآ]", "ا", t).replace("ة", "ه").replace("ى", "ي")
    return t.strip(".:;,()[]«»\"'’…_-–—/|")


def is_filler(token: str) -> bool:
    return bool(FILLER.match(token)) or not re.search(r"\w", unicodedata.normalize("NFKC", token))


# ---------------------------------------------------------------------- word extraction
def pdf_words(doc: fitz.Document) -> list[Word]:
    out = []
    for pno, page in enumerate(doc):
        for x0, y0, x1, y1, text, block, line, _ in page.get_text("words"):
            out.append(Word(text, pno, x0, y0, x1, y1, (pno, block, line)))
    return out


def ocr_available() -> bool:
    return shutil.which("tesseract") is not None


def ocr_words(image_bytes: bytes, page: int, languages: str) -> list[Word]:
    """Runs local Tesseract on in-memory image bytes (stdin -> stdout, no temporary files)."""
    proc = subprocess.run(
        ["tesseract", "stdin", "stdout", "-l", languages, "--psm", "4", "tsv"],
        input=image_bytes, capture_output=True, timeout=OCR_TIMEOUT_SECONDS, check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError("OCR failed")
    rows = []
    for row in proc.stdout.decode("utf-8", "replace").splitlines()[1:]:
        cols = row.split("\t")
        text = BIDI.sub("", cols[11]).strip() if len(cols) >= 12 else ""
        if not text:
            continue
        try:
            conf = float(cols[10])
        except ValueError:
            continue
        if conf < 0:
            continue
        left, top, width, height = (float(v) for v in cols[6:10])
        rows.append((conf, Word(text, page, left, top, left + width, top + height,
                                (page, int(cols[2]), int(cols[3]), int(cols[4])))))
    return drop_leader_artifacts(rows)


def drop_leader_artifacts(rows: list[tuple[float, "Word"]]) -> list["Word"]:
    """Tesseract reads dot leaders as short, very wide, near-zero-confidence words (e.g. a
    4-letter "word" spanning 1000 px). Such tokens would look like filled-in values."""
    reliable = sorted((w.x1 - w.x0) / len(w.text) for conf, w in rows if conf >= 60 and len(w.text) >= 3)
    median = reliable[len(reliable) // 2] if reliable else None
    out = []
    for conf, w in rows:
        too_wide = median is not None and (w.x1 - w.x0) / len(w.text) > ARTIFACT_WIDTH_RATIO * median
        if conf < MIN_OCR_CONFIDENCE or too_wide:
            continue
        out.append(w)
    return out


def deskew(image: bytes) -> bytes:
    """Straightens a photographed or scanned page before OCR.

    Projection-profile search: the rotation that maximises the variance of the row sums of the
    binarised page aligns the text lines with the pixel rows. Returns PNG bytes (in memory)."""
    img = cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return image
    small = cv2.resize(img, None, fx=600 / max(img.shape), fy=600 / max(img.shape), interpolation=cv2.INTER_AREA)
    ink = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    center = (small.shape[1] / 2, small.shape[0] / 2)

    def profile_score(angle: float) -> float:
        rotated = cv2.warpAffine(ink, cv2.getRotationMatrix2D(center, angle, 1.0), ink.shape[::-1])
        return float(np.var(rotated.sum(axis=1, dtype=np.float64)))

    coarse = max(np.arange(-MAX_DESKEW_DEGREES, MAX_DESKEW_DEGREES + 0.01, 0.5), key=profile_score)
    best = max(np.arange(coarse - 0.5, coarse + 0.51, 0.1), key=profile_score)
    if abs(best) < 0.15:
        return cv2.imencode(".png", img)[1].tobytes()
    h, w = img.shape
    straight = cv2.warpAffine(img, cv2.getRotationMatrix2D((w / 2, h / 2), float(best), 1.0), (w, h),
                              flags=cv2.INTER_LINEAR, borderValue=255)
    return cv2.imencode(".png", straight)[1].tobytes()


def group_lines(words: list[Word]) -> dict[tuple, list[Word]]:
    lines: dict[tuple, list[Word]] = {}
    for w in words:
        lines.setdefault(w.line, []).append(w)
    return lines


# ---------------------------------------------------------------------- templates
@dataclass
class Template:
    fields: list[TemplateField]
    words: list[Word]  # every word printed on the blank official form
    path: str = ""  # official PDF, rendered to compare ink with scanned uploads


def _clean_label(text: str) -> str:
    text = LEADER.sub(" ", unicodedata.normalize("NFKC", text))
    text = re.sub(r"[.:/]+(?=\s|$)|(?<=\s)[.:/]+|^[.:/]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _same_row(a: fitz.Rect, b: fitz.Rect) -> bool:
    return min(a.y1, b.y1) - max(a.y0, b.y0) > 0.5 * min(a.height, b.height)


def _gap(a: fitz.Rect, b: fitz.Rect) -> float:
    return max(b.x0 - a.x1, a.x0 - b.x1, 0)


def page_spans(page: fitz.Page) -> list[tuple[str, fitz.Rect]]:
    return [(s["text"], fitz.Rect(s["bbox"])) for b in page.get_text("dict")["blocks"]
            for ln in b.get("lines", []) for s in ln["spans"] if s["text"].strip()]


def template_fields(doc: fitz.Document) -> list[TemplateField]:
    """One field per row of adjacent dot leaders; the label is the adjacent text on that row."""
    fields = []
    for pno, page in enumerate(doc):
        spans = page_spans(page)
        groups: list[list[tuple[str, fitz.Rect]]] = []
        for span in (s for s in spans if LEADER.search(s[0])):
            for g in groups:
                if any(_same_row(span[1], o[1]) and _gap(span[1], o[1]) <= MAX_LABEL_GAP for o in g):
                    g.append(span)
                    break
            else:
                groups.append([span])
        for group in groups:
            box = fitz.Rect(group[0][1])
            for _, b in group[1:]:
                box |= b
            parts = [_clean_label(t) for t, _ in group]
            for other, obox in spans:
                if (not LEADER.search(other) and len(other) < 60 and _same_row(box, obox)
                        and _gap(box, obox) <= MAX_LABEL_GAP):
                    parts.append(_clean_label(other))
            latin = " ".join(p for p in parts if p and not ARABIC.search(p))
            arabic = " ".join(p for p in parts if p and ARABIC.search(p))
            label = " / ".join(p for p in (latin, arabic) if p)
            tokens = frozenset(t for t in (norm_token(x) for x in label.replace("/", " ").split()) if t)
            if tokens:
                fields.append(TemplateField(label, tokens, pno, (box.x0, box.y0, box.x1, box.y1)))
    return fields


def _narrow_to_leaders(fields: list[TemplateField], words: list[Word]) -> list[TemplateField]:
    """Restricts each field region to its dot-leader words (a span may also contain the label)."""
    out = []
    for f in fields:
        x0, y0, x1, y1 = f.region
        dots = [w for w in words if w.page == f.page and LEADER.search(w.text)
                and x0 - 1 <= _center(w)[0] <= x1 + 1 and y0 - 1 <= _center(w)[1] <= y1 + 1]
        if dots:
            region = (min(w.x0 for w in dots), min(w.y0 for w in dots), max(w.x1 for w in dots), max(w.y1 for w in dots))
            f = TemplateField(f.label, f.label_tokens, f.page, region)
        out.append(f)
    return out


@lru_cache(maxsize=16)
def _template_for(path: str, _mtime: float) -> Template:
    with fitz.open(path) as doc:
        words = pdf_words(doc)
        return Template(_narrow_to_leaders(template_fields(doc), words), words, path)


# ---------------------------------------------------------------------- checks
def _center(w: Word) -> tuple[float, float]:
    return (w.x0 + w.x1) / 2, (w.y0 + w.y1) / 2


def new_words(template: Template, words: list[Word], tolerance: float = 3.0, min_len: int = 1) -> list[Word]:
    """Words of the upload that are not printed at the same place on the blank official form."""
    printed: dict[str, list[tuple[int, float, float]]] = {}
    for w in template.words:
        printed.setdefault(norm_token(w.text), []).append((w.page, *_center(w)))
    out = []
    for w in words:
        if is_filler(w.text) or len(norm_token(w.text)) < min_len:
            continue
        cx, cy = _center(w)
        same = printed.get(norm_token(w.text), [])
        if not any(p == w.page and abs(x - cx) <= tolerance and abs(y - cy) <= tolerance for p, x, y in same):
            out.append(w)
    return out


def _anchor_pairs(template: Template, words: list[Word]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """(image point, template point) for words that occur exactly once on both pages."""
    def unique(ws: list[Word]) -> dict[str, Word]:
        seen: dict[str, list[Word]] = {}
        for w in ws:
            t = norm_token(w.text)
            if len(t) >= 4 and not ARABIC.search(t) and w.page == 0:
                seen.setdefault(t, []).append(w)
        return {t: v[0] for t, v in seen.items() if len(v) == 1}

    tpl, ocr = unique(template.words), unique(words)
    return [(_center(ocr[t]), _center(tpl[t])) for t in tpl if t in ocr]


def fit_homography(template: Template, words: list[Word]) -> np.ndarray | None:
    """Homography from image pixels to template points (RANSAC over anchor words).

    Handles scale, rotation, skew and perspective of scans and photos of the official form."""
    pairs = _anchor_pairs(template, words)
    if len(pairs) < MIN_ANCHORS:
        return None
    src = np.float32([a for a, _ in pairs])
    dst = np.float32([b for _, b in pairs])
    h, mask = cv2.findHomography(src, dst, cv2.RANSAC, RANSAC_THRESHOLD_POINTS)
    if h is None or int(mask.sum()) < MIN_ANCHORS:
        return None
    return h


def _render_gray(path: str, scale: float) -> np.ndarray:
    with fitz.open(path) as doc:
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csGRAY, alpha=False)
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.stride)[:, : pix.width]


def check_ink(template: Template, image: bytes, homography: np.ndarray) -> list[FormField]:
    """Warps the upload onto the blank official form and compares the ink inside every
    dot-leader band: extra ink means that something was written on the line."""
    upload = cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_GRAYSCALE)
    if upload is None:
        return [FormField(label=f.label, status="not_found") for f in template.fields]
    # Compare at the upload's own resolution (pixels per template point), within sane bounds.
    scale = float(np.clip(1 / np.sqrt(abs(np.linalg.det(homography[:2, :2]))), 1.0, 4.0))
    blank = _render_gray(template.path, scale)
    to_blank = np.diag([scale, scale, 1.0]) @ homography
    warped = cv2.warpPerspective(upload, to_blank, (blank.shape[1], blank.shape[0]), borderValue=255)
    out = []
    for f in template.fields:
        x0, y0, x1, y1 = f.region
        top = y0 - (y1 - y0) * 0.4  # the dotted line and the space just above it
        r0, r1 = int(top * scale), int(y1 * scale)
        c0, c1 = int(x0 * scale), int(x1 * scale)
        if r1 - r0 < 2 or c1 - c0 < 4:
            out.append(FormField(label=f.label, status="not_found"))
            continue
        mine = float((warped[r0:r1, c0:c1] < INK_THRESHOLD).mean())
        ref = float((blank[r0:r1, c0:c1] < INK_THRESHOLD).mean())
        out.append(FormField(label=f.label, status="filled" if mine - ref > INK_DELTA else "empty"))
    return out


def check_geometric(template: Template, words: list[Word], tolerance: float = 3.0, min_len: int = 1) -> list[FormField]:
    added = new_words(template, words, tolerance, min_len)
    out = []
    for f in template.fields:
        x0, y0, x1, y1 = f.region
        # Values are typed or written on the dotted line, or slightly above it.
        top = y0 - (y1 - y0) * 0.3
        filled = any(w.page == f.page and x0 <= _center(w)[0] <= x1 and top <= _center(w)[1] <= y1 for w in added)
        out.append(FormField(label=f.label, status="filled" if filled else "empty"))
    return out


def check_lines(fields: list[TemplateField], words: list[Word]) -> list[FormField]:
    lines = [[norm_token(w.text) for w in ws if not is_filler(w.text)] for ws in group_lines(words).values()]
    lines = [[t for t in ln if t] for ln in lines]
    out = []
    for f in fields:
        best, best_score = None, 0.0
        for ln in lines:
            score = len(f.label_tokens & set(ln)) / len(f.label_tokens)
            if score > best_score:
                best, best_score = ln, score
        if best is None or best_score < MIN_LINE_MATCH:
            out.append(FormField(label=f.label, status="not_found"))
            continue
        extra = [t for t in best if t not in f.label_tokens and len(t) > 1]
        out.append(FormField(label=f.label, status="filled" if extra else "empty"))
    return out


class FormHelper:
    def __init__(self, corpus: Corpus, max_bytes: int, ocr_languages: str = "ara+fra"):
        self.corpus = corpus
        self.max_bytes = max_bytes
        self.ocr_languages = ocr_languages

    def templates(self) -> dict[str, Template]:
        out = {}
        for rec in self.corpus.records().values():
            if rec.document_type.value != "official_form" or not rec.file_path or rec.file_format != "pdf":
                continue
            path = self.corpus.raw_dir.parent.parent / rec.file_path
            if path.exists():
                template = _template_for(str(path), path.stat().st_mtime)
                if template.fields:
                    out[rec.doc_id] = template
        return out

    def check(self, req: FormCheckRequest, default_language: str = "fr") -> FormCheckResult:
        lang = req.language or default_language
        try:
            data = base64.b64decode(req.data_b64, validate=True)
        except (binascii.Error, ValueError):
            return self._error(lang, "invalid base64 payload")
        if len(data) > self.max_bytes:
            return self._error(lang, f"file larger than {self.max_bytes // (1024 * 1024)} MB")
        mime = req.mime_type.lower().split(";")[0].strip()
        try:
            words, method, extra_tokens, page_image = self._extract(data, mime)
        except ValueError as exc:
            return self._error(lang, str(exc))
        finally:
            del data
        log.info("form_check", extra={"fields": {"method": method, "words": len(words), "mime": mime}})

        tokens = {norm_token(w.text) for w in words if not is_filler(w.text)} | extra_tokens
        best_id, best_score = None, 0.0
        templates = self.templates()
        labels = {d: set().union(*(f.label_tokens for f in t.fields)) for d, t in templates.items()}
        ranking = []
        for doc_id, label_tokens in labels.items():
            # The overall share decides whether this is the form at all. Official forms share many
            # labels (e.g. RNE F-001 / F-002), so the share of tokens found only on this form
            # decides between candidates.
            others = set().union(set(), *(v for d, v in labels.items() if d != doc_id))
            distinct = label_tokens - others
            overall = len(label_tokens & tokens) / len(label_tokens)
            distinctive = len(distinct & tokens) / len(distinct) if distinct else 0.0
            ranking.append((overall >= MIN_MATCH, distinctive, overall, doc_id))
        if ranking:
            eligible, _, best_score, best_id = max(ranking)
            if not eligible:
                best_id = None
        if best_id is None or best_score < MIN_MATCH:
            # Metadata only (no file content): lets an unrecognised upload be diagnosed later (near miss vs other form).
            closest = max(ranking, key=lambda r: r[2]) if ranking else (False, 0.0, 0.0, None)
            log.info("form_unrecognised", extra={"fields": {"closest_template": closest[3],
                                                            "closest_overall": round(closest[2], 3),
                                                            "threshold": MIN_MATCH, "method": method}})
            return FormCheckResult(text=i18n.t("form_unknown", lang), recognised=False, method=method,
                                   match_score=round(best_score, 3))

        template = templates[best_id]
        if method == "text_layer":
            checked = check_geometric(template, words)
        else:
            # Text written on a dot leader is read by OCR merged with the dots and with very low
            # confidence, so OCR text cannot tell filled from empty. OCR is used to recognise and
            # align the form; the decision compares ink with the blank official form.
            homography = fit_homography(template, words)
            if homography is not None and page_image is not None:
                checked = check_ink(template, page_image, homography)
                method = "ocr_ink"
            else:
                checked = check_lines(template.fields, words)
        del page_image
        rec = self.corpus.records()[best_id]
        missing = [f.label for f in checked if f.status == "empty"]
        unlocated = [f.label for f in checked if f.status == "not_found"]
        lines = [f"📝 {i18n.t('form_identified', lang, title=rec.title)}", ""]
        if missing:
            lines.append(f"❗ {i18n.t('form_missing', lang)}:")
            lines += [f"• {m}" for m in missing]
        if unlocated:
            lines += ["", f"❔ {i18n.t('form_unreadable', lang)}:"] + [f"• {m}" for m in unlocated]
        if not missing and not unlocated:
            lines.append(f"✅ {i18n.t('form_complete', lang)}")
        lines += ["", f"ℹ️ {i18n.t('form_heuristic', lang, method='PDF' if method == 'text_layer' else 'OCR')}",
                  "", f"📚 {i18n.t('sources', lang)}:", f"[1] {rec.title} ({rec.source_organization})\n{rec.url}"]
        return FormCheckResult(
            text="\n".join(lines), recognised=True, method=method, form_doc_id=best_id, form_title=rec.title,
            form_url=rec.url, match_score=round(best_score, 3), fields=checked, missing=missing,
        )

    def _extract(self, data: bytes, mime: str) -> tuple[list[Word], str, set[str], bytes | None]:
        """Returns (words, method, extra recognition tokens, first page image for OCR uploads)."""
        if mime in PDF_TYPES:
            try:
                doc = fitz.open(stream=data, filetype="pdf")
            except Exception as exc:  # PyMuPDF raises several exception types for corrupt files
                raise ValueError("unreadable PDF") from exc
            with doc:
                words = pdf_words(doc)
                if sum(len(w.text) for w in words) >= 50:
                    span_tokens = {norm_token(t) for page in doc for text, _ in page_spans(page) for t in text.split()}
                    return words, "text_layer", span_tokens, None
                if not ocr_available():
                    raise ValueError("scanned PDF and OCR (tesseract) is not installed")
                out: list[Word] = []
                first_page = None
                for pno, page in enumerate(doc):
                    if pno >= MAX_OCR_PAGES:
                        break
                    png = deskew(page.get_pixmap(dpi=OCR_DPI).tobytes("png"))
                    first_page = first_page or png
                    out += ocr_words(png, pno, self.ocr_languages)
                return out, "ocr", set(), first_page
        if mime in IMAGE_TYPES:
            if not ocr_available():
                raise ValueError("OCR (tesseract) is not installed")
            try:
                straight = deskew(data)
                return ocr_words(straight, 0, self.ocr_languages), "ocr", set(), straight
            except (RuntimeError, subprocess.TimeoutExpired) as exc:
                raise ValueError("OCR failed on this image") from exc
        raise ValueError(f"unsupported file type {mime}")

    @staticmethod
    def _error(lang: str, reason: str) -> FormCheckResult:
        # `error` keeps the technical reason (English, for logs/clients); the user text is localized.
        key = next((k for prefix, k in ERROR_REASON_KEYS if reason.startswith(prefix)), "reason_generic")
        localized = i18n.t(key, lang, mb=(re.search(r"\d+", reason) or ["?"])[0])
        return FormCheckResult(text=i18n.t("form_error", lang, reason=localized), recognised=False, error=reason)


# Technical reasons raised above -> localized explanation keys in agents/i18n.py.
ERROR_REASON_KEYS = [
    ("unreadable PDF", "reason_unreadable_pdf"), ("invalid base64", "reason_invalid_upload"),
    ("file larger than", "reason_too_large"), ("unsupported file type", "reason_unsupported_type"),
    ("OCR failed", "reason_ocr_failed"), ("scanned PDF and OCR", "reason_ocr_missing"), ("OCR (tesseract)", "reason_ocr_missing"),
]
