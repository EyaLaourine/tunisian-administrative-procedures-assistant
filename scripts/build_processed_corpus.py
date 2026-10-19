"""Build data/processed/ (extracted TextBlocks and chunk files) from the tracked originals in data/raw/.

Offline and safe: it only reads data/raw/ and writes data/processed/. It does NOT call Ollama, does NOT write
to Qdrant and does NOT download anything. A fresh clone needs this step before the unit tests and before the
backend can quote official checklists; vectors are created separately (see docs/INSTALLATION.md).

Run from the repository root:  python scripts/build_processed_corpus.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.settings import get_settings  # noqa: E402
from rag.indexing import build_chunks  # noqa: E402


def main() -> None:
    settings = get_settings()
    _, report = build_chunks(settings)
    print(f"processed corpus written to {settings.processed_dir}")
    print(f"documents extracted: {len(report.documents_indexed)}")
    for doc_id, reason in sorted(report.documents_skipped.items()):
        print(f"skipped: {doc_id} ({reason})")
    for strategy, count in sorted(report.chunks_per_strategy.items()):
        print(f"chunks ({strategy}): {count}")


if __name__ == "__main__":
    main()
