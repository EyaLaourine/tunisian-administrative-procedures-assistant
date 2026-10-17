"""Text extraction with document-structure detection.

Every source is turned into an ordered list of `TextBlock`s (heading / paragraph / list_item /
table_row) carrying page numbers. Both chunking strategies consume this same representation, so
evaluation compares chunking only, not extraction.
"""

import json
import re
import unicodedata
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

import fitz  # PyMuPDF
from bs4 import BeautifulSoup


@dataclass
class TextBlock:
    text: str
    kind: str  # "heading" | "paragraph" | "list_item" | "table_row"
    level: int = 0  # heading depth (1 = top); 0 for non-headings
    page: int | None = None  # 1-based page number for PDFs

    def to_dict(self) -> dict:
        return asdict(self)


# Legal-text structure markers in French and Arabic official texts (JORT).
_LEGAL_HEADING = re.compile(
    r"^\s*(?:"
    r"(?:TITRE|Titre|CHAPITRE|Chapitre|SECTION|Section)\s+[\wIVXLC]+"
    r"|(?:Article|Art\.)\s+(?:premier|\d+)"
    r"|(?:الباب|العنوان|القسم)\s+\S+"
    r"|الفصل\s*(?:الأول|\d+)"
    r")",
)
# Running headers/footers printed on every JORT page.
_JORT_BOILERPLATE = re.compile(
    r"^\s*(?:"
    r"Journal Officiel de la République Tunisienne\b.*"
    r"|N°\s*\d+\s*"
    r"|Page\s+\d+\s*"
    r"|الرائد الرسمي للجمهورية التونسية.*"
    r"|(?:عـ*دد|صفحـ*ة)\s*\d+\s*"
    r")$"
)


def normalize_text(text: str) -> str:
    """NFKC folds Arabic presentation forms (U+FB50-U+FEFF) into standard letters; collapse spaces."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("ـ", "")  # tatweel (kashida) is purely typographic
    # Some JORT Arabic fonts map ligatures to Private Use Area code points with no standard
    # meaning. They cannot be decoded reliably, so they are dropped (known limitation).
    text = re.sub(r"[-]", "", text)
    text = re.sub(r"[ \t ]+", " ", text)
    return text.strip()


def detect_script_language(text: str) -> str:
    """Script-based language hint: 'ar', 'fr' (Latin script), 'mixed' or 'unknown'."""
    arabic = len(re.findall(r"[؀-ۿ]", text))
    latin = len(re.findall(r"[A-Za-zÀ-ÿ]", text))
    total = arabic + latin
    if total < 20:
        return "unknown"
    if arabic / total > 0.8:
        return "ar"
    if latin / total > 0.8:
        return "fr"
    return "mixed"


# ----------------------------------------------------------------------------- PDF


def extract_pdf(path: Path) -> list[TextBlock]:
    blocks: list[TextBlock] = []
    with fitz.open(path) as doc:
        sizes: Counter[float] = Counter()
        pages = []
        for page in doc:
            data = page.get_text("dict")
            pages.append(data)
            for b in data["blocks"]:
                for line in b.get("lines", []):
                    for span in line["spans"]:
                        if span["text"].strip():
                            sizes[round(span["size"], 1)] += len(span["text"])
        body_size = sizes.most_common(1)[0][0] if sizes else 10.0

        for page_no, data in enumerate(pages, start=1):
            for b in data["blocks"]:
                lines = []
                max_size = 0.0
                bold_chars = total_chars = 0
                for line in b.get("lines", []):
                    line_text = "".join(span["text"] for span in line["spans"])
                    if line_text.strip():
                        lines.append(line_text)
                    for span in line["spans"]:
                        n = len(span["text"].strip())
                        total_chars += n
                        max_size = max(max_size, span["size"])
                        if span["flags"] & 16:  # bold
                            bold_chars += n
                text = normalize_text(" ".join(lines))
                if not text or _JORT_BOILERPLATE.match(text):
                    continue
                legal = _LEGAL_HEADING.match(text)
                if legal:
                    # "Article 3 - ..." / "الفصل 3 ...": the marker opens a section, and the block
                    # usually also contains the article body, which must be kept as content.
                    blocks.append(TextBlock(legal.group(0).strip(), "heading", 2, page_no))
                    blocks.append(TextBlock(text, "paragraph", 0, page_no))
                    continue
                if len(text) < 160 and max_size >= body_size * 1.2:
                    blocks.append(TextBlock(text, "heading", 1, page_no))
                elif len(text) < 160 and total_chars and bold_chars / total_chars > 0.8:
                    blocks.append(TextBlock(text, "heading", 3, page_no))
                else:
                    blocks.append(TextBlock(text, "paragraph", 0, page_no))
    return blocks


# ----------------------------------------------------------------------------- HTML


def _rne_procedure_rows(html: str) -> list[dict] | None:
    """The RNE formalities page embeds its procedure table as a JSON array in the page source."""
    start = html.find('[{"Code proc')
    if start < 0:
        return None
    rows, _ = json.JSONDecoder().raw_decode(html[start:])
    return rows if isinstance(rows, list) else None


def _extract_rne_procedure_table(rows: list[dict]) -> list[TextBlock]:
    blocks = [TextBlock("Formalités - Registre National des Entreprises", "heading", 1)]
    for row in rows:
        fields = {normalize_text(k): normalize_text(str(v)) for k, v in row.items() if str(v).strip()}
        blocks.append(TextBlock("\n".join(f"{k}: {v}" for k, v in fields.items()), "table_row"))
    return blocks


def _extract_generic_html(html: str) -> list[TextBlock]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    root = soup.select_one(".content-primary") or soup.body or soup
    blocks: list[TextBlock] = []
    for el in root.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "div"]):
        if el.name == "div" and "alert" not in (el.get("class") or []):
            continue
        # Skip containers whose text is emitted by their own block-level children.
        if el.name in ("p", "div") and el.find(["li", "p", "h3", "h4"]):
            continue
        text = normalize_text(el.get_text(" ", strip=True))
        if not text:
            continue
        if el.name[0] == "h":
            blocks.append(TextBlock(text, "heading", int(el.name[1])))
        elif el.name == "div":  # section labels such as "Pièces à fournir"
            blocks.append(TextBlock(text, "heading", 6))
        elif el.name == "li":
            blocks.append(TextBlock(text, "list_item"))
        else:
            blocks.append(TextBlock(text, "paragraph"))
    # Drop trailing copyright/footer lines.
    return [b for b in blocks if not b.text.startswith("©")]


def extract_html(path: Path) -> list[TextBlock]:
    html = path.read_text(encoding="utf-8", errors="replace")
    rows = _rne_procedure_rows(html)
    if rows:
        return _extract_rne_procedure_table(rows)
    return _extract_generic_html(html)


def extract_document(path: Path, file_format: str) -> list[TextBlock]:
    if file_format == "pdf":
        return extract_pdf(path)
    if file_format == "html":
        return extract_html(path)
    raise ValueError(f"unsupported format: {file_format}")
