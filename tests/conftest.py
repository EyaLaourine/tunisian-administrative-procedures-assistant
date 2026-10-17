"""Shared fixtures.

Fixture documents contain neutral placeholder text only; they are never part of the knowledge
base and do not describe any real or invented administrative procedure.
"""

from pathlib import Path

import fitz
import pytest

from backend.settings import REPO_ROOT, Settings


@pytest.fixture
def make_pdf(tmp_path: Path):
    def _make(pages: list[list[tuple[str, float]]], name: str = "fixture.pdf") -> Path:
        """pages: list of [(text, fontsize), ...] lines per page."""
        doc = fitz.open()
        for lines in pages:
            page = doc.new_page()
            y = 72
            for text, size in lines:
                page.insert_text((72, y), text, fontsize=size)
                y += size * 2
        path = tmp_path / name
        doc.save(path)
        doc.close()
        return path

    return _make


@pytest.fixture
def image_only_pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.draw_rect(fitz.Rect(50, 50, 200, 200), color=(0, 0, 0), fill=(0.5, 0.5, 0.5))
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture
def real_manifest_path() -> Path:
    return REPO_ROOT / "data" / "raw" / "manifest.json"


@pytest.fixture
def settings_in(tmp_path: Path):
    def _settings(registry_yaml: str) -> Settings:
        reg = tmp_path / "sources.yaml"
        reg.write_text(registry_yaml, encoding="utf-8")
        return Settings(_env_file=None, data_dir=tmp_path / "data", sources_registry=reg, default_crawl_delay_seconds=0)

    return _settings
