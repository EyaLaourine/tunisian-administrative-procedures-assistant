"""Two chunking strategies over the same extracted blocks, for later retrieval evaluation.

1. `recursive`: structure-agnostic recursive character splitting of the concatenated text.
2. `structure`: sections delimited by detected headings; each chunk is prefixed with its heading
   path (e.g. "Passeport > Modification > Pièces à fournir"); table rows are atomic chunks.
"""

import hashlib
from dataclasses import asdict, dataclass, field

from rag.extraction import TextBlock

RECURSIVE_SEPARATORS = ["\n\n", "\n", ". ", "، ", " ", ""]


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    strategy: str
    index: int
    text: str
    heading_path: list[str] = field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _chunk_id(doc_id: str, strategy: str, index: int, text: str) -> str:
    digest = hashlib.sha256(f"{doc_id}|{strategy}|{index}|{text}".encode("utf-8")).hexdigest()[:16]
    return f"{doc_id}:{strategy}:{index}:{digest}"


def recursive_split(text: str, chunk_size: int, overlap: int, separators: list[str] | None = None) -> list[str]:
    """Recursively split on the coarsest separator that yields pieces <= chunk_size, then merge
    adjacent pieces up to chunk_size with `overlap` characters carried between chunks."""
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("require chunk_size > overlap >= 0")
    separators = RECURSIVE_SEPARATORS if separators is None else separators
    text = text.strip()
    if len(text) <= chunk_size:
        return [text] if text else []

    sep = next((s for s in separators if s == "" or s in text), "")
    rest = separators[separators.index(sep) + 1 :] if sep else []
    pieces = list(text) if sep == "" else [p for p in text.split(sep) if p.strip()]

    # Recurse into pieces that are still too large.
    atoms: list[str] = []
    for piece in pieces:
        if len(piece) > chunk_size and sep != "":
            atoms.extend(recursive_split(piece, chunk_size, overlap, rest))
        else:
            atoms.append(piece)

    chunks: list[str] = []
    current = ""
    for atom in atoms:
        candidate = f"{current}{sep}{atom}" if current else atom
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            chunks.append(current.strip())
            tail = current[-overlap:] if overlap else ""
            # Start the overlap on a word boundary where possible.
            if " " in tail:
                tail = tail[tail.index(" ") + 1 :]
            current = f"{tail}{sep}{atom}" if tail and len(tail) + len(sep) + len(atom) <= chunk_size else atom
        else:
            current = atom
    if current.strip():
        chunks.append(current.strip())
    return chunks


def _pages_for_span(offsets: list[tuple[int, int | None]], start: int, end: int) -> tuple[int | None, int | None]:
    pages = [p for off, p in offsets if p is not None and start <= off < end]
    before = [p for off, p in offsets if p is not None and off <= start]
    first = before[-1] if before else (pages[0] if pages else None)
    last = pages[-1] if pages else first
    return first, last


def recursive_chunks(
    doc_id: str, blocks: list[TextBlock], chunk_size: int = 1000, overlap: int = 150, doc_title: str | None = None
) -> list[Chunk]:
    """`doc_title` is accepted for interface symmetry; the baseline strategy ignores structure."""
    parts: list[str] = []
    offsets: list[tuple[int, int | None]] = []
    pos = 0
    for b in blocks:
        offsets.append((pos, b.page))
        parts.append(b.text)
        pos += len(b.text) + 2
    full = "\n\n".join(parts)

    chunks: list[Chunk] = []
    cursor = 0
    for i, piece in enumerate(recursive_split(full, chunk_size, overlap)):
        found = full.find(piece[:80], max(0, cursor - overlap - 1))
        start = found if found >= 0 else cursor
        cursor = start + len(piece)
        p_start, p_end = _pages_for_span(offsets, start, cursor)
        chunks.append(Chunk(_chunk_id(doc_id, "recursive", i, piece), doc_id, "recursive", i, piece, [], p_start, p_end))
    return chunks


@dataclass
class _Section:
    heading_path: list[str]
    lines: list[str] = field(default_factory=list)
    pages: list[int] = field(default_factory=list)
    atomic: bool = False  # table rows are never merged or split

    @property
    def size(self) -> int:
        return sum(len(line) + 1 for line in self.lines)


def _sections(blocks: list[TextBlock]) -> list[_Section]:
    stack: list[tuple[int, str]] = []
    sections: list[_Section] = []
    current = _Section([])
    for b in blocks:
        if b.kind == "heading":
            if current.lines:
                sections.append(current)
            while stack and stack[-1][0] >= b.level:
                stack.pop()
            stack.append((b.level, b.text))
            current = _Section([h for _, h in stack])
            if b.page:
                current.pages.append(b.page)
        elif b.kind == "table_row":
            if current.lines:
                sections.append(current)
            sections.append(_Section([h for _, h in stack], [b.text], [b.page] if b.page else [], atomic=True))
            current = _Section([h for _, h in stack])
        else:
            current.lines.append(f"- {b.text}" if b.kind == "list_item" else b.text)
            if b.page:
                current.pages.append(b.page)
    if current.lines:
        sections.append(current)
    return sections


def structure_chunks(
    doc_id: str, blocks: list[TextBlock], max_chars: int = 1200, min_chars: int = 200, doc_title: str | None = None
) -> list[Chunk]:
    sections = _sections(blocks)
    if doc_title:
        for sec in sections:
            if not sec.heading_path or sec.heading_path[0] != doc_title:
                sec.heading_path.insert(0, doc_title)

    # Merge small consecutive sections that share the same parent heading.
    merged: list[_Section] = []
    for sec in sections:
        prev = merged[-1] if merged else None
        if (
            prev is not None
            and not sec.atomic
            and not prev.atomic
            and prev.heading_path[:-1] == sec.heading_path[:-1]
            and prev.size < min_chars
            and prev.size + sec.size <= max_chars
        ):
            label = sec.heading_path[-1] if sec.heading_path and sec.heading_path != prev.heading_path else None
            prev.lines.extend(([label] if label else []) + sec.lines)
            prev.pages.extend(sec.pages)
        else:
            merged.append(_Section(list(sec.heading_path), list(sec.lines), list(sec.pages), sec.atomic))

    chunks: list[Chunk] = []
    for sec in merged:
        header = " > ".join(sec.heading_path)
        body = "\n".join(sec.lines)
        budget = max(200, max_chars - len(header) - 2)
        pieces = [body] if sec.atomic or len(body) <= budget else recursive_split(body, budget, min(150, budget // 5))
        for piece in pieces:
            text = f"{header}\n{piece}" if header else piece
            i = len(chunks)
            chunks.append(
                Chunk(
                    _chunk_id(doc_id, "structure", i, text),
                    doc_id,
                    "structure",
                    i,
                    text,
                    sec.heading_path,
                    min(sec.pages) if sec.pages else None,
                    max(sec.pages) if sec.pages else None,
                )
            )
    return chunks


STRATEGIES = {"recursive": recursive_chunks, "structure": structure_chunks}
