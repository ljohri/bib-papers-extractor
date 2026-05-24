"""Manifest writer: persist a RunManifest to ``<output_dir>/manifest.json``."""

from __future__ import annotations

import json
from pathlib import Path

from ..models import RunManifest


def write_manifest(manifest: RunManifest, output_dir: str | Path) -> Path:
    """Write the manifest as pretty-printed JSON. Returns the file path."""
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    path = out / "manifest.json"
    payload = manifest.model_dump(mode="json")
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_manifest(path: str | Path) -> RunManifest:
    """Inverse of write_manifest. Raises FileNotFoundError if missing."""
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(p)
    return RunManifest.model_validate_json(p.read_text(encoding="utf-8"))
