import pytest

from rag.chunking import recursive_chunks, recursive_split, structure_chunks
from rag.extraction import TextBlock


def _words(n: int) -> str:
    return " ".join(f"word{i}" for i in range(n))


def test_recursive_split_respects_size_and_covers_text():
    text = "\n\n".join(_words(60) for _ in range(10))
    chunks = recursive_split(text, chunk_size=300, overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 300 for c in chunks)
    for token in set(text.split()):
        assert any(token in c for c in chunks)


def test_recursive_split_overlap_carries_context():
    text = ". ".join(f"Sentence number {i} with filler words" for i in range(40))
    chunks = recursive_split(text, chunk_size=200, overlap=60)
    shared = sum(1 for a, b in zip(chunks, chunks[1:]) if set(a.split()[-3:]) & set(b.split()[:12]))
    assert shared >= len(chunks) // 2


def test_recursive_split_short_and_invalid():
    assert recursive_split("short", 100, 10) == ["short"]
    assert recursive_split("   ", 100, 10) == []
    with pytest.raises(ValueError):
        recursive_split("x", 100, 100)


def test_recursive_chunks_track_pages():
    blocks = [TextBlock(_words(80), "paragraph", 0, 1), TextBlock(_words(80), "paragraph", 0, 2)]
    chunks = recursive_chunks("d", blocks, chunk_size=300, overlap=30)
    assert chunks[0].page_start == 1
    assert chunks[-1].page_end == 2
    assert len({c.chunk_id for c in chunks}) == len(chunks)


def test_structure_chunks_carry_heading_path_and_title():
    blocks = [
        TextBlock("Part A", "heading", 3),
        TextBlock("Sub A1", "heading", 4),
        TextBlock("Label", "heading", 6),
        TextBlock("item one", "list_item"),
        TextBlock("item two", "list_item"),
        TextBlock("Part B", "heading", 3),
        TextBlock("body of part b " * 5, "paragraph"),
    ]
    chunks = structure_chunks("d", blocks, doc_title="Doc")
    assert chunks[0].heading_path == ["Doc", "Part A", "Sub A1", "Label"]
    assert chunks[0].text.startswith("Doc > Part A > Sub A1 > Label\n- item one")
    assert chunks[-1].heading_path == ["Doc", "Part B"]  # heading stack popped correctly


def test_structure_chunks_table_rows_are_atomic():
    blocks = [TextBlock("Table", "heading", 1)] + [TextBlock(f"Code: R{i}\nValue: v{i}", "table_row") for i in range(5)]
    chunks = structure_chunks("d", blocks)
    assert len(chunks) == 5
    assert all(c.text.count("Code:") == 1 for c in chunks)


def test_structure_chunks_split_long_sections():
    blocks = [TextBlock("H", "heading", 1), TextBlock(_words(600), "paragraph")]
    chunks = structure_chunks("d", blocks, max_chars=800)
    assert len(chunks) > 1
    assert all(c.text.startswith("H\n") and len(c.text) <= 800 for c in chunks)
