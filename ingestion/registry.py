"""Load and validate the official source registry."""

from pathlib import Path

import yaml

from ingestion.models import SourceRegistry


def load_registry(path: Path) -> SourceRegistry:
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return SourceRegistry.model_validate(raw)
