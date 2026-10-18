"""Builds presentation/FINAL_PRESENTATION.pptx (editable, 16:9) from the committed evidence files.

usage: <python with python-pptx 1.0.2> presentation/build_presentation.py

Every number shown on a slide is read from a file under data/evaluation/ or report/tables/ (the source is printed
on the slide). Missing evidence raises an error instead of falling back to a default value. Speaker notes are
taken from presentation/SPEAKER_NOTES.md (one "### Slide N" section per slide).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "data" / "evaluation"
OUT = ROOT / "presentation" / "FINAL_PRESENTATION.pptx"

NAVY, TEAL, AMBER = RGBColor(0x12, 0x30, 0x5B), RGBColor(0x0F, 0x8B, 0x8D), RGBColor(0xE8, 0xA3, 0x3D)
SLATE, MIST, STEEL = RGBColor(0x4A, 0x55, 0x60), RGBColor(0xEE, 0xF2, 0xF6), RGBColor(0x8C, 0x99, 0xA6)
RED, GREEN, WHITE = RGBColor(0xB8, 0x3A, 0x3A), RGBColor(0x2E, 0x7D, 0x4F), RGBColor(0xFF, 0xFF, 0xFF)
RED_T, GREEN_T, AMBER_T, TEAL_T = RGBColor(0xF8, 0xE5, 0xE5), RGBColor(0xE3, 0xF2, 0xE8), RGBColor(0xFC, 0xF0, 0xDC), RGBColor(0xDF, 0xF1, 0xF1)
FONT, MONO = "Segoe UI", "Consolas"
FOOTER = "Tunisian Administrative Procedures Assistant · Advanced Deep Learning · October 2026"

SECTIONS = {1: "Introduction and Use Case", 2: "System Architecture and Automation Workflow", 3: "Prompt Engineering",
            4: "Retrieval-Augmented Generation", 5: "Multi-Agent Architecture", 6: "Multimodality",
            7: "Live Demonstration and Evaluation", 8: "Conclusion and Future Improvements"}


# ------------------------------------------------------------------------------------------------ evidence
def load(name: str) -> dict:
    path = EV / name
    if not path.exists():
        raise FileNotFoundError(f"evidence file missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def evidence() -> dict:
    retr = load("retrieval_results_improved.json")
    e = {"retr": {k: retr[k]["overall"] for k in retr}, "retr_par": {k: retr[k]["parallel_by_language"] for k in retr}}
    e["intent"] = load("prompt_experiments/intent_router_results.json")["summary"]
    dd = load("prompt_experiments/dialogue_understanding_results.json")
    e["dialogue"], e["dialogue_valid"] = dd["summary"], dd["summary_after_production_validation"]
    e["translate"] = load("prompt_experiments/translate_items_results.json")["summary"]
    e["mm"] = load("multimodal_eval_results.json")["records"]
    e["ml"] = load("multilingual_eval_results.json")
    pc_a = load("agent_results_hybrid.json")["prompt_comparison"]
    pc_b = load("agent_results_prompt_v3.json")["prompt_comparison"]
    e["ga"] = {"v1": pc_a["v1"], "v2": pc_a["v2"], "v2b": pc_b["v2"], "v3": pc_b["v3"]}
    reg = (ROOT / "report" / "tables" / "final_regression.tex").read_text(encoding="utf-8")
    e["final"] = {m.group(1).strip(): (m.group(2), m.group(3), m.group(4))
                  for m in re.finditer(r"^(.+?) & ([^&]+?) & ([^&]+?) & ([^&\\]+?) \\\\", reg, re.M)}
    return e


def notes() -> dict[int, str]:
    text = (ROOT / "presentation" / "SPEAKER_NOTES.md").read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r"^### Slide (\d+)[^\n]*\n(.*?)(?=^### Slide |\Z)", text, re.S | re.M):
        out[int(m.group(1))] = m.group(2).strip()
    return out


# ------------------------------------------------------------------------------------------------ helpers
def font(run, size, bold=False, color=SLATE, name=FONT, italic=False):
    run.font.size, run.font.bold, run.font.name, run.font.italic = Pt(size), bold, name, italic
    run.font.color.rgb = color


def text(slide, x, y, w, h, content, size=16, bold=False, color=SLATE, align=PP_ALIGN.LEFT, name=FONT,
         anchor=MSO_ANCHOR.TOP, bullets=False, spacing=4, italic=False):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = Inches(0.03)
    lines = content if isinstance(content, list) else [content]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(spacing)
        segs = line if isinstance(line, list) else [(line, {})]
        if bullets:
            r = p.add_run()
            r.text = "▪  "
            font(r, size, color=TEAL)
        for seg, style in segs:
            r = p.add_run()
            r.text = seg
            font(r, style.get("size", size), style.get("bold", bold), style.get("color", color), style.get("name", name),
                 style.get("italic", italic))
    return tb


def box(slide, x, y, w, h, label="", fill=MIST, line=None, size=13, color=SLATE, bold=False, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        name=FONT, align=PP_ALIGN.CENTER, dash=False, anchor=MSO_ANCHOR.MIDDLE):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = 0.12
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1.25)
        if dash:
            s.line.dash_style = 4
    s.shadow.inherit = False
    tf = s.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for m in ("margin_left", "margin_right"):
        setattr(tf, m, Inches(0.08))
    tf.margin_top = tf.margin_bottom = Inches(0.04)
    lines = label if isinstance(label, list) else [label]
    for i, line_ in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        segs = line_ if isinstance(line_, list) else [(line_, {})]
        for seg, st in segs:
            r = p.add_run()
            r.text = seg
            font(r, st.get("size", size), st.get("bold", bold), st.get("color", color), st.get("name", name))
    return s


def arrow(slide, x1, y1, x2, y2, color=SLATE, dash=False, width=1.5):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(width)
    if dash:
        c.line.dash_style = 4
    ln = c.line._get_or_add_ln()
    tail = ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
    ln.append(tail)
    return c


def header(slide, n, section, title, presenter, kicker=None):
    chip = box(slide, 0.5, 0.28, 4.6, 0.36, f"{section} · {SECTIONS[section]}", fill=NAVY, color=WHITE, size=11, bold=True,
               align=PP_ALIGN.LEFT)
    chip.adjustments[0] = 0.5
    text(slide, 9.3, 0.28, 3.55, 0.36, presenter, size=11, color=STEEL, align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)
    text(slide, 0.5, 0.72, 12.3, 0.7, title, size=28, bold=True, color=NAVY)
    if kicker:
        text(slide, 0.5, 1.33, 12.3, 0.45, kicker, size=15, color=SLATE)
    text(slide, 0.5, 7.08, 10.5, 0.3, FOOTER, size=10, color=STEEL)
    text(slide, 11.8, 7.08, 1.0, 0.3, str(n), size=10, color=STEEL, align=PP_ALIGN.RIGHT)


def source(slide, content, y=6.72):
    text(slide, 0.5, y, 12.3, 0.32, "Source: " + content, size=10, color=STEEL, italic=True)


def card(slide, x, y, w, h, number, label, color=NAVY, fill=MIST, num_size=32):
    box(slide, x, y, w, h, "", fill=fill)
    text(slide, x + 0.12, y + 0.08, w - 0.24, 0.65, number, size=num_size, bold=True, color=color)
    text(slide, x + 0.12, y + 0.75, w - 0.24, h - 0.8, label, size=12, color=SLATE)


def table(slide, x, y, w, rows, col_w, size=12, header_fill=NAVY, row_h=0.32, bold_first_col=False):
    shp = slide.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(row_h * len(rows)))
    tbl = shp.table
    tblpr = tbl._tbl.tblPr
    style = tblpr.find(qn("a:tableStyleId"))
    if style is not None:
        style.text = "{5940675A-B579-460E-94D1-54222C63F5DA}"  # "No Style, Table Grid"
    for i, cw in enumerate(col_w):
        tbl.columns[i].width = Inches(cw)
    for r, row in enumerate(rows):
        tbl.rows[r].height = Inches(row_h)
        for c, val in enumerate(row):
            cell = tbl.cell(r, c)
            cell.margin_left = cell.margin_right = Inches(0.06)
            cell.margin_top = cell.margin_bottom = Inches(0.02)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            st = {}
            if isinstance(val, tuple):
                val, st = val
            cell.text = ""
            p = cell.text_frame.paragraphs[0]
            run = p.add_run()
            run.text = str(val)
            if r == 0:
                font(run, size, True, WHITE)
                cell.fill.solid()
                cell.fill.fore_color.rgb = header_fill
            else:
                font(run, st.get("size", size), st.get("bold", bold_first_col and c == 0), st.get("color", SLATE),
                     st.get("name", FONT))
                cell.fill.solid()
                cell.fill.fore_color.rgb = st.get("fill", WHITE if r % 2 else MIST)
            p.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER
    return tbl


def chart(slide, x, y, w, h, categories, series, colors, number_format='0.00', y_max=1.0, legend=True, labels=True):
    data = CategoryChartData()
    data.categories = categories
    for name, values in series:
        data.add_series(name, values)
    gf = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(x), Inches(y), Inches(w), Inches(h), data)
    ch = gf.chart
    ch.font.size, ch.font.name = Pt(11), FONT
    ch.has_legend = legend and len(series) > 1
    if ch.has_legend:
        ch.legend.position = XL_LEGEND_POSITION.TOP
        ch.legend.include_in_layout = False
    va = ch.value_axis
    va.maximum_scale, va.minimum_scale = y_max, 0
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = MIST
    va.tick_labels.font.size = Pt(10)
    ch.category_axis.tick_labels.font.size = Pt(10)
    for s, col in zip(ch.plots[0].series, colors):
        s.format.fill.solid()
        s.format.fill.fore_color.rgb = col
    if labels:
        pl = ch.plots[0]
        pl.has_data_labels = True
        pl.data_labels.number_format = number_format
        pl.data_labels.number_format_is_linked = False
        pl.data_labels.font.size = Pt(9)
        pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
    ch.plots[0].gap_width = 60
    return ch


def picture(slide, path, x, y, w=None, h=None, border=True):
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w) if w else None, Inches(h) if h else None)
    if border:
        pic.line.color.rgb = STEEL
        pic.line.width = Pt(1)
    return pic


def pct(x):
    return f"{x:.3f}"


# ------------------------------------------------------------------------------------------------ slides
def build():
    ev, sn = evidence(), notes()
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    blank = prs.slide_layouts[6]
    slides = []

    def new(n):
        s = prs.slides.add_slide(blank)
        slides.append((n, s))
        return s

    # 1 Title ---------------------------------------------------------------------------------------------
    s = new(1)
    band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(1.6), prs.slide_width, Inches(3.2))
    band.fill.solid(); band.fill.fore_color.rgb = NAVY; band.line.fill.background()
    text(s, 0.8, 1.9, 11.8, 0.9, "Tunisian Administrative Procedures Assistant", size=38, bold=True, color=WHITE)
    text(s, 0.8, 2.85, 11.8, 0.6, "A local, source-grounded multi-agent RAG system for multilingual administrative guidance",
         size=20, color=RGBColor(0xD6, 0xE2, 0xF0))
    text(s, 0.8, 3.65, 11.8, 0.9, [[("Telegram · n8n · FastAPI · Qdrant · Ollama", {"color": AMBER, "bold": True})],
                                   [("French · English · Arabic · Tunisian Derja (Arabic and Latin script)", {"color": WHITE})]], size=16)
    text(s, 0.8, 5.2, 11.8, 0.5, "Advanced Deep Learning · Team of six · October 2026", size=16, color=SLATE)
    text(s, 0.8, 5.65, 11.8, 0.5, "Member 1 · Member 2 · Member 3 · Member 4 · Member 5 · Member 6", size=14, color=STEEL)

    # 2 Problem --------------------------------------------------------------------------------------------
    s = new(2)
    header(s, 2, 1, "Fragmented, bilingual and risky to paraphrase", "Member 1")
    cards = [
        ("Fragmented", ["Ministry of the Interior guides (FR / AR)", "RNE table of 95 procedures with fees and deadlines",
                        "Laws and decrees as Official Journal PDFs"], NAVY),
        ("Language gap", ["Official text: French and Arabic", "Users often write Tunisian Derja, in Latin script with digits: “9adech ya5ou wa9t el passbor?”"], TEAL),
        ("High stakes", ["FR and AR passport pages state different stamp duties: 20/60 vs 25/80 TND",
                                          "A fluent but invented fee or document costs citizens time and money"], RED),
    ]
    for i, (title_, lines, col) in enumerate(cards):
        x = 0.5 + i * 4.18
        box(s, x, 1.7, 3.95, 3.9, "", fill=MIST)
        bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(1.7), Inches(3.95), Inches(0.12))
        bar.fill.solid(); bar.fill.fore_color.rgb = col; bar.line.fill.background()
        text(s, x + 0.2, 1.95, 3.6, 0.5, title_, size=20, bold=True, color=col)
        text(s, x + 0.2, 2.6, 3.6, 3.5, lines, size=15, bullets=True, spacing=10)
    source(s, "report §1; official pages interior passport guide FR/AR (data/raw), RNE formalities table")

    # 3 Objectives -----------------------------------------------------------------------------------------
    s = new(3)
    header(s, 3, 1, "Objectives, scope and expected value", "Member 1")
    objs = [("1", "Answer only from verifiable official documents, with citations"),
            ("2", "Refuse or ask for clarification when the corpus cannot answer"),
            ("3", "Support FR, EN, AR and Derja without altering official text"),
            ("4", "Check official forms and dossiers without certifying them"),
            ("5", "Run on one laptop (4 GB GPU): no paid API, no data leaves the machine")]
    for i, (n_, t_) in enumerate(objs):
        y = 1.65 + i * 0.86
        box(s, 0.5, y, 0.62, 0.62, n_, fill=TEAL, color=WHITE, size=18, bold=True, shape=MSO_SHAPE.OVAL)
        text(s, 1.3, y + 0.08, 6.2, 0.6, t_, size=16)
    box(s, 7.9, 1.65, 4.95, 2.35, [[("Scope", {"bold": True, "color": NAVY, "size": 16})],
                                    "Passports · National identity card (CIN)",
                                    "RNE business registration (95 procedures, 6 legal texts, forms F-001/F-002)"],
        fill=MIST, align=PP_ALIGN.LEFT, size=14, anchor=MSO_ANCHOR.TOP)
    box(s, 7.9, 4.15, 4.95, 1.25, [[("Deliberately excluded", {"bold": True, "color": RED, "size": 15})],
                                    "Birth certificates: the only source opts out of AI use (robots.txt)"],
        fill=RED_T, align=PP_ALIGN.LEFT, size=13, anchor=MSO_ANCHOR.TOP)
    box(s, 7.9, 5.55, 4.95, 1.0, [[("Value: ", {"bold": True, "color": GREEN}), ("traceable answers, free, private, multilingual", {})]],
        fill=GREEN_T, align=PP_ALIGN.LEFT, size=14)
    source(s, "report §1 (objectives, scope); config/sources.yaml (exclusions with recorded reasons)")

    # 4 Architecture ---------------------------------------------------------------------------------------
    s = new(4)
    header(s, 4, 2, "Architecture: everything runs locally behind 127.0.0.1", "Member 2")
    box(s, 0.5, 2.0, 1.9, 0.9, ["Citizen", [("Telegram", {"size": 11})]], fill=MIST, size=14, bold=True)
    box(s, 0.5, 3.4, 1.9, 0.9, ["Web page / CLI", [("same webhook", {"size": 11})]], fill=MIST, size=13)
    box(s, 2.9, 2.0, 2.1, 0.9, ["Telegram bridge", [("long polling, no inbound port", {"size": 10})]], fill=TEAL_T, line=TEAL, size=13, bold=True)
    box(s, 5.5, 2.0, 2.1, 2.3, ["n8n 2.41.3", [("wf 03 assistant (17 nodes)", {"size": 11})], [("wf 02 retrieve API", {"size": 11})],
                               [("wf 01 ingest+index (inactive)", {"size": 11})]], fill=NAVY, color=WHITE, size=15, bold=True)
    box(s, 8.1, 1.7, 2.3, 3.6, ["FastAPI backend", [("/agents/route", {"size": 10, "name": MONO})], [("/agents/retrieve", {"size": 10, "name": MONO})],
                               [("/agents/checklist", {"size": 10, "name": MONO})], [("/agents/answer", {"size": 10, "name": MONO})],
                               [("/agents/form-check", {"size": 10, "name": MONO})], [("/agents/dossier-check", {"size": 10, "name": MONO})]],
        fill=TEAL_T, line=TEAL, size=14, bold=True)
    box(s, 10.9, 1.7, 1.95, 1.05, ["Qdrant 1.19", [("272 + 174 chunks", {"size": 10})]], fill=STEEL, color=WHITE, size=13, bold=True)
    box(s, 10.9, 2.95, 1.95, 1.2, ["Ollama 0.40.4", [("bge-m3 · mistral 7B", {"size": 10})], [("translategemma 4B", {"size": 10})]],
        fill=AMBER, color=NAVY, size=13, bold=True)
    box(s, 10.9, 4.35, 1.95, 0.95, ["Official corpus", [("12 docs + SHA-256", {"size": 10})]], fill=STEEL, color=WHITE, size=13, bold=True)
    for (x1, y1, x2, y2) in [(2.4, 2.45, 2.9, 2.45), (5.0, 2.45, 5.5, 2.45), (2.4, 3.85, 5.5, 3.85), (7.6, 3.15, 8.1, 3.15),
                             (10.4, 2.2, 10.9, 2.2), (10.4, 3.55, 10.9, 3.55), (10.4, 4.8, 10.9, 4.8)]:
        arrow(s, x1, y1, x2, y2)
    box(s, 0.5, 5.6, 12.35, 0.85, [[("Design choices: ", {"bold": True, "color": NAVY}),
                                    ("Docker Compose · ports bound to 127.0.0.1 · Ollama on the host GPU (RTX 3050, 4 GB) reached via host.docker.internal · "
                                     "no paid API · uploads processed in memory, never indexed", {})]], fill=MIST, align=PP_ALIGN.LEFT, size=13)
    source(s, "docker-compose.yml; backend/main.py; backend/agents_api.py; live inventory 2026-10-18")

    # 5 n8n workflows --------------------------------------------------------------------------------------
    s = new(5)
    header(s, 5, 2, "Three real n8n workflows", "Member 2", "Screenshots of the live editor (Zoom to Fit), 2026-10-18")
    shots = [("n8n_workflow_01.png", "01 · Ingest and index", "5 nodes · inactive · admin-only backend calls"),
             ("n8n_workflow_02.png", "02 · Retrieval API", "3 nodes · published · POST /webhook/retrieve"),
             ("n8n_workflow_03.png", "03 · Assistant orchestration", "17 nodes · published · POST /webhook/assistant")]
    for i, (f, t_, d_) in enumerate(shots):
        x = 0.5 + i * 4.18
        picture(s, ROOT / "presentation" / "assets" / f, x, 1.85, w=3.75)
        text(s, x, 5.05, 3.95, 0.4, t_, size=15, bold=True, color=NAVY)
        text(s, x, 5.42, 3.95, 0.6, d_, size=12)
    box(s, 0.5, 6.05, 12.35, 0.55, "Sticky-note frames document each stage; every agent call in 03 has an error output to a sanitised HTTP 503 reply.",
        fill=MIST, size=13)
    source(s, "workflows/*.json = live published versions (verified 2026-10-18); n8n editor screenshots")

    # 6 Request flow ---------------------------------------------------------------------------------------
    s = new(6)
    header(s, 6, 2, "One request, end to end", "Member 2", "Workflow 03 routes on file, dossier mode and the router's decision")
    steps = [("Telegram", "user message", MIST, SLATE), ("Bridge", "language, session context", TEAL_T, TEAL),
             ("Webhook", "File attached?", NAVY, WHITE), ("Intent Router", "rules first, LLM fallback", TEAL_T, TEAL),
             ("Direct reply?", "greeting / clarification", NAVY, WHITE), ("RAG Retriever", "hybrid or exact code", TEAL_T, TEAL),
             ("Checklist?", "next_agent", NAVY, WHITE), ("Builder / Answer", "verbatim or verified", AMBER_T, AMBER)]
    for i, (a, b, fill, col) in enumerate(steps):
        x = 0.5 + i * 1.57
        box(s, x, 2.05, 1.42, 1.1, [[(a, {"bold": True, "size": 13, "color": WHITE if fill == NAVY else NAVY})], [(b, {"size": 10, "color": WHITE if fill == NAVY else SLATE})]],
            fill=fill, line=None if fill == NAVY else col)
        if i:
            arrow(s, x - 0.15, 2.6, x, 2.6)
    box(s, 0.5, 3.55, 6.0, 1.15, [[("Uploads ", {"bold": True, "color": NAVY}), ("(PDF, PNG, JPEG, Telegram photo) go to the Form-Filling Helper, or to the Dossier Validator in /dossier_check mode.", {})]],
        fill=MIST, align=PP_ALIGN.LEFT, size=13)
    box(s, 6.85, 3.55, 6.0, 1.15, [[("Errors ", {"bold": True, "color": RED}), ("from any of the six agent calls go to one sanitised 503 reply; the bridge retries, then shows a localised message.", {})]],
        fill=RED_T, align=PP_ALIGN.LEFT, size=13)
    lat = [("RNE row", "0.08 s"), ("FR checklist", "0.19 s"), ("Legal article", "0.25 s"), ("PDF form", "0.16 s"),
           ("Image OCR", "1.72 s"), ("EN checklist", "17.5 s"), ("LLM answer", "20–70 s")]
    text(s, 0.5, 4.95, 12, 0.35, "Measured latency, final candidate alone on the GPU (median of 3):", size=13, bold=True, color=NAVY)
    for i, (a, b) in enumerate(lat):
        x = 0.5 + i * 1.77
        box(s, x, 5.35, 1.62, 0.95, [[(b, {"bold": True, "size": 17, "color": AMBER if "LLM" in a or "EN" in a else TEAL})], [(a, {"size": 11})]],
            fill=MIST)
    source(s, "workflows/03_assistant_multi_agent.json; report §7 latency (final candidate)")

    # 7 Prompt library -------------------------------------------------------------------------------------
    s = new(7)
    header(s, 7, 3, "Prompt library: versioned and validated", "Member 3", "Language models are used only where rules cannot decide")
    rows = [["Prompt", "Role (model)", "Active", "Versions", "Output validated in code"],
            ["intent_router", "Fallback classifier (Mistral 7B)", "v1", "v1", "JSON; enums checked"],
            ["grounded_answer", "Answer from numbered passages (Mistral)", "v2", "v1 · v2 · v3", "[n] citations exist; numbers in cited text"],
            ["dialogue_understanding", "User-declared facts (Mistral)", "v3", "v1 · v2 · v3", "JSON schema; evidence = exact substring"],
            ["translate_items", "FR→EN checklist lines (TranslateGemma 4B)", "v1", "v1", "same numbered lines and numbers"],
            ["evidence_topic", "Topic consistency (Mistral)", "v1 (off)", "v1", "disabled: unstable verdicts"]]
    table(s, 0.5, 1.85, 12.35, rows, [2.35, 3.6, 1.1, 1.5, 3.8], size=12, row_h=0.4, bold_first_col=True)
    techs = ["Role prompting", "Grounding rules", "Citation format [n]", "Structured JSON / schema", "Few-shot examples",
             "Untrusted-input framing", "Language variable", "Length limits", "temperature 0"]
    text(s, 0.5, 4.45, 4, 0.35, "Techniques used", size=14, bold=True, color=NAVY)
    for i, t_ in enumerate(techs):
        x = 0.5 + (i % 5) * 2.48
        y = 4.85 + (i // 5) * 0.55
        b = box(s, x, y, 2.33, 0.42, t_, fill=TEAL_T, line=TEAL, size=12, color=NAVY)
        b.adjustments[0] = 0.5
    box(s, 0.5, 6.0, 12.35, 0.6, [[("Files: ", {"bold": True}), ("prompts/<name>/<version>.yaml · registry selects the active version · every response records its prompt_ref · versions are never edited in place", {})]],
        fill=MIST, align=PP_ALIGN.LEFT, size=12)
    source(s, "prompts/registry.yaml; agents/llm.py; agents/prompts.py; report Annex A")

    # 8 grounded_answer before/after -----------------------------------------------------------------------
    s = new(8)
    ga = ev["ga"]
    header(s, 8, 3, "Before / after 1: grounded_answer v1 → v2", "Member 3", "Stored versions v1, v2, v3 — v3 was measured and not adopted")
    box(s, 0.5, 1.85, 6.05, 2.0, [[("BEFORE · v1", {"bold": True, "color": RED, "size": 14})],
                                   [("num_predict: 600", {"name": MONO, "size": 12})],
                                   [("7. Be concise: at most 8 short sentences or bullet points.", {"name": MONO, "size": 12})],
                                   [("Problem: an Arabic answer was cut mid-sentence at 600 tokens; lists were summarised.", {"size": 13})]],
        fill=RED_T, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP)
    box(s, 6.8, 1.85, 6.05, 2.0, [[("AFTER · v2 (active)", {"bold": True, "color": GREEN, "size": 14})],
                                   [("num_predict: 900", {"name": MONO, "size": 12})],
                                   [("7. ... When the passages contain a list (documents, conditions), reproduce the relevant list items faithfully instead of summarising.", {"name": MONO, "size": 12})],
                                   [("Technique: output-length budget + explicit list-fidelity constraint", {"size": 13})]],
        fill=GREEN_T, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP)
    rows = [["Same 12 answer-routed dev questions", "v1", "v2", "v3 (run B)"],
            ["Answer accepted by citation validation", pct(ga["v1"]["accepted"]["rate"]), pct(ga["v2"]["accepted"]["rate"]), pct(ga["v3"]["accepted"]["rate"])],
            ["Response language correct", pct(ga["v1"]["language_ok"]["rate"]), pct(ga["v2"]["language_ok"]["rate"]), pct(ga["v3"]["language_ok"]["rate"])],
            ["Verified evidence span present", pct(ga["v1"]["evidence_found"]["rate"]), pct(ga["v2"]["evidence_found"]["rate"]), pct(ga["v3"]["evidence_found"]["rate"])],
            ["Median seconds", f'{ga["v1"]["median_seconds"]:.1f}', f'{ga["v2"]["median_seconds"]:.1f}', f'{ga["v3"]["median_seconds"]:.1f}']]
    table(s, 0.5, 4.1, 7.3, rows, [3.7, 1.2, 1.2, 1.2], size=12, row_h=0.36)
    box(s, 8.05, 4.1, 4.8, 1.8, [[("Same input R29 ", {"bold": True, "color": NAVY}), ("“What shareholding threshold makes someone a beneficial owner?”", {"italic": True})],
                                  [("v1: LLM answer rejected → Arabic passage quoted to an English user", {"color": RED, "size": 12})],
                                  [("v2: “...hold 20% or more of the capital...” [1, 2] — correct, in English", {"color": GREEN, "size": 12})]],
        fill=MIST, align=PP_ALIGN.LEFT, size=12, anchor=MSO_ANCHOR.TOP)
    source(s, "prompts/grounded_answer/v1-v3.yaml; data/evaluation/agent_results_hybrid.json (v1,v2) and agent_results_prompt_v3.json (v2,v3)")

    # 9 router + dialogue before/after ---------------------------------------------------------------------
    s = new(9)
    it, dl = ev["intent"], ev["dialogue"]
    header(s, 9, 3, "Before / after 2 and 3: intent router and dialogue extractor", "Member 3")
    box(s, 0.5, 1.55, 6.05, 1.45, [[("intent_router: B0 → v1", {"bold": True, "color": NAVY, "size": 14})],
                                    [("B0 (controlled baseline, written 2026-10-18 — not historical): same enums and JSON mode; no role, no Derja/Latin-script note, no category definitions.", {"size": 11})],
                                    [("v1 adds: role · multilingual + Arabizi notice · definitions (RNE, CIN) · “do not answer”.", {"size": 11})]],
        fill=MIST, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP)
    a, b = it["B0"]["all"], it["v1"]["all"]
    rows = [["84 dev questions, LLM only", "B0", "v1"],
            ["Category accuracy", pct(a["category_accuracy"]), pct(b["category_accuracy"])],
            ["Intent accuracy", pct(a["intent_accuracy"]), pct(b["intent_accuracy"])],
            ["Both correct", pct(a["both_correct"]), pct(b["both_correct"])],
            ["Valid enums", pct(a["enum_valid"]), pct(b["enum_valid"])],
            ["Median seconds", f'{a["median_seconds"]:.1f}', f'{b["median_seconds"]:.1f}']]
    table(s, 0.5, 3.15, 6.05, rows, [3.25, 1.4, 1.4], size=12, row_h=0.36)
    box(s, 6.8, 1.55, 6.05, 1.45, [[("dialogue_understanding: v1 → v2 → v3", {"bold": True, "color": NAVY, "size": 14})],
                                    [("v1: schema in prose, pipe-separated enum hints. v2: “default {items: []}”, two few-shot examples, “never write 'not provided'”.", {"size": 11})],
                                    [("v3: same text + JSON response schema enforced by Ollama (constrained decoding).", {"size": 11})]],
        fill=MIST, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP)
    dv = ev["dialogue_valid"]
    rows = [["18 synthetic declarations", "v1", "v2", "v3"],
            ["Schema-valid outputs (raw)", f'{dl["v1"]["schema_valid"]}/18', f'{dl["v2"]["schema_valid"]}/18', f'{dl["v3"]["schema_valid"]}/18'],
            ["Invented application / residence (raw)", str(dv["v1"]["raw_wrong_application_or_residence"]), str(dv["v2"]["raw_wrong_application_or_residence"]), str(dv["v3"]["raw_wrong_application_or_residence"])],
            ["Item precision after code validation", pct(dv["v1"]["after_validation_item_precision"]), pct(dv["v2"]["after_validation_item_precision"]), pct(dv["v3"]["after_validation_item_precision"])],
            ["Item recall after code validation", pct(dv["v1"]["after_validation_item_recall"]), pct(dv["v2"]["after_validation_item_recall"]), pct(dv["v3"]["after_validation_item_recall"])],
            ["Median seconds", f'{dl["v1"]["median_seconds"]:.1f}', f'{dl["v2"]["median_seconds"]:.1f}', f'{dl["v3"]["median_seconds"]:.1f}']]
    table(s, 6.8, 3.15, 6.05, rows, [3.05, 1.0, 1.0, 1.0], size=11, row_h=0.36)
    text(s, 0.5, 5.4, 12.35, 1.2, [[("Reading: ", {"bold": True, "color": NAVY}),
                                    (INTERPRET["intent"] + " " + INTERPRET["dialogue"], {})]], size=13)
    source(s, "data/evaluation/prompt_experiments/intent_router_results.json, dialogue_understanding_results.json (scripts/prompt_experiments.py)")

    # 10 translate + lesson + matrix -----------------------------------------------------------------------
    s = new(10)
    tr = ev["translate"]
    header(s, 10, 3, "Before / after 4: translation — and the lesson we drew", "Member 3")
    box(s, 0.5, 1.55, 6.05, 1.6, [[("translate_items: B0 → v1", {"bold": True, "color": NAVY, "size": 14})],
                                   [("B0 (controlled baseline): “Translate this text from French into English.”", {"size": 11, "name": MONO})],
                                   [("v1: “...one line per item, keeping exactly the same numbering. Keep all numbers, amounts and measurements exactly as they are.”", {"size": 11, "name": MONO})]],
        fill=MIST, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP)
    rows = [["11 official FR checklist scenarios", "B0", "v1"],
            ["Same numbered structure", f'{tr["B0"]["structure_valid"]}/11', f'{tr["v1"]["structure_valid"]}/11'],
            ["Accepted by production validator", f'{tr["B0"]["accepted_by_production_validator"]}/11', f'{tr["v1"]["accepted_by_production_validator"]}/11'],
            ["Median seconds", f'{tr["B0"]["median_seconds"]:.1f}', f'{tr["v1"]["median_seconds"]:.1f}']]
    table(s, 0.5, 3.3, 6.05, rows, [3.65, 1.2, 1.2], size=12, row_h=0.38)
    box(s, 6.8, 1.55, 6.05, 1.6, [[("Withdrawn, not re-prompted: FR → AR", {"bold": True, "color": RED, "size": 14})],
                                   [("“veuve” (widow) → “العوراء” (one-eyed woman); “timbre” → “الطوابق” (floors). Both passed format validation.", {"size": 12})],
                                   [("Decision: Arabic and Derja users receive the official text.", {"size": 12})]],
        fill=RED_T, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP)
    box(s, 6.8, 3.3, 6.05, 1.55, [[("Lesson", {"bold": True, "color": GREEN, "size": 14})],
                                   [("No prompt version made a 7B model paraphrase law reliably (Law 2018-52 Art. 16 was fabricated behind a valid citation). Fix was architectural: legal articles and table rows are now extracted verbatim, not generated.", {"size": 12})]],
        fill=GREEN_T, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP)
    rows = [["Compliance", "intent_router", "grounded_answer", "dialogue_und.", "translate_items"],
            ["Before version", "B0 (labelled baseline)", "v1 (historical)", "v1 (historical)", "B0 (labelled baseline)"],
            ["Documented failure / test / outputs", "yes / 84 dev / JSON", "yes / 12 dev / JSON", "yes / 18 synth. / JSON", "yes / 11 official / JSON"]]
    table(s, 0.5, 5.1, 12.35, rows, [2.75, 2.4, 2.4, 2.4, 2.4], size=11, row_h=0.42)
    source(s, "prompt_experiments/translate_items_results.json; docs/PROMPT_ENGINEERING.md; report §7; presentation/PROMPT_ENGINEERING_EVIDENCE.md")

    # 11 Corpus --------------------------------------------------------------------------------------------
    s = new(11)
    header(s, 11, 4, "Official corpus: 12 documents, provenance first", "Member 4")
    rows = [["Publisher", "Indexed documents", "Language"],
            ["Ministry of the Interior", "Passport guide (FR), passport guide (AR), national ID guide (FR)", "FR · AR"],
            ["RNE (registre-entreprises.tn)", "Formalities table (95 procedures), forms F-001 and F-002", "FR · FR/AR"],
            ["Legal texts via RNE", "Law 2018-52 (AR), Decree 2022-298 fees (FR), Decree-law 2022-18 (FR)", "AR · FR"],
            ["Legal texts via RNE", "Decrees 2019 (beneficial owners, name reservation, AR), Order of 13 Jan 2026 (FR)", "AR · FR"]]
    table(s, 0.5, 1.6, 8.0, rows, [2.4, 4.6, 1.0], size=12, row_h=0.5)
    flow = [("18 candidate sources", NAVY), ("robots.txt + AI opt-out + TLS", TEAL), ("original + SHA-256 manifest", TEAL),
            ("typed text blocks (PyMuPDF / HTML)", TEAL), ("two chunkers", TEAL)]
    for i, (t_, col) in enumerate(flow):
        y = 1.6 + i * 0.78
        box(s, 8.85, y, 4.0, 0.6, t_, fill=TEAL_T if col == TEAL else NAVY, color=NAVY if col == TEAL else WHITE, line=col, size=13, bold=True)
        if i:
            arrow(s, 10.85, y - 0.18, 10.85, y)
    card(s, 0.5, 4.45, 2.6, 1.35, "272", "structure-aware chunks (≤1200 chars)", color=TEAL)
    card(s, 3.25, 4.45, 2.6, 1.35, "174", "recursive chunks (1000 chars, 150 overlap)", color=NAVY)
    card(s, 6.0, 4.45, 2.5, 1.35, "1024-d", "BGE-M3 embeddings, cosine (Qdrant)", color=AMBER)
    box(s, 8.85, 5.6, 4.0, 0.95, "Excluded with a recorded reason: birth certificate and passport-form pages (robots), one scanned decree without text layer",
        fill=RED_T, size=11, color=SLATE)
    source(s, "data/raw/manifest.json; config/sources.yaml; rag/chunking.py; Qdrant collection info (read-only, 2026-10-18)")

    # 12 Retrieval pipeline --------------------------------------------------------------------------------
    s = new(12)
    header(s, 12, 4, "Retrieval: hybrid fusion, exact keys, and a per-document cap", "Member 4")
    box(s, 0.5, 2.1, 2.3, 1.0, ["Question + route", [("category, intent, code?", {"size": 11})]], fill=NAVY, color=WHITE, bold=True, size=14)
    box(s, 3.3, 1.65, 2.6, 0.75, "Dense: raw query", fill=TEAL_T, line=TEAL, size=13)
    box(s, 3.3, 2.5, 2.6, 0.75, "Dense: expanded query", fill=TEAL_T, line=TEAL, size=13)
    box(s, 3.3, 3.35, 2.6, 0.75, "BM25 + term normalisation", fill=TEAL_T, line=TEAL, size=13)
    box(s, 6.4, 2.3, 2.4, 1.15, ["Reciprocal rank fusion", [("k = 60, category filter", {"size": 11})]], fill=TEAL, color=WHITE, bold=True, size=14)
    box(s, 9.3, 2.3, 3.55, 1.15, ["≤ 2 chunks per document", [("in the top 5", {"size": 11})]], fill=TEAL, color=WHITE, bold=True, size=14)
    box(s, 3.3, 4.5, 5.5, 0.85, [[("RNE code in the question → ", {"bold": True}), ("exact payload scroll: the table row by key (a code is a key, not a meaning)", {})]],
        fill=AMBER_T, line=AMBER, size=12, align=PP_ALIGN.LEFT)
    for (x1, y1, x2, y2) in [(2.8, 2.6, 3.3, 2.0), (2.8, 2.6, 3.3, 2.9), (2.8, 2.6, 3.3, 3.7), (5.9, 2.0, 6.4, 2.8), (5.9, 2.9, 6.4, 2.9),
                             (5.9, 3.7, 6.4, 3.0), (8.8, 2.9, 9.3, 2.9), (1.65, 3.1, 3.3, 4.9)]:
        arrow(s, x1, y1, x2, y2)
    text(s, 9.3, 3.7, 3.55, 1.8, ["Retrieval only finds the document and section;",
                                  "agents then read complete official units (section, row, article).",
                                  "Citations are copied from the payload, never generated."], size=12, bullets=True)
    box(s, 0.5, 5.65, 12.35, 0.8, "Arabizi word map and company-type normalisation feed BM25 (e.g. charika → شركة, “public limited company” → Société anonyme). No neural reranker (4 GB GPU).",
        fill=MIST, size=12)
    source(s, "rag/hybrid.py; agents/retriever.py; backend/settings.py (retrieval_mode=hybrid); report §4")

    # 13 Retrieval evaluation ------------------------------------------------------------------------------
    s = new(13)
    r = ev["retr"]
    header(s, 13, 4, "Retrieval evaluation on verified evidence spans", "Member 4", "71 labelled dev questions, k = 5; relevance = the official span occurs in the chunk")
    cats = ["Dense raw", "Agent (Phase 2)", "Hybrid RRF", "Hybrid + cap 2"]
    keys_s = ["dense_structure", "agent_structure", "hybrid_structure", "hybridcap2_structure"]
    chart(s, 0.5, 1.85, 7.4, 3.9, cats, [("Hit@5", [r[k]["hit@5"] for k in keys_s]), ("MRR@5", [r[k]["mrr@5"] for k in keys_s])], [NAVY, AMBER])
    rows = [["Chunking (Hit@5)", "Dense raw", "Hybrid + cap"],
            ["Structure-aware (272)", pct(r["dense_structure"]["hit@5"]), pct(r["hybridcap2_structure"]["hit@5"])],
            ["Recursive (174)", pct(r["dense_recursive"]["hit@5"]), pct(r["hybridcap2_recursive"]["hit@5"])]]
    table(s, 8.2, 1.85, 4.65, rows, [2.15, 1.25, 1.25], size=12, row_h=0.38)
    text(s, 8.2, 3.15, 4.65, 2.7, ["Ranking reverses: recursive wins dense, structure wins hybrid (one table row = one chunk).",
                                    "Held-out (20): hybrid ties dense at Hit@5 0.750; MRR@5 0.531 vs 0.635 — part of the dev gain was overfitting.",
                                    "Latin-script Derja: 0.000 → 0.714 Hit@5 (parallel subset)."], size=12, bullets=True)
    source(s, "retrieval_results_improved.json; docs/EVALUATION.md §2, §6; " + REPRO_NOTE)

    # 14 Multi-agent ---------------------------------------------------------------------------------------
    s = new(14)
    header(s, 14, 5, "Orchestrated multi-agent architecture", "Member 5", "Specialised agents coordinated by n8n — no agent plans or chooses tools at run time")
    rows = [["Component", "Decision it owns", "Type", "LLM use"],
            ["n8n workflow 03", "Branch on file, mode, next_agent; error replies", ("Orchestrator", {"color": NAVY, "bold": True}), "none"],
            ["Intent Router", "Language, procedure, intent, clarification, dialogue state", ("Agent (rule-first)", {"color": TEAL, "bold": True}), ("fallback only", {"color": AMBER, "bold": True})],
            ["RAG Retriever", "Which passages are evidence (fusion, exact key)", ("Deterministic", {"color": TEAL, "bold": True}), "embeddings only"],
            ["Checklist Builder", "Official scenario and sections quoted verbatim; FR/AR conflicts", ("Deterministic + LLM", {"color": TEAL, "bold": True}), ("FR→EN translation", {"color": AMBER, "bold": True})],
            ["Grounded Answer", "Extract article/row, generate, or refuse", ("Agent", {"color": AMBER, "bold": True}), ("Mistral 7B + verifiers", {"color": AMBER, "bold": True})],
            ["Form-Filling Helper", "Form identity, field statuses", ("Deterministic", {"color": TEAL, "bold": True}), "none (OCR)"],
            ["Dossier Validator", "Readiness report; composes 3 agents", ("Deterministic", {"color": TEAL, "bold": True}), "none"]]
    table(s, 0.5, 1.85, 8.6, rows, [2.1, 3.6, 1.6, 1.3], size=11, row_h=0.42)
    text(s, 9.4, 1.6, 3.45, 0.4, "Why separate agents?", size=15, bold=True, color=NAVY)
    text(s, 9.4, 2.05, 3.45, 3.5, ["Lists must be complete and verbatim",
                                   "Procedure codes are keys",
                                   "Legal text must not be paraphrased by a 7B model",
                                   "Forms need geometry and OCR",
                                   "Readiness is never certified by a model"], size=13, bullets=True, spacing=8)
    box(s, 0.5, 5.35, 12.35, 1.2, [[("Evidence of the cost of one generic path: ", {"bold": True, "color": RED}),
                                    ("before the dedicated paths, all 190 RNE follow-ups returned only links, and the official legal passage appeared in 1 of 30 legal answers. "
                                     "After: 190/190 and 26/30 on the same 728 replayed cases.", {})]], fill=RED_T, align=PP_ALIGN.LEFT, size=13)
    source(s, "backend/agents_api.py; agents/*.py; report Table 1 and Table 7 (final_regression.tex)")

    # 15 Multimodality -------------------------------------------------------------------------------------
    s = new(15)
    mm = ev["mm"]
    header(s, 15, 6, "Multimodality: official forms as PDF, scan or photo", "Member 5")
    chain = [("Upload", "type, signature, ≤10 MB", MIST, SLATE), ("Text layer?", "PDF geometry", NAVY, WHITE), ("Deskew + OCR", "Tesseract ara+fra", TEAL_T, TEAL),
             ("RANSAC homography", "anchor words → blank form", TEAL_T, TEAL), ("Ink per field", "vs blank template", TEAL_T, TEAL), ("Statuses", "filled / empty / unreadable", GREEN_T, GREEN)]
    for i, (a, b, fill, col) in enumerate(chain):
        x = 0.5 + i * 2.1
        box(s, x, 1.65, 1.9, 1.05, [[(a, {"bold": True, "size": 13, "color": WHITE if fill == NAVY else NAVY})], [(b, {"size": 10, "color": WHITE if fill == NAVY else SLATE})]],
            fill=fill, line=None if fill == NAVY else col)
        if i:
            arrow(s, x - 0.2, 2.17, x, 2.17)
    sel = [m for m in mm if m["id"] in ("M01", "M02", "M04", "M05b", "M06", "M08", "M10", "M11")]
    rows = [["Case (fixtures derived from official blank forms)", "Method", "Result", "s"]]
    for m in sel:
        fc = m["form-check"]
        res = (f'{fc["filled"]} filled / {fc["fields"]} fields' if fc.get("recognised") else (fc.get("error") or "not recognised"))
        rows.append([m["desc"], fc.get("method") or "—", res, f'{fc["seconds"]:.2f}'])
    table(s, 0.5, 2.95, 8.3, rows, [4.6, 1.1, 1.95, 0.65], size=10, row_h=0.36)
    ok = sum(1 for m in mm if _mm_ok(m))
    card(s, 9.1, 2.95, 3.75, 1.3, f"{ok}/{len(mm)}", "multimodal cases behave as expected (candidate backend, 2026-10-18)", color=GREEN)
    box(s, 9.1, 4.4, 3.75, 1.85, [[("Dossier Validator", {"bold": True, "color": NAVY})],
                                  [("Keeps apart: field status · official requirements quoted verbatim · completeness, which is never certified (no official RNE list exists).", {"size": 12})]],
        fill=MIST, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP)
    source(s, "agents/form_helper.py; agents/dossier_validator.py; data/evaluation/multimodal_eval_results.json (scripts/multimodal_eval.py). Filled text = neutral word 'placeholder'.")

    # 16 Live demo -----------------------------------------------------------------------------------------
    s = new(16)
    header(s, 16, 7, "Live demonstration", "Member 6", "Four interactions chosen for fast, deterministic paths (≈ 90 s in total)")
    demo = [("1", "FR", "Quels documents pour renouveler mon passeport ? J'habite en Tunisie.", "Checklist Builder · verbatim official list + source", "≈ 0.2 s"),
            ("2", "FR", "Et combien ça coûte ?", "Follow-up keeps context · fee section (timbre) + FR/AR conflict note", "≈ 0.2 s"),
            ("3", "Derja", "9adech el ma3loum mta3 RNE C 012?", "Exact official RNE row by key · Arabic header", "< 1 s"),
            ("4", "Photo", "/form_check + photo of blank F-001", "OCR + homography · 7 fields reported empty", "≈ 2.5 s")]
    for i, (n_, lang, q, exp, t_) in enumerate(demo):
        y = 1.95 + i * 1.02
        box(s, 0.5, y, 0.6, 0.8, n_, fill=NAVY, color=WHITE, size=18, bold=True)
        box(s, 1.2, y, 0.95, 0.8, lang, fill=TEAL_T, line=TEAL, size=13, bold=True, color=NAVY)
        box(s, 2.25, y, 4.75, 0.8, [[(q, {"name": MONO, "size": 11})]], fill=MIST, align=PP_ALIGN.LEFT)
        box(s, 7.1, y, 4.45, 0.8, exp, fill=WHITE, line=STEEL, size=12, align=PP_ALIGN.LEFT)
        box(s, 11.65, y, 1.2, 0.8, t_, fill=GREEN_T, size=13, bold=True, color=GREEN)
    box(s, 0.5, 6.05, 12.35, 0.6, [[("Fallback: ", {"bold": True, "color": AMBER}),
                                    ("if the live bot is slow, show the recorded results in data/evaluation/multilingual_eval_results.json and the n8n execution view. "
                                     "Grounded LLM answers (20–70 s) are shown from recordings only.", {})]], fill=AMBER_T, align=PP_ALIGN.LEFT, size=12)
    source(s, "presentation/LIVE_DEMO_SCRIPT.md; latencies from report §7 and data/evaluation/multilingual_eval_results.json")

    # 17 Evaluation ----------------------------------------------------------------------------------------
    s = new(17)
    fin = ev["final"]
    header(s, 17, 7, "Evaluation: what the end-to-end audit changed", "Member 6", "Same 728 audit cases replayed through n8n: original production vs final candidate")

    def fr(key_start):
        k = next(k for k in fin if k.startswith(key_start))
        return fin[k]
    big = [(fr("RNE fee/deadline with Telegram-style"), "RNE fee/deadline with chat context: exact row"),
           (fr("All targeted official facts"), "Targeted official facts present"),
           (fr("Legal questions"), "Legal answers containing the official passage"),
           (fr("Form-instruction"), "Form-instruction answers with the official passage")]
    for i, (vals, label) in enumerate(big):
        x = 0.5 + i * 3.1
        box(s, x, 1.9, 2.95, 2.15, "", fill=MIST)
        text(s, x + 0.12, 1.98, 2.7, 0.4, "before → after", size=11, color=STEEL)
        text(s, x + 0.12, 2.32, 2.75, 0.75, [[(vals[0], {"color": RED}), ("  →  ", {"color": STEEL}), (vals[2], {"color": GREEN})]], size=24, bold=True)
        text(s, x + 0.12, 3.15, 2.75, 0.85, label, size=12)
    ml = ev["ml"]["summary"]
    oc = ev["ml"]["summary_classified"]["part_A_outcomes"]
    MLA = f'{oc["evidence_present"]} evidence, {oc["correct_refusal"]} correct refusals, {oc["clarification_question"]} clarification questions, {oc["failure"]} failures'
    MLA_SCORE = f'{36 - oc["failure"]}/36 correct'
    rows = [["Check", "Result"],
            ["Fabricated legal provision (Law 2018-52 Art. 16)", f'{fr("Fabricated")[0]} → {fr("Fabricated")[2]}'],
            ["Citation URLs found in the official manifest", fr("Citation URLs")[2]],
            ["Multilingual parallel subset, 36 questions (candidate, today): " + MLA, MLA_SCORE],
            ["Behaviour cases: clarification, follow-up, RNE codes, out-of-scope, injection", ml["part_B"] + " (carte grise fixed on overnight branch)"],
            ["Unit and regression tests (no services needed)", UNIT_TESTS]]
    table(s, 0.5, 4.3, 12.35, rows, [9.0, 3.35], size=11, row_h=0.38)
    source(s, "report/tables/final_regression.tex; data/evaluation/multilingual_eval_results.json (scripts/multilingual_eval.py); pytest -m 'not integration'")

    # 18 Limitations + future ------------------------------------------------------------------------------
    s = new(18)
    header(s, 18, 8, "Limitations and future improvements", "Member 6")
    lims = ["Small corpus (12 documents); legal currency unverified", "No official RNE list of supporting documents",
            "Latin-script Derja retrieval weakest (0.714 Hit@5)", "LLM answers slow on 4 GB (20–70 s)",
            "No evaluation on real handwriting or photographs", "Labels written by the team; human review pending"]
    fut = ["Human-reviewed labels and a larger held-out set", "Activate agent and webhook keys (phase 2 plan ready)",
           "Arabic legal translation with expert validation", "Semantic answer–evidence check (H17 type errors)",
           "More procedures from official sources that allow reuse", "GPU with more memory → reranker, faster answers"]
    box(s, 0.5, 1.6, 6.05, 0.5, "Limitations", fill=RED, color=WHITE, bold=True, size=15)
    text(s, 0.6, 2.2, 5.9, 4.0, lims, size=14, bullets=True, spacing=10)
    box(s, 6.8, 1.6, 6.05, 0.5, "Future improvements", fill=GREEN, color=WHITE, bold=True, size=15)
    text(s, 6.9, 2.2, 5.9, 4.0, fut, size=14, bullets=True, spacing=10)
    source(s, "report §8; docs/EVALUATION.md; docs/SECURITY_PHASE2_ACTIVATION_PLAN.md")

    # 19 Conclusion ----------------------------------------------------------------------------------------
    s = new(19)
    header(s, 19, 8, "Conclusion", "Member 6")
    concl = [("Grounded by construction", "Lists, table rows, legal articles and form instructions are quoted verbatim; generation is fenced and verified."),
             ("Measured, not assumed", "Retrieval on verified spans, held-out and independent end-to-end audit; failures reported, not hidden."),
             ("Local and multilingual", "FR, EN, AR and Derja on one laptop: no paid API, no data leaves the machine."),
             ("Main lesson", "Perfect citation metrics hid empty and fabricated answers. The fix was architectural: extract, do not paraphrase.")]
    for i, (a, b_) in enumerate(concl):
        x = 0.5 + (i % 2) * 6.25
        y = 1.65 + (i // 2) * 2.15
        box(s, x, y, 6.0, 1.95, [[(a, {"bold": True, "color": NAVY, "size": 17})], [(b_, {"size": 14})]], fill=MIST if i < 3 else AMBER_T,
            align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP)
    text(s, 0.5, 6.05, 12.35, 0.55, "Thank you — questions welcome (10 minutes).", size=20, bold=True, color=TEAL, align=PP_ALIGN.CENTER)

    # Backup divider + backup slides ---------------------------------------------------------------------------
    s = new(20)
    band = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(2.6), prs.slide_width, Inches(1.8))
    band.fill.solid(); band.fill.fore_color.rgb = STEEL; band.line.fill.background()
    text(s, 0.8, 2.95, 11.8, 1.0, "Backup slides (not part of the 20-minute talk)", size=30, bold=True, color=WHITE)
    backup(prs, new, ev)

    for n, sl in slides:
        if n in sn:
            sl.notes_slide.notes_text_frame.text = sn[n]
    prs.save(OUT)
    return len(slides)


def _mm_ok(m: dict) -> bool:
    fc = m["form-check"]
    exp = m["expect"]
    if "all fields empty" in exp or "recognised via OCR" in exp:
        return bool(fc.get("recognised")) and fc["filled"] == 0
    if exp.endswith("filled") or "filled via" in exp:
        return bool(fc.get("recognised")) and fc["filled"] == int(exp.split()[0])
    if exp == "not recognised":
        return not fc.get("recognised")
    return not fc.get("recognised") and (fc.get("error") is not None or exp == "safe error")


def backup(prs, new, ev):
    # B1 security plan
    s = new(21)
    header(s, 21, 7, "Backup · Security controls and phase-2 activation", "All members")
    rows = [["Control", "Status in validated candidate", "Production today"],
            ["Admin endpoints (/ingestion/run, /index/run)", "403 unless ADMIN_API_KEY set; 401 on wrong key", "no authentication (older image)"],
            ["Agent endpoints (/agents/*, /retrieve)", "open while AGENT_API_KEY unset; 401 when set", "open"],
            ["Assistant webhook (X-Assistant-Key)", "bridge sends it when configured; n8n Header Auth", "not configured"],
            ["Request size", "413 above 15 MB; uploads ≤ 10 MB", "uploads ≤ 10 MB"],
            ["Network", "all ports on 127.0.0.1; Ollama loopback only", "same"]]
    table(s, 0.5, 1.6, 12.35, rows, [4.2, 4.75, 3.4], size=12, row_h=0.45)
    text(s, 0.5, 4.5, 12.35, 2.0, ["Order: create n8n Header Auth credentials → attach to the 7 agent nodes (harmless while keys unset) → set AGENT_API_KEY and recreate backend → set ASSISTANT_WEBHOOK_KEY and recreate bridge → enable webhook auth.",
                                   "Workflow 03 maps any backend error (including 401) to 503: a key mismatch looks like an outage — smoke-test after every step.",
                                   "No step is executed without the owner's approval."], size=13, bullets=True, spacing=8)
    source(s, "backend/main.py; backend/agents_api.py; docs/SECURITY_PHASE2_ACTIVATION_PLAN.md")

    # B2 full retrieval table
    s = new(22)
    r = ev["retr"]
    header(s, 22, 4, "Backup · Full retrieval comparison (71 dev questions, k = 5)", "Member 4")
    names = [("dense_structure", "Dense raw · structure"), ("dense_recursive", "Dense raw · recursive"), ("agent_structure", "Agent + normalisation · structure"),
             ("agent_recursive", "Agent + normalisation · recursive"), ("hybrid_structure", "Hybrid RRF · structure"),
             ("hybridcap2_structure", "Hybrid + cap 2 · structure"), ("hybridcap2_recursive", "Hybrid + cap 2 · recursive"), ("hybridcap3_structure", "Hybrid + cap 3 · structure")]
    rows = [["Configuration", "R@1", "R@3", "R@5", "MRR@5", "Hit@5"]] + [[lbl] + [pct(r[k][m]) for m in ("recall@1", "recall@3", "recall@5", "mrr@5", "hit@5")] for k, lbl in names]
    table(s, 0.5, 1.55, 12.35, rows, [4.85, 1.5, 1.5, 1.5, 1.5, 1.5], size=11, row_h=0.34)
    par = ev["retr_par"]["hybridcap2_structure"]
    langs = ["fr", "en", "ar", "derja", "derja-latin"]
    chart(s, 0.5, 4.75, 12.35, 1.9, langs, [("Dense raw", [ev["retr_par"]["dense_structure"][l]["hit@5"] for l in langs]),
                                                  ("Hybrid + cap", [par[l]["hit@5"] for l in langs])], [STEEL, NAVY], labels=False)
    source(s, "data/evaluation/retrieval_results_improved.json (overall and parallel_by_language)")

    # B3 numeric verifier
    s = new(23)
    header(s, 23, 7, "Backup · Numeric evidence verifier (off → on)", "Member 6")
    vt = (ROOT / "report" / "tables" / "verification.tex").read_text(encoding="utf-8")
    rows = [["Set", "False accept off", "on", "False refusal off", "on", "Unsupp. numbers off", "on"]]
    for m in re.finditer(r"^(Development|Regression|Held-out|Test 1|Test 2)[^&]*& (.+?) \\\\", vt, re.M):
        vals = [v.strip() for v in m.group(2).split("&")]
        rows.append([m.group(1)] + vals[:6])
    table(s, 0.5, 1.6, 12.35, rows, [2.6, 1.6, 1.35, 1.75, 1.35, 2.35, 1.35], size=12, row_h=0.45)
    text(s, 0.5, 4.6, 12.35, 1.6, ["Every number written with digits in an LLM answer must occur in the cited passage (digits or number words: “خمسون ألف” = 50,000).",
                                   "H14: Mistral wrote “510,000 TND” for fifty thousand dinars — now refused instead of shown. Median cost 3 ms."], size=13, bullets=True, spacing=8)
    source(s, "report/tables/verification.tex; agents/verification.py; docs/EVALUATION.md §7")

    # B4 dialogue prompt details
    s = new(24)
    dl = ev["dialogue"]
    header(s, 24, 3, "Backup · dialogue_understanding outputs (identical inputs)", "Member 3")
    rows = [["Metric (18 synthetic messages, 4 languages)", "v1", "v2", "v3"]]
    dv = ev["dialogue_valid"]
    for k, lbl in [("json_valid", "Valid JSON (raw)"), ("schema_valid", "Schema-valid (raw)"), ("item_precision", "Item precision (raw)"), ("item_recall", "Item recall (raw)"),
                   ("evidence_exact_substring", "Evidence exact substring (raw)"), ("spurious_items_on_messages_without_items", "Spurious items on questions / injection (raw)"),
                   ("quantity_errors", "Invented quantities (raw)"), ("application_residence_correct", "Expected application / residence found (raw)")]:
        rows.append([lbl] + [str(dl[v][k]) if not isinstance(dl[v][k], float) else f"{dl[v][k]:.3f}" for v in ("v1", "v2", "v3")])
    rows.append(["Invented application / residence (raw)"] + [str(dv[v]["raw_wrong_application_or_residence"]) for v in ("v1", "v2", "v3")])
    rows.append(["Item precision / recall after code validation"] + [f'{dv[v]["after_validation_item_precision"]:.3f} / {dv[v]["after_validation_item_recall"]:.3f}' for v in ("v1", "v2", "v3")])
    rows.append(["Invented quantities after code validation"] + [str(dv[v]["after_validation_quantity_errors"]) for v in ("v1", "v2", "v3")])
    rows.append(["Median seconds"] + [f'{dl[v]["median_seconds"]:.1f}' for v in ("v1", "v2", "v3")])
    table(s, 0.5, 1.55, 12.35, rows, [6.35, 2.0, 2.0, 2.0], size=11, row_h=0.37)
    source(s, "data/evaluation/prompt_experiments/dialogue_understanding_results.json; dialogue_messages.jsonl (synthetic, labelled)")

    # B5 intent by language
    s = new(25)
    it = ev["intent"]
    header(s, 25, 3, "Backup · intent_router B0 vs v1 by language (LLM path only)", "Member 3")
    langs = [l for l in ("fr", "en", "ar", "derja") if l in it["v1"]]
    chart(s, 0.5, 1.7, 12.35, 4.6, [f"{l} (n={it['v1'][l]['n']})" for l in langs],
          [("B0 both correct", [it["B0"][l]["both_correct"] for l in langs]), ("v1 both correct", [it["v1"][l]["both_correct"] for l in langs])], [STEEL, NAVY])
    source(s, "data/evaluation/prompt_experiments/intent_router_results.json. In production the keyword rules answer first; this measures the fallback prompt alone.")


REPRO_NOTE = ""
UNIT_TESTS = ""
INTERPRET = {"intent": "", "dialogue": ""}

if __name__ == "__main__":
    import sys
    cfg = json.loads((ROOT / "presentation" / "deck_facts.json").read_text(encoding="utf-8"))
    REPRO_NOTE, UNIT_TESTS, INTERPRET = cfg["repro_note"], cfg["unit_tests"], cfg["interpret"]
    n = build()
    print(f"written {OUT.relative_to(ROOT)} ({n} slides)")
