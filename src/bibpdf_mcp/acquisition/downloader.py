"""Streaming PDF downloader with content-type and magic-byte validation.

Phase 1 stub.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ..models import DownloadResult, PdfCandidate


async def download_candidates(
    candidates: Iterable[PdfCandidate],
    output_dir: str | Path,
) -> list[DownloadResult]:
    """Download approved candidates and return per-candidate results."""
    raise NotImplementedError("Phase 5: implement streaming PDF downloader.")
