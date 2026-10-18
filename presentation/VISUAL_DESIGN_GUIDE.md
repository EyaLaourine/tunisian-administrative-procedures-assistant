# Visual design guide

The goal is a calm, technical, academic look, in which colour carries meaning. The generator
`presentation/build_presentation.py` applies every rule below. If you edit the deck by hand, keep to them.

## Format
- 16:9 (13.333 × 7.5 in). White background. Safe margin of 0.5 in on every side.
- Top-left section chip with the professor's outline number and name (for example "3 · Prompt Engineering").
  The presenter tag ("Member 3") sits on the right of the same line.
- Footer at 10 pt, slate: project name · course · slide number.

## Colour palette (meaning first)

| Token | Hex | Use |
|---|---|---|
| Navy | `#12305B` | Titles, orchestration (n8n), primary emphasis |
| Teal | `#0F8B8D` | Deterministic components (rules, retriever, form helper, verifiers) |
| Amber | `#E8A33D` | LLM-powered steps (Mistral 7B, TranslateGemma) |
| Slate | `#4A5560` | Body text |
| Mist | `#EEF2F6` | Card and box backgrounds |
| Steel | `#8C99A6` | Stores and model servers, secondary lines |
| Red | `#B83A3A` | Errors, failures, "before" column |
| Green | `#2E7D4F` | Verified results, "after" column |

Never use colour alone to carry a meaning: pair it with a label ("LLM", "rule", "before", "after").

## Typography
- Font: Segoe UI (installed on Windows), with Calibri as fallback. Monospace: Consolas, for prompt excerpts only.
- Title: 28 pt bold navy. Subtitle and kicker: 16 pt slate.
- Body: 16–18 pt. Never below 12 pt, except footers (10 pt) and source notes (11 pt).
- Big-number cards: number at 36 pt bold, label at 12 pt.

## Text density
- At most 6 bullet lines per slide, and at most about 10 words per line.
- The speaker notes carry the explanation; the slide carries the evidence.
- Every number shown has a source note (file or table) on the same slide.

## Layout repertoire (rotate to avoid monotony)
1. **Title**: navy band, white title, team line.
2. **Statement + cards**: one sentence, then 3–4 cards.
3. **Full-width diagram**: native shapes and connectors, editable.
4. **Split before/after**: red-tinted left, green-tinted right, monospace excerpts, result bar below.
5. **Table + takeaway**: a compact native table plus one highlighted takeaway box.
6. **Chart + interpretation**: a native column chart (editable data) plus 2–3 interpretation bullets.
7. **Timeline / sequence**: numbered steps along a line.

## Diagrams
- Rounded rectangles. Fill by component type (teal deterministic, amber LLM, navy orchestration, steel store).
- Arrows: 1.5 pt slate, with an arrowhead. Error paths are dashed red.
- Labels inside boxes: 12–14 pt. Endpoint paths are in Consolas, 10–11 pt.

## Charts
- Native PowerPoint charts, with editable data.
- At most three series. Navy for the system, steel for the baseline, amber for the intermediate.
- Y axis from 0 to 1 for rates. Data labels on bars.

## Screenshots
- **None are included in the generated deck: no fake screenshots.** Slides that should show a real screen
  carry a slate dashed frame marked "Insert real screenshot: <what>", with the capture instructions in
  `LIVE_DEMO_SCRIPT.md`.
- When inserting: a 1 pt steel border, no drop shadow, and a crop that removes personal Telegram names.
