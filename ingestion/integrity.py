"""Checksums and file-format validation for downloaded originals."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

PDF_MAGIC = b"%PDF-"
# Pages with fewer extractable characters than this are treated as image-only (OCR needed).
MIN_TEXT_CHARS_PER_PDF = 50


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


class ValidationError(Exception):
    pass


@dataclass
class ValidatedFile:
    file_format: str  # "pdf" | "html"
    page_count: int | None
    has_text_layer: bool | None


def detect_format(data: bytes, content_type: str | None) -> str:
    head = data[:1024].lstrip().lower()
    if data.startswith(PDF_MAGIC):
        return "pdf"
    if head.startswith((b"<!doctype html", b"<html", b"<meta", b"<?xml")) or b"<html" in head:
        return "html"
    ct = (content_type or "").split(";")[0].strip().lower()
    raise ValidationError(f"unrecognized file signature (content-type={ct or 'none'})")


def validate_pdf(data: bytes) -> ValidatedFile:
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:  # PyMuPDF raises several exception types for corrupt files
        raise ValidationError(f"PDF cannot be opened: {exc}") from exc
    with doc:
        if doc.needs_pass:
            raise ValidationError("PDF is password protected")
        if doc.page_count == 0:
            raise ValidationError("PDF has no pages")
        text_chars = sum(len(page.get_text("text").strip()) for page in doc)
        return ValidatedFile("pdf", doc.page_count, text_chars >= MIN_TEXT_CHARS_PER_PDF)


def validate_html(data: bytes) -> ValidatedFile:
    if len(data) < 200:
        raise ValidationError("HTML document is suspiciously small")
    return ValidatedFile("html", None, True)


def validate_document(data: bytes, content_type: str | None) -> ValidatedFile:
    fmt = detect_format(data, content_type)
    return validate_pdf(data) if fmt == "pdf" else validate_html(data)
