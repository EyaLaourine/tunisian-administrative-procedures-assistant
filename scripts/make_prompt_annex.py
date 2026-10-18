"""Generate report/appendices/prompt_library.tex from the actual prompt files (prompts/<name>/<version>.yaml).

Every prompt version is reproduced verbatim (fvextra Verbatim with line breaking). Runtime usage,
model and status come from prompts/registry.yaml and the call sites listed in USAGE below; they are
documented here once so the annex cannot drift from the code silently (the script fails if a prompt
has no usage entry).

Run from the repository root:  .venv/Scripts/python scripts/make_prompt_annex.py
"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "prompts"
OUT = ROOT / "report" / "appendices" / "prompt_library.tex"
MODELS = {"llm": r"\code{mistral:latest} (Mistral 7B Instruct, Q4\_K\_M)",
          "translation": r"\code{translategemma:4b} (Q4\_K\_M)"}
# name -> (runtime component, when it is called, status note)
USAGE = {
    "intent_router": (r"\code{agents/intent\_router.py} (\code{IntentRouter.\_llm\_classify})",
                      "Only when no deterministic procedure keyword matches; output validated against fixed enumerations.",
                      "Single version; registry-selected."),
    "language_identification": (r"\code{agents/language.py} (\code{\_model\_language})",
                                "Only for Latin-script messages of at least four words in which the deterministic markers "
                                "find no French, English or Arabizi Derja word; any value outside the three accepted codes "
                                "is ignored and the conversation language is kept.",
                                "Single version (added on 18 October 2026); registry-selected."),
    "dialogue_understanding": (r"\code{agents/dialogue.py} (\code{understand})",
                               "Telegram dialogue path only, when the rules extract no fact but the message contains a "
                               "possession/residence cue; every item must quote an exact substring of the message.",
                               "v1 and v2 historical; v3 (JSON schema) registry-selected."),
    "grounded_answer": (r"\code{agents/answer.py} (\code{GroundedAnswerer})",
                        "Free questions that are not RNE table rows, not guide checklists, not legal-article or form "
                        "questions and not RNE registration questions (those are answered deterministically). "
                        "Citations and numbers are verified after generation.",
                        "v1 historical; v2 registry-selected; v3 evaluated and not adopted."),
    "translate_items": (r"\code{agents/checklist\_builder.py} (\code{\_translate})",
                        "French official checklist items to English only; rejected unless every line and number is "
                        "preserved. French-to-Arabic use was withdrawn after meaning-changing errors.",
                        "Single version; registry-selected."),
    "evidence_topic": (r"\code{agents/verification.py} (\code{EvidenceVerifier.check\_topic})",
                       r"Disabled at run time (\code{EVIDENCE\_TOPIC\_CHECK=false} by default); kept for experiments.",
                       "Listed in the registry but disabled (experimental): unstable verdicts across runs."),
}
# name -> (expected output, main grounding and safety constraints, tests and evaluation evidence)
CONTRACT = {
    "intent_router": (r"one JSON object with \code{procedure\_category} and \code{intent} from fixed enumerations.",
                      r"classification only (``Do not answer the question''); values outside the enumerations are "
                      r"rejected and a default route is used; the message is delimited as data.",
                      r"\code{tests/test\_agents\_routing.py} (fallback and enumeration validation with a fake model); "
                      r"Annex~\ref{app:prompt_experiments} (84 development questions)."),
    "language_identification": (r"one JSON object with a \code{language} field (\code{en}, \code{fr} or \code{derja}).",
                                r"no answer and no explanation; only three codes are accepted; failures are logged "
                                r"without message content.",
                                r"\code{tests/test\_auto\_language.py}; language suite (Section~\ref{sec:eval})."),
    "dialogue_understanding": (r"JSON list of declared items; v3 constrains it with a JSON schema.",
                               r"each item must quote an exact substring of the user's message; items failing code "
                               r"validation are dropped; no administrative fact is produced.",
                               r"\code{tests/test\_dialogue.py}; Annex~\ref{app:prompt_experiments} (18 synthetic "
                               r"declarations)."),
    "grounded_answer": (r"plain text with numbered citations \code{[n]} pointing to the supplied passages.",
                        r"answer only from the numbered passages; answers citing no or non-existent passages are "
                        r"replaced by quoted passages; numbers absent from the cited passages are removed or the answer "
                        r"is refused.",
                        r"\code{tests/test\_form\_helper\_and\_answer.py}, \code{tests/test\_answerability.py}, "
                        r"\code{tests/test\_verification.py}; Annex~\ref{app:prompt_experiments}."),
    "translate_items": (r"plain text, one translated line per numbered input line.",
                        r"rejected unless the numbering and every number of the source are preserved; the official "
                        r"French text is shown instead.",
                        r"\code{tests/test\_checklist\_builder.py}; Annex~\ref{app:prompt_experiments} (11 official "
                        r"checklists)."),
    "evidence_topic": (r"one JSON object with a same-procedure verdict.",
                       r"any invalid output is treated as ``not the same''; disabled in the deployed configuration.",
                       r"\code{tests/test\_verification.py}; development runs in \code{docs/EVALUATION.md} (Section 7)."),
}
DETERMINISTIC = [
    ("Language rules", r"\code{agents/language.py}", "marker words and Arabizi digit-letters; the model fallback is used only when no marker is found"),
    ("Conversational intents", r"\code{agents/conversation.py}", "greetings, thanks, yes/no against the pending clarification; no administrative facts"),
    ("RAG Retriever", r"\code{agents/retriever.py}, \code{rag/hybrid.py}", "dense BGE-M3 retrieval, BM25, reciprocal rank fusion, exact RNE code lookup"),
    ("RNE registration", r"\code{agents/rne\_registration.py}", "legal form $\\rightarrow$ official creation rows of the RNE table; asks for the legal form when unknown"),
    ("Checklist Builder (core)", r"\code{agents/checklist\_builder.py}", "verbatim official sections; only the optional FR$\\rightarrow$EN translation uses a prompt"),
    ("Legal evidence extractor", r"\code{agents/legal\_evidence.py}", "article/table location, verbatim quotation, form overview, verified download links"),
    ("Answerability gate", r"\code{agents/answerability.py}", "IDF-weighted lexical support of the question in the evidence"),
    ("Numeric claim verifier", r"\code{agents/verification.py}", "every digit-written number must occur in the cited passages"),
    ("Form-Filling Helper", r"\code{agents/form\_helper.py}, \code{agents/form\_roles.py}", "template matching, Tesseract OCR, homography, ink detection, field roles"),
    ("Dossier Validator", r"\code{agents/dossier\_validator.py}", "field statuses and verbatim official requirements; never certifies completeness"),
]


def tex_escape(text: str) -> str:
    repl = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
            "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}
    return "".join(repl.get(c, c) for c in text)


def variables(spec: dict) -> list[str]:
    found = re.findall(r"\{(\w+)\}", (spec.get("system") or "") + (spec.get("user_template") or ""))
    keys = [k for k in dict.fromkeys(found) if k in (spec.get("user_template") or "") or k in {"passages", "question", "language_name", "message"}]
    return keys


def main() -> None:
    registry = yaml.safe_load((PROMPTS / "registry.yaml").read_text(encoding="utf-8"))["active"]
    names = sorted(d.name for d in PROMPTS.iterdir() if d.is_dir())
    missing = [n for n in names if n not in USAGE or n not in CONTRACT or n not in registry]
    if missing:
        raise SystemExit(f"no usage entry for prompts: {missing}")
    out = [
        "% Generated by scripts/make_prompt_annex.py from prompts/*/*.yaml -- do not edit by hand.",
        r"\section{Prompt library}\label{app:prompts}",
        r"\sloppy",
        r"This annex reproduces every prompt template of the implementation \emph{verbatim}, as stored in "
        r"\code{prompts/<name>/<version>.yaml}. A registry (\code{prompts/registry.yaml}) selects the active version; "
        r"versions are immutable once evaluated, and every LLM response records the reference "
        r"\code{name@version} it used. Placeholders \code{\{name\}} are substituted at run time; other braces "
        r"(JSON examples) are left untouched. All prompts run on local Ollama models with temperature~0.",
        "",
        r"\subsection*{Active versions and runtime use}",
        r"\begin{center}\footnotesize",
        r"\begin{tabularx}{\textwidth}{@{}l c l X@{}}",
        r"\toprule Prompt & Active & Model & Runtime component and trigger \\ \midrule",
    ]
    for n in names:
        spec = yaml.safe_load((PROMPTS / n / f"{registry[n]}.yaml").read_text(encoding="utf-8"))
        comp, when, _ = USAGE[n]
        out.append(rf"\code{{{tex_escape(n)}}} & {registry[n]} & {MODELS[spec.get('model_role', 'llm')].split(' (')[0]} & {comp}: {when} \\")
    out += [r"\bottomrule", r"\end{tabularx}", r"\end{center}", ""]
    out += [r"\subsection*{Components without a prompt}",
            r"The following components are deterministic and use \emph{no} prompt; no prompt is invented for them.",
            r"\begin{center}\footnotesize", r"\begin{tabularx}{\textwidth}{@{}l l X@{}}",
            r"\toprule Component & Source & Method \\ \midrule"]
    out += [rf"{a} & {b} & {c} \\" for a, b, c in DETERMINISTIC]
    out += [r"\bottomrule", r"\end{tabularx}", r"\end{center}", ""]
    for n in names:
        comp, when, status = USAGE[n]
        versions = sorted(p.stem for p in (PROMPTS / n).glob("*.yaml"))
        out.append(rf"\subsection{{\code{{{tex_escape(n)}}}}}")
        out.append(rf"\textbf{{Runtime:}} {comp}. {when} \textbf{{Status:}} {status} "
                   rf"\textbf{{Versions:}} {', '.join(v + (' (active)' if v == registry[n] else '') for v in versions)}.")
        for v in versions:
            path = PROMPTS / n / f"{v}.yaml"
            spec = yaml.safe_load(path.read_text(encoding="utf-8"))
            opts = ", ".join(f"{k}={val}" for k, val in (spec.get("options") or {}).items())
            tag = (' --- registry version, disabled at run time' if n == 'evidence_topic' else ' --- active') if v == registry[n] else ''
            out.append(rf"\subsubsection*{{\code{{{tex_escape(n)}@{v}}}{tag}}}")
            out.append(r"\begin{itemize}")
            out.append(rf"\item \textbf{{Purpose:}} {tex_escape(' '.join((spec.get('description') or '').split()))}")
            if v == registry[n]:
                state = "registry-selected" + (", disabled at run time" if n == "evidence_topic" else "")
            elif (n, v) == ("grounded_answer", "v3"):
                state = "evaluated, not adopted"
            else:
                state = "historical"
            out.append(rf"\item \textbf{{File:}} \code{{prompts/{tex_escape(n)}/{v}.yaml}}; \textbf{{status:}} {state}.")
            out.append(rf"\item \textbf{{Model:}} {MODELS[spec.get('model_role', 'llm')]}; options: \code{{{tex_escape(opts)}}}; "
                       rf"structured JSON output: {'yes' + (' (JSON schema)' if spec.get('response_schema') else '') if spec.get('json_output') else 'no'}.")
            names_tex = ", ".join("\\code{" + tex_escape(k) + "}" for k in variables(spec)) or "none"
            out.append(r"\item \textbf{Input variables:} " + names_tex + ".")
            if v == registry[n]:
                fmt, rules, tests = CONTRACT[n]
                out.append(r"\item \textbf{Expected output:} " + fmt)
                out.append(r"\item \textbf{Grounding and safety constraints:} " + rules)
                out.append(r"\item \textbf{Tests and evaluation evidence:} " + tests)
            out.append(r"\end{itemize}")
            out.append(r"\begin{Verbatim}[fontsize=\scriptsize,breaklines=true,breakanywhere=true,frame=single,framesep=2pt]")
            out.append(path.read_text(encoding="utf-8").rstrip())
            out.append(r"\end{Verbatim}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(names)} prompts)")


if __name__ == "__main__":
    main()
