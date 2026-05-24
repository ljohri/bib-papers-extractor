"""JSON summary report writer.

The full structured data lives in ``manifest.json``; this is a compact summary
suitable for tooling/dashboards.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..models import RunManifest


def write_json_report(manifest: RunManifest, output_dir: str | Path) -> Path:
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    path = out / "report.json"

    payload = {
        "run_id": manifest.run_id,
        "source_path": manifest.source_path,
        "strategy": manifest.strategy,
        "started_at": manifest.started_at.isoformat(),
        "finished_at": manifest.finished_at.isoformat() if manifest.finished_at else None,
        "summary": manifest.summary.model_dump(),
        "downloads": [
            {
                "reference_id": d.reference_id,
                "url": d.url,
                "status": d.status,
                "file_path": d.file_path,
                "error": d.error,
            }
            for d in manifest.downloads
        ],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
