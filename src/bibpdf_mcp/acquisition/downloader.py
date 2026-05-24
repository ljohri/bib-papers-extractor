"""Streaming PDF downloader.

Each candidate goes through:

  1. license_policy.evaluate()        — must allow
  2. httpx GET (streaming)            — follow redirects
  3. Content-Type header check        — must be application/pdf or
                                         application/octet-stream
  4. PDF magic-byte check             — first 5 bytes must be ``%PDF-``
  5. Write to disk via aiofiles
  6. Filename via filename_policy.build_filename(work)

A `ResolvedWork` lookup is required to compute the deterministic filename. The
caller passes a `dict[reference_id -> ResolvedWork]`; if a candidate references
an unknown work the candidate's URL filename is used as a fallback.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
from pathlib import Path

import aiofiles
import httpx

from ..config import get_settings
from ..logging_config import get_logger
from ..models import DownloadResult, PdfCandidate, ResolvedWork
from ..storage.filename_policy import build_filename
from . import license_policy

log = get_logger(__name__)

_PDF_MAGIC = b"%PDF-"
_ACCEPTABLE_CONTENT_TYPES: tuple[str, ...] = (
    "application/pdf",
    "application/octet-stream",
    "binary/octet-stream",
)


async def download_candidates(
    candidates: Iterable[PdfCandidate],
    output_dir: str | Path,
    *,
    works: Mapping[str, ResolvedWork] | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[DownloadResult]:
    """Download approved candidates, one per reference_id (best-confidence wins).

    Returns one DownloadResult per attempted candidate (downloaded, skipped, or
    failed). Skipped candidates carry the policy reason in ``error``.
    """
    settings = get_settings()
    works = works or {}

    out_dir = Path(output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    own_client = client is None
    client = client or httpx.AsyncClient(
        timeout=httpx.Timeout(60.0, connect=10.0),
        headers={"User-Agent": settings.user_agent},
        follow_redirects=True,
    )

    selected = _select_per_reference(list(candidates))

    sem = asyncio.Semaphore(max(1, settings.max_concurrent_requests))

    async def _one(c: PdfCandidate) -> DownloadResult:
        async with sem:
            return await _download_one(c, out_dir, works.get(c.reference_id), client)

    try:
        return await asyncio.gather(*[_one(c) for c in selected])
    finally:
        if own_client:
            await client.aclose()


def _select_per_reference(candidates: list[PdfCandidate]) -> list[PdfCandidate]:
    """For each reference_id pick the highest-confidence allowed candidate.

    If no candidate is allowed for a given reference, surface the highest-
    confidence rejected candidate so the caller can record the skip reason.
    """
    by_ref: dict[str, list[PdfCandidate]] = {}
    for c in candidates:
        by_ref.setdefault(c.reference_id, []).append(c)

    out: list[PdfCandidate] = []
    for cands in by_ref.values():
        allowed: list[PdfCandidate] = []
        rejected: list[PdfCandidate] = []
        for c in cands:
            ok, _ = license_policy.evaluate(c)
            (allowed if ok else rejected).append(c)
        if allowed:
            allowed.sort(key=lambda c: c.confidence, reverse=True)
            out.append(allowed[0])
        elif rejected:
            rejected.sort(key=lambda c: c.confidence, reverse=True)
            out.append(rejected[0])
    return out


async def _download_one(
    candidate: PdfCandidate,
    out_dir: Path,
    work: ResolvedWork | None,
    client: httpx.AsyncClient,
) -> DownloadResult:
    allowed, reason = license_policy.evaluate(candidate)
    if not allowed:
        return DownloadResult(
            reference_id=candidate.reference_id,
            url=candidate.url,
            status="skipped",
            error=f"policy: {reason}",
        )

    fname = build_filename(work) if work is not None else _fallback_filename(candidate)
    path = out_dir / fname

    try:
        async with client.stream("GET", candidate.url) as resp:
            if resp.status_code != 200:
                return DownloadResult(
                    reference_id=candidate.reference_id,
                    url=candidate.url,
                    status="failed",
                    error=f"http_{resp.status_code}",
                    content_type=resp.headers.get("content-type"),
                )

            ctype = (resp.headers.get("content-type") or "").lower().split(";", 1)[0].strip()
            if ctype and not any(ctype == acc for acc in _ACCEPTABLE_CONTENT_TYPES):
                return DownloadResult(
                    reference_id=candidate.reference_id,
                    url=candidate.url,
                    status="failed",
                    error=f"non_pdf_content_type:{ctype}",
                    content_type=ctype,
                )

            tmp = path.with_suffix(path.suffix + ".part")
            magic_checked = False
            total = 0
            async with aiofiles.open(tmp, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=64 * 1024):
                    if not magic_checked:
                        if not chunk.startswith(_PDF_MAGIC):
                            await f.close()
                            tmp.unlink(missing_ok=True)
                            return DownloadResult(
                                reference_id=candidate.reference_id,
                                url=candidate.url,
                                status="failed",
                                error="non_pdf_magic_bytes",
                                content_type=ctype or None,
                            )
                        magic_checked = True
                    await f.write(chunk)
                    total += len(chunk)

            tmp.replace(path)
            return DownloadResult(
                reference_id=candidate.reference_id,
                url=candidate.url,
                status="downloaded",
                file_path=str(path),
                bytes_written=total,
                content_type=ctype or "application/pdf",
            )
    except httpx.HTTPError as e:
        return DownloadResult(
            reference_id=candidate.reference_id,
            url=candidate.url,
            status="failed",
            error=f"http_error:{type(e).__name__}:{e}",
        )
    except OSError as e:
        return DownloadResult(
            reference_id=candidate.reference_id,
            url=candidate.url,
            status="failed",
            error=f"io_error:{e}",
        )


def _fallback_filename(candidate: PdfCandidate) -> str:
    base = candidate.url.rsplit("/", 1)[-1].split("?", 1)[0] or "download.pdf"
    if not base.lower().endswith(".pdf"):
        base = f"{candidate.reference_id}.pdf"
    return base
