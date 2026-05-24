"""Manifest writer. Phase 1 stub."""

from __future__ import annotations

from pathlib import Path

from ..models import RunManifest


def write_manifest(manifest: RunManifest, output_dir: str | Path) -> Path:
    """Persist a RunManifest to `<output_dir>/manifest.json`."""
    raise NotImplementedError("Phase 5: implement manifest writer.")
