"""Sequential latency measurements (3 runs each) on one webhook; run with no other load."""
import base64
import glob
import json
import statistics
import sys
import time

import fitz
import httpx

URL = sys.argv[1]
f1 = glob.glob("data/raw/rne-form-f001-natural-person-registration/*.pdf")[0]
pdf = base64.b64encode(open(f1, "rb").read()).decode()
with fitz.open(f1) as d:
    png = base64.b64encode(d[0].get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).tobytes("png")).decode()
OPS = [
    ("passport_checklist_fr", {"text": "Quelles pièces fournir pour une première demande de passeport ? J'habite en Tunisie.", "language": "fr", "context": {}}),
    ("cin_checklist_fr", {"text": "Quelles pièces pour une CIN après une perte ?", "language": "fr", "context": {}}),
    ("rne_fee", {"text": "Quelle redevance pour RNE C 012 ?", "language": "fr", "context": {}}),
    ("rne_deadline", {"text": "Quel délai légal pour RNE C 001 ?", "language": "fr", "context": {}}),
    ("legal_article", {"text": "ماذا ينص الفصل 16 من قانون السجل الوطني للمؤسسات 52 لسنة 2018؟", "language": "ar", "context": {}}),
    ("multiturn_followup", None),
    ("passport_checklist_en", {"text": "What documents are needed to renew a Tunisian passport? I live in Tunisia.", "language": "en", "context": {}}),
    ("form_check_pdf", {"file": {"filename": "f001.pdf", "mime_type": "application/pdf", "data_b64": pdf}, "language": "fr"}),
    ("form_check_png", {"file": {"filename": "f001.png", "mime_type": "image/png", "data_b64": png}, "language": "fr"}),
    ("dossier_pdf", {"file": {"filename": "f001.pdf", "mime_type": "application/pdf", "data_b64": pdf}, "language": "fr", "mode": "dossier"}),
]
out = {}
with httpx.Client(timeout=900) as c:
    for name, body in OPS:
        times = []
        for _ in range(3):
            if name == "multiturn_followup":
                ctx = c.post(URL, json={"text": "Quelle redevance pour RNE C 012 ?", "language": "fr", "context": {}}).json().get("context")
                body = {"text": "Et le délai ?", "language": "fr", "context": ctx}
            t = time.monotonic()
            r = c.post(URL, json=body)
            r.raise_for_status()
            times.append(round(time.monotonic() - t, 2))
        out[name] = {"runs_s": times, "median_s": statistics.median(times), "agent": r.json().get("agent")}
        print(name, out[name], flush=True)
json.dump(out, open(sys.argv[2], "w"), indent=1)
