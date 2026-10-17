import pytest

from ingestion.integrity import (
    ValidationError,
    detect_format,
    sha256_bytes,
    sha256_file,
    validate_document,
    validate_pdf,
)


def test_sha256_known_vector():
    # NIST FIPS 180-2 test vector for "abc".
    assert sha256_bytes(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_sha256_file_matches_bytes(tmp_path):
    data = b"x" * (3 << 20)  # larger than one read chunk
    path = tmp_path / "f.bin"
    path.write_bytes(data)
    assert sha256_file(path) == sha256_bytes(data)


def test_detect_format():
    assert detect_format(b"%PDF-1.7\n...", "application/pdf") == "pdf"
    assert detect_format(b"<!DOCTYPE html><html></html>", "text/html") == "html"
    with pytest.raises(ValidationError):
        detect_format(b"\x89PNG\r\n\x1a\n", "image/png")


def test_validate_pdf_with_text(make_pdf):
    path = make_pdf([[("Fixture heading line for extraction tests", 12)] * 3])
    result = validate_pdf(path.read_bytes())
    assert result.file_format == "pdf"
    assert result.page_count == 1
    assert result.has_text_layer is True


def test_validate_pdf_image_only_flags_missing_text_layer(image_only_pdf_bytes):
    result = validate_pdf(image_only_pdf_bytes)
    assert result.has_text_layer is False


def test_corrupt_pdf_is_rejected():
    with pytest.raises(ValidationError):
        validate_pdf(b"%PDF-1.4\nthis is not a real pdf body")


def test_tiny_html_is_rejected():
    with pytest.raises(ValidationError):
        validate_document(b"<html></html>", "text/html")
