"""CLI: python -m ingestion [--only DOC_ID ...]"""

import argparse
import json

from backend.logging_setup import configure_logging
from backend.settings import get_settings
from ingestion.pipeline import run_ingestion


def main() -> None:
    parser = argparse.ArgumentParser(description="Download official documents listed in config/sources.yaml")
    parser.add_argument("--only", nargs="*", help="restrict to these doc_ids")
    args = parser.parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)
    summary = run_ingestion(settings, only=args.only)
    print(json.dumps({"counts": summary.counts()}, indent=2))


if __name__ == "__main__":
    main()
