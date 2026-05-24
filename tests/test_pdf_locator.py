"""Tests for the PDF locator + license policy."""

from __future__ import annotations

import httpx
import pytest
import respx

from bibpdf_mcp.acquisition import license_policy
from bibpdf_mcp.acquisition.pdf_locator import find_pdfs
from bibpdf_mcp.models import PdfCandidate, ResolvedWork

# --- license policy --------------------------------------------------------


def test_policy_allows_arxiv_https() -> None:
    c = PdfCandidate(
        reference_id="r", url="https://arxiv.org/pdf/1706.03762.pdf", source="arxiv", is_oa=True
    )
    ok, reason = license_policy.evaluate(c)
    assert ok and reason is None


def test_policy_blocks_http() -> None:
    c = PdfCandidate(
        reference_id="r", url="http://arxiv.org/pdf/1706.03762.pdf", source="arxiv", is_oa=True
    )
    ok, reason = license_policy.evaluate(c)
    assert not ok and "non-https" in (reason or "")


def test_policy_blocks_scihub() -> None:
    c = PdfCandidate(
        reference_id="r", url="https://sci-hub.se/10.foo/bar", source="unpaywall", is_oa=True
    )
    ok, reason = license_policy.evaluate(c)
    assert not ok and "sci-hub" in (reason or "")


def test_policy_blocks_libgen() -> None:
    c = PdfCandidate(
        reference_id="r", url="https://libgen.is/foo.pdf", source="unpaywall", is_oa=True
    )
    ok, reason = license_policy.evaluate(c)
    assert not ok and "libgen" in (reason or "")


def test_policy_blocks_login_path() -> None:
    c = PdfCandidate(
        reference_id="r", url="https://example.org/login?x=1", source="unpaywall", is_oa=True
    )
    ok, reason = license_policy.evaluate(c)
    assert not ok and "login" in (reason or "")


def test_policy_blocks_off_allowlist_source() -> None:
    c = PdfCandidate(
        reference_id="r", url="https://example.org/x.pdf", source="other", is_oa=True
    )
    ok, reason = license_policy.evaluate(c)
    assert not ok and "allowlist" in (reason or "")


def test_policy_blocks_non_oa_unpaywall() -> None:
    c = PdfCandidate(
        reference_id="r", url="https://publisher.org/x.pdf", source="unpaywall", is_oa=False
    )
    ok, reason = license_policy.evaluate(c)
    assert not ok and "is_oa" in (reason or "")


# --- locator ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_pdfs_emits_arxiv_canonical() -> None:
    works = [
        ResolvedWork(
            reference_id="r1",
            title="t",
            source="arxiv",
            confidence=0.98,
            arxiv_id="1706.03762",
        )
    ]
    cands = await find_pdfs(works)
    assert any(
        c.url == "https://arxiv.org/pdf/1706.03762.pdf" and c.source == "arxiv" and c.is_oa
        for c in cands
    )


@pytest.mark.asyncio
async def test_find_pdfs_unpaywall_oa(respx_mock: respx.Router) -> None:
    respx_mock.get("https://api.unpaywall.org/v2/10.foo/bar").mock(
        return_value=httpx.Response(
            200,
            json={
                "is_oa": True,
                "doi": "10.foo/bar",
                "best_oa_location": {
                    "url_for_pdf": "https://repo.example.org/pdf/x.pdf",
                    "license": "cc-by",
                    "host_type": "repository",
                    "version": "publishedVersion",
                },
                "oa_locations": [],
            },
        )
    )
    works = [
        ResolvedWork(
            reference_id="r1",
            title="t",
            source="crossref",
            confidence=1.0,
            doi="10.foo/bar",
        )
    ]
    cands = await find_pdfs(works)
    oa = [c for c in cands if c.is_oa]
    assert any(c.url == "https://repo.example.org/pdf/x.pdf" for c in oa)


@pytest.mark.asyncio
async def test_find_pdfs_filters_scihub(respx_mock: respx.Router) -> None:
    """Even if Unpaywall returned a sci-hub URL (it wouldn't, but defense-in-depth),
    the locator must reject it via license_policy."""
    respx_mock.get("https://api.unpaywall.org/v2/10.bad/x").mock(
        return_value=httpx.Response(
            200,
            json={
                "is_oa": True,
                "doi": "10.bad/x",
                "best_oa_location": {
                    "url_for_pdf": "https://sci-hub.se/10.bad/x",
                    "host_type": "repository",
                },
                "oa_locations": [],
            },
        )
    )
    works = [
        ResolvedWork(
            reference_id="r1", title="t", source="crossref", confidence=1.0, doi="10.bad/x"
        )
    ]
    cands = await find_pdfs(works)
    # The candidate is present but not OA-flagged — downloader will skip it.
    sci = [c for c in cands if "sci-hub" in c.url]
    assert sci, "candidate should appear in the list with policy_reason"
    for c in sci:
        assert not c.is_oa
        assert "sci-hub" in c.evidence.get("policy_reason", "")
