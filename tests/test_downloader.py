"""Tests for the streaming PDF downloader."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from bibpdf_mcp.acquisition.downloader import download_candidates
from bibpdf_mcp.models import PdfCandidate, ResolvedWork

_PDF_BYTES = b"%PDF-1.4\n%fake content\n%%EOF\n"


def _work(ref_id: str = "r1") -> ResolvedWork:
    return ResolvedWork(
        reference_id=ref_id,
        title="Attention Is All You Need",
        authors=["Vaswani, Ashish"],
        year=2017,
        doi="10.foo/bar",
        source="arxiv",
        confidence=0.98,
        arxiv_id="1706.03762",
    )


@pytest.mark.asyncio
async def test_downloader_writes_pdf_with_deterministic_name(
    respx_mock: respx.Router, tmp_path: Path
) -> None:
    respx_mock.get("https://arxiv.org/pdf/1706.03762.pdf").mock(
        return_value=httpx.Response(
            200,
            content=_PDF_BYTES,
            headers={"Content-Type": "application/pdf"},
        )
    )

    cand = PdfCandidate(
        reference_id="r1",
        url="https://arxiv.org/pdf/1706.03762.pdf",
        source="arxiv",
        is_oa=True,
        confidence=0.97,
    )
    works = {"r1": _work()}

    results = await download_candidates([cand], tmp_path, works=works)
    assert len(results) == 1
    res = results[0]
    assert res.status == "downloaded"
    assert res.file_path is not None
    p = Path(res.file_path)
    assert p.exists()
    assert p.read_bytes().startswith(b"%PDF-")
    # Deterministic name: 2017_Vaswani_AttentionIsAllYouNeed_<hash>.pdf
    assert p.name.startswith("2017_Vaswani_AttentionIsAllYouNeed_")
    assert p.name.endswith(".pdf")


@pytest.mark.asyncio
async def test_downloader_rejects_html_landing_page(
    respx_mock: respx.Router, tmp_path: Path
) -> None:
    respx_mock.get("https://example.org/landing").mock(
        return_value=httpx.Response(
            200,
            content=b"<html>Login required</html>",
            headers={"Content-Type": "text/html"},
        )
    )
    cand = PdfCandidate(
        reference_id="r1",
        url="https://example.org/landing",
        source="unpaywall",
        is_oa=True,
        confidence=0.5,
    )
    results = await download_candidates([cand], tmp_path, works={"r1": _work()})
    assert results[0].status == "failed"
    assert "non_pdf_content_type" in (results[0].error or "")
    assert not any(p.suffix == ".pdf" for p in tmp_path.iterdir())


@pytest.mark.asyncio
async def test_downloader_rejects_bad_magic_bytes(
    respx_mock: respx.Router, tmp_path: Path
) -> None:
    respx_mock.get("https://example.org/sneaky.pdf").mock(
        return_value=httpx.Response(
            200,
            content=b"NOT A PDF\n",
            headers={"Content-Type": "application/pdf"},
        )
    )
    cand = PdfCandidate(
        reference_id="r1",
        url="https://example.org/sneaky.pdf",
        source="unpaywall",
        is_oa=True,
        confidence=0.5,
    )
    results = await download_candidates([cand], tmp_path, works={"r1": _work()})
    assert results[0].status == "failed"
    assert results[0].error == "non_pdf_magic_bytes"


@pytest.mark.asyncio
async def test_downloader_skips_policy_rejected(tmp_path: Path) -> None:
    cand = PdfCandidate(
        reference_id="r1",
        url="https://sci-hub.se/10.foo/bar",
        source="unpaywall",
        is_oa=True,
        confidence=0.9,
    )
    results = await download_candidates([cand], tmp_path, works={"r1": _work()})
    assert results[0].status == "skipped"
    assert "sci-hub" in (results[0].error or "").lower()


@pytest.mark.asyncio
async def test_downloader_picks_highest_confidence_per_reference(
    respx_mock: respx.Router, tmp_path: Path
) -> None:
    """Two allowed candidates for the same reference — only the best should be downloaded."""
    respx_mock.get("https://arxiv.org/pdf/1706.03762.pdf").mock(
        return_value=httpx.Response(
            200, content=_PDF_BYTES, headers={"Content-Type": "application/pdf"}
        )
    )

    high = PdfCandidate(
        reference_id="r1",
        url="https://arxiv.org/pdf/1706.03762.pdf",
        source="arxiv",
        is_oa=True,
        confidence=0.97,
    )
    low = PdfCandidate(
        reference_id="r1",
        url="https://repo.example.org/x.pdf",
        source="unpaywall",
        is_oa=True,
        confidence=0.5,
    )
    results = await download_candidates([low, high], tmp_path, works={"r1": _work()})
    assert len(results) == 1
    assert results[0].url == "https://arxiv.org/pdf/1706.03762.pdf"
    assert results[0].status == "downloaded"
