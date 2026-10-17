"""Read-only access to the processed official corpus (manifest + extracted TextBlocks)."""

import json
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ingestion.manifest import Manifest
from ingestion.models import ManifestRecord
from rag.retrieval import Citation

# Section headings used by the official procedure guides (FR and AR versions).
# Anchored at the start: scenario titles may contain these words (e.g. "من أجل السرقة").
SECTION_PATTERNS: dict[str, re.Pattern] = {
    "documents": re.compile(r"^\s*(?:pi[eè]ces?\s+[aà]\s+fournir|الوثائق\s+المطلوبة)", re.I),
    "conditions": re.compile(r"^\s*(?:conditions?\b|شروط)", re.I),
    "place": re.compile(r"^\s*(?:lieu\s+de\s+d[ée]p[oô]t|مكان\s+إيداع)", re.I),
    "delay": re.compile(r"^\s*(?:d[ée]lais?\b|أجل)", re.I),
}
MAX_SECTION_HEADING_CHARS = 60


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("’", "'").replace("\u00a0", " ")
    text = re.sub(r"[\u064b-\u0652\u0640]", "", text)
    return re.sub(r"\s+", " ", text).strip().rstrip(".:،").strip().lower()


def section_kind(heading: str) -> str | None:
    if len(heading) > MAX_SECTION_HEADING_CHARS:
        return None
    for kind, pattern in SECTION_PATTERNS.items():
        if pattern.search(heading):
            return kind
    return None


@dataclass
class Section:
    kind: str
    heading: str
    items: list[str]


@dataclass
class Scenario:
    index: int  # position among the document's scenarios (used to align FR/AR versions)
    title: str
    path: list[str]  # ancestor headings, outermost first, ending with `title`
    page: int | None
    sections: list[Section] = field(default_factory=list)


def parse_scenarios(blocks: list[dict]) -> list[Scenario]:
    """A scenario is the heading directly above a run of section headings (conditions, documents...)."""
    scenarios: list[Scenario] = []
    stack: list[tuple[int, str, int | None]] = []  # (level, text, page) of open headings
    by_key: dict[tuple, Scenario] = {}
    current: Section | None = None
    for b in blocks:
        if b["kind"] == "heading":
            kind = section_kind(b["text"])
            if kind is None:
                stack = [h for h in stack if h[0] < b["level"]] + [(b["level"], b["text"], b.get("page"))]
                current = None
                continue
            parents = [h for h in stack if h[0] < b["level"]]
            if not parents:
                current = None
                continue
            key = tuple(h[1] for h in parents)
            scenario = by_key.get(key)
            if scenario is None:
                scenario = Scenario(len(scenarios), parents[-1][1], list(key), parents[-1][2])
                scenarios.append(scenario)
                by_key[key] = scenario
            current = Section(kind, b["text"], [])
            scenario.sections.append(current)
        elif current is not None and b["kind"] in {"list_item", "paragraph"}:
            current.items.append(b["text"])
    return scenarios


class Corpus:
    def __init__(self, raw_dir: Path, processed_dir: Path):
        self.raw_dir = raw_dir
        self.processed_dir = processed_dir

    def records(self) -> dict[str, ManifestRecord]:
        path = self.raw_dir / "manifest.json"
        return _manifest_records(str(path), path.stat().st_mtime if path.exists() else 0)

    def blocks(self, doc_id: str) -> list[dict]:
        path = self.processed_dir / "extracted" / f"{doc_id}.json"
        if not path.exists():
            return []
        return _load_json(str(path), path.stat().st_mtime)

    def scenarios(self, doc_id: str) -> list[Scenario]:
        return parse_scenarios(self.blocks(doc_id))

    def citation(self, doc_id: str, heading_path: list[str] | None = None, page: int | None = None) -> Citation | None:
        rec = self.records().get(doc_id)
        if rec is None:
            return None
        return Citation(
            doc_id=rec.doc_id, title=rec.title, source_organization=rec.source_organization, url=rec.url,
            official_reference=rec.official_reference,
            publication_date=rec.publication_date.isoformat() if rec.publication_date else None,
            applicability=rec.applicability.value, page_start=page, page_end=page,
            heading_path=heading_path or [], sha256=rec.sha256 or "", language=rec.language.value,
            document_type=rec.document_type.value, procedure_category=rec.procedure_category.value,
        )


@lru_cache(maxsize=4)
def _manifest_records(path: str, _mtime: float) -> dict[str, ManifestRecord]:
    return Manifest(Path(path)).records


@lru_cache(maxsize=64)
def _load_json(path: str, _mtime: float) -> list[dict]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
