"""Markdown report writer. Phase 1 stub."""

from __future__ import annotations

from pathlib import Path

from ..models import RunManifest


def write_markdown_report(manifest: RunManifest, output_dir: str | Path) -> Path:
    """Persist a human-readable Markdown report at `<output_dir>/report.md`."""
    raise NotImplementedError("Phase 5: implement Markdown report writer.")
