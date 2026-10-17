import json

import pytest

from rag.extraction import detect_script_language, extract_document, extract_html, normalize_text


def test_normalize_folds_arabic_presentation_forms():
    # U+FE97 U+FEEE U+FEE7 U+FEB2 are presentation forms; NFKC maps them to standard letters.
    assert normalize_text("ﺗﻮﻧﺲ") == "تونس"


def test_normalize_strips_tatweel_and_private_use_glyphs():
    assert normalize_text("اـل") == "ال"


def test_detect_script_language():
    assert detect_script_language("Ceci est un texte en alphabet latin uniquement.") == "fr"
    assert detect_script_language("هذا نص " * 10) == "ar"
    assert detect_script_language("ok") == "unknown"


def test_pdf_extraction_detects_headings_and_pages(make_pdf):
    path = make_pdf(
        [
            [("Article premier - placeholder body text one.", 10), ("Ordinary paragraph text " * 3, 10)],
            [("LARGE TITLE", 20), ("Second page paragraph text.", 10)],
        ]
    )
    blocks = extract_document(path, "pdf")
    headings = [(b.text, b.level, b.page) for b in blocks if b.kind == "heading"]
    assert ("Article premier", 2, 1) in headings
    assert ("LARGE TITLE", 1, 2) in headings
    # The article body is kept as content, not swallowed by the heading.
    assert any(b.kind == "paragraph" and "placeholder body text one" in b.text for b in blocks)


def test_html_extraction_structure(tmp_path):
    html = """<html><body><div class="content-primary">
      <h3>Section A</h3><h4>Subsection</h4>
      <div class="alert alert-info">Label</div>
      <ul><li>first item</li><li>second item</li></ul>
      <p>&copy; footer</p></div></body></html>"""
    path = tmp_path / "x.html"
    path.write_text(html, encoding="utf-8")
    blocks = extract_html(path)
    assert [(b.kind, b.text) for b in blocks] == [
        ("heading", "Section A"),
        ("heading", "Subsection"),
        ("heading", "Label"),
        ("list_item", "first item"),
        ("list_item", "second item"),
    ]


def test_embedded_json_table_extraction(tmp_path):
    rows = [{"Code procédure": "X 1", "Champ": "valeur"}, {"Code procédure": "X 2", "Champ": "autre"}]
    path = tmp_path / "t.html"
    path.write_text("<html><script>var t = " + json.dumps(rows) + ";</script>" + " " * 300 + "</html>", encoding="utf-8")
    blocks = extract_html(path)
    table = [b for b in blocks if b.kind == "table_row"]
    assert len(table) == 2
    assert "Code procédure: X 1" in table[0].text


# --------------------------------------------------------------------- real corpus (if ingested)


def _real_record(manifest_path, doc_id):
    if not manifest_path.exists():
        pytest.skip("corpus not ingested yet (run: python -m ingestion)")
    for rec in json.loads(manifest_path.read_text(encoding="utf-8"))["records"]:
        if rec["doc_id"] == doc_id and rec["verification_status"] == "official_source_verified":
            return rec
    pytest.skip(f"{doc_id} not available in manifest")


def test_real_passport_guide_extraction(real_manifest_path):
    from backend.settings import REPO_ROOT

    rec = _real_record(real_manifest_path, "interior-passport-guide-fr")
    blocks = extract_document(REPO_ROOT / rec["file_path"], "html")
    headings = {b.text for b in blocks if b.kind == "heading"}
    assert "Pièces à fournir" in headings
    assert sum(b.kind == "list_item" for b in blocks) > 20


def test_real_rne_procedure_table_extraction(real_manifest_path):
    from backend.settings import REPO_ROOT

    rec = _real_record(real_manifest_path, "rne-formalities-procedure-table")
    rows = [b for b in extract_document(REPO_ROOT / rec["file_path"], "html") if b.kind == "table_row"]
    assert any("RNE C 012" in r.text for r in rows)
    assert len(rows) >= 90


def test_real_jort_pdf_extraction(real_manifest_path):
    from backend.settings import REPO_ROOT

    rec = _real_record(real_manifest_path, "rne-arrete-2026-35")
    blocks = extract_document(REPO_ROOT / rec["file_path"], "pdf")
    assert any(b.kind == "heading" and b.text.startswith("Article premier") for b in blocks)
    assert not any(b.text.startswith("Journal Officiel de la République Tunisienne") for b in blocks)
