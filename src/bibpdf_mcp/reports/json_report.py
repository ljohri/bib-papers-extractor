"""JSON report writer. Phase 1 stub."""

from __future__ import annotations

from pathlib import Path

from ..models import RunManifest


def write_json_report(manifest: RunManifest, output_dir: str | Path) -> Path:
    """Persist a JSON report alongside the manifest."""
    raise NotImplementedError("Phase 5: implement JSON report writer.")
