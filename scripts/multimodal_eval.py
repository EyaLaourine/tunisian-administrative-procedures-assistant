"""Multimodal evaluation against a running backend (default: the candidate on 127.0.0.1:8002).

usage: python scripts/multimodal_eval.py [--base http://127.0.0.1:8002]

Fixtures are derived from the official blank forms RNE F-001/F-002 (data/raw). "Filled" fields contain only
the neutral word "placeholder" (synthetic, not personal data). Images are renders of the official PDFs. No
fixture is indexed or stored outside data/evaluation; only statuses and counts are recorded.
"""

from __future__ import annotations

import argparse
import base64
import glob

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import fitz
import httpx
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.corpus import Corpus  # noqa: E402
from agents.form_helper import FormHelper  # noqa: E402

F001, F002 = "rne-form-f001-natural-person-registration", "rne-form-f002-legal-entity-registration"


def official(doc_id: str) -> bytes:
    return Path(glob.glob(str(ROOT / "data" / "raw" / doc_id / "*.pdf"))[0]).read_bytes()


def fill(doc_id: str, n_fields: int) -> bytes:
    helper = FormHelper(Corpus(ROOT / "data" / "raw", ROOT / "data" / "processed"), max_bytes=10 * 1024 * 1024)
    fields = helper.templates()[doc_id].fields[:n_fields]
    doc = fitz.open(stream=official(doc_id), filetype="pdf")
    for f in fields:
        doc[f.page].insert_text((f.region[0] + 5, f.region[3] - 3), "placeholder", fontsize=11)
    return doc.tobytes()


def render(pdf: bytes, fmt: str, rotate: float = 0.0, dpi: int = 200) -> bytes:
    page = fitz.open(stream=pdf, filetype="pdf")[0]
    pix = page.get_pixmap(dpi=dpi)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3].copy()
    if rotate:
        h, w = img.shape[:2]
        m = cv2.getRotationMatrix2D((w / 2, h / 2), rotate, 1.0)
        cos, sin = abs(m[0, 0]), abs(m[0, 1])
        nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
        m[0, 2] += nw / 2 - w / 2
        m[1, 2] += nh / 2 - h / 2
        img = cv2.warpAffine(img, m, (nw, nh), borderValue=(255, 255, 255))
    ok, buf = cv2.imencode(".jpg" if fmt == "JPEG" else ".png", img[:, :, ::-1], [cv2.IMWRITE_JPEG_QUALITY, 90] if fmt == "JPEG" else [])
    assert ok
    return buf.tobytes()


def cases() -> list[dict]:
    f1, f2 = official(F001), official(F002)
    return [
        {"id": "M01", "desc": "Official blank F-001 (PDF)", "mime": "application/pdf", "data": f1, "expect": "recognised, all fields empty"},
        {"id": "M02", "desc": "Official blank F-002 (PDF)", "mime": "application/pdf", "data": f2, "expect": "recognised, all fields empty"},
        {"id": "M03", "desc": "F-001 with 3 fields filled ('placeholder', synthetic)", "mime": "application/pdf", "data": fill(F001, 3), "expect": "3 filled"},
        {"id": "M04", "desc": "F-002 with 5 fields filled ('placeholder', synthetic)", "mime": "application/pdf", "data": fill(F002, 5), "expect": "5 filled"},
        {"id": "M05", "desc": "F-001 blank rendered to PNG (200 dpi)", "mime": "image/png", "data": render(f1, "PNG"), "expect": "recognised via OCR"},
        {"id": "M05b", "desc": "F-001 with 3 filled fields rendered to PNG (200 dpi)", "mime": "image/png", "data": render(fill(F001, 3), "PNG"), "expect": "3 filled via OCR + ink"},
        {"id": "M06", "desc": "F-001 with 3 filled fields rendered to JPEG, rotated 3 degrees", "mime": "image/jpeg", "data": render(fill(F001, 3), "JPEG", rotate=3), "expect": "3 filled via OCR + deskew"},
        {"id": "M07", "desc": "F-002 blank rendered to JPEG (150 dpi)", "mime": "image/jpeg", "data": render(f2, "JPEG", dpi=150), "expect": "recognised via OCR"},
        {"id": "M08", "desc": "Corrupt PDF (first 5 KB of F-001)", "mime": "application/pdf", "data": f1[:5000], "expect": "safe error"},
        {"id": "M09", "desc": "Plain text declared as PDF", "mime": "application/pdf", "data": b"neutral placeholder text", "expect": "safe error"},
        {"id": "M10", "desc": "Unsupported type (text/plain)", "mime": "text/plain", "data": b"neutral placeholder text", "expect": "unsupported"},
        {"id": "M11", "desc": "Oversized upload (11 MB of zeros declared as PNG)", "mime": "image/png", "data": b"\x00" * (11 * 1024 * 1024), "expect": "rejected (size)"},
        {"id": "M12", "desc": "Unrelated one-page PDF (neutral text)", "mime": "application/pdf", "data": _neutral_pdf(), "expect": "not recognised"},
    ]


def _neutral_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    for i in range(5):
        page.insert_text((72, 100 + 20 * i), "Neutral placeholder line " * 3, fontsize=11)
    return doc.tobytes()


def summarise_form(d: dict) -> dict:
    fields = d.get("fields") or []
    return {"recognised": d.get("recognised"), "form_doc_id": d.get("form_doc_id"), "method": d.get("method"),
            "fields": len(fields), "filled": sum(f.get("status") == "filled" for f in fields),
            "empty": sum(f.get("status") == "empty" for f in fields),
            "unreadable": sum(f.get("status") == "unreadable" for f in fields), "error": d.get("error")}


def summarise_dossier(d: dict) -> dict:
    return {"recognized": d.get("recognized"), "missing_fields": len(d.get("missing_fields") or []),
            "official_checklist_available": d.get("official_checklist_available"),
            "requirements": len(d.get("official_requirements") or d.get("requirements") or []),
            "completeness_certified": d.get("complete") if "complete" in d else None}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8002")
    args = ap.parse_args()
    client = httpx.Client(timeout=300)
    records = []
    for case in cases():
        body = {"filename": "upload", "mime_type": case["mime"], "data_b64": base64.b64encode(case["data"]).decode(), "language": "en"}
        rec = {k: case[k] for k in ("id", "desc", "mime", "expect")} | {"bytes": len(case["data"])}
        for path, summ in (("/agents/form-check", summarise_form), ("/agents/dossier-check", summarise_dossier)):
            t = time.perf_counter()
            r = client.post(args.base + path, json=body)
            dt = round(time.perf_counter() - t, 2)
            try:
                data = r.json()
            except ValueError:
                data = {}
            rec[path.rsplit("/", 1)[1]] = {"status": r.status_code, "seconds": dt,
                                           **(summ(data) if r.status_code == 200 else {"detail": str(data)[:160]})}
        records.append(rec)
        print(rec["id"], rec["desc"][:50], "|", rec["form-check"], flush=True)
    out = ROOT / "data" / "evaluation" / "multimodal_eval_results.json"
    out.write_text(json.dumps({"base": args.base, "at": datetime.now(timezone.utc).isoformat(), "records": records},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print("written", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
