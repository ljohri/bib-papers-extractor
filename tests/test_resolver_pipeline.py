"""Tests for the resolver pipeline confidence scoring and orchestration."""

from __future__ import annotations

import httpx
import pytest
import respx

from bibpdf_mcp.models import Reference, ResolvedWork
from bibpdf_mcp.resolvers.crossref import CrossrefResolver
from bibpdf_mcp.resolvers.openalex import OpenAlexResolver
from bibpdf_mcp.resolvers.resolver_pipeline import build_resolvers, resolve_all, score

# --- Confidence scoring -----------------------------------------------------


def test_score_doi_exact() -> None:
    r = Reference(id="r1", raw="x", doi="10.foo/bar", title="T")
    c = ResolvedWork(reference_id="r1", title="other", source="crossref", confidence=0, doi="10.foo/bar")
    assert score(r, c) == 1.0


def test_score_arxiv_exact_with_version_suffix() -> None:
    r = Reference(id="r1", raw="x", arxiv_id="1706.03762", title="T")
    c = ResolvedWork(reference_id="r1", title="other", source="arxiv", confidence=0, arxiv_id="1706.03762v3")
    assert score(r, c) == 0.98


def test_score_title_year_match() -> None:
    r = Reference(id="r1", raw="x", title="Attention Is All You Need", year=2017)
    c = ResolvedWork(
        reference_id="r1",
        title="Attention is all you need",
        year=2017,
        authors=["Vaswani A"],
        source="crossref",
        confidence=0,
    )
    assert score(r, c) == 0.93


def test_score_fuzzy_title_with_author_overlap() -> None:
    """Fuzzy title (with one extra/missing word) plus author overlap should land
    in the high-fuzzy band (per spec: 0.85 when fuzzy >= 0.92 and overlap >= 0.5).
    """
    r = Reference(
        id="r1", raw="x", title="Attention is all you need", authors=["Vaswani"]
    )
    c = ResolvedWork(
        reference_id="r1",
        title="Attention Is All You Need",  # only casing differs
        authors=["Vaswani A", "Shazeer N"],
        source="crossref",
        confidence=0,
    )
    assert score(r, c) == 0.85


def test_score_unrelated_low() -> None:
    r = Reference(id="r1", raw="x", title="Attention is all you need")
    c = ResolvedWork(
        reference_id="r1", title="Quantum gravity in five dimensions", source="crossref", confidence=0
    )
    assert score(r, c) < 0.7


# --- Resolver behavior with respx mocks -------------------------------------


@pytest.mark.asyncio
async def test_crossref_doi_lookup_success(respx_mock: respx.Router) -> None:
    respx_mock.get("https://api.crossref.org/works/10.foo/bar").mock(
        return_value=httpx.Response(
            200,
            json={
                "message": {
                    "DOI": "10.foo/bar",
                    "title": ["Attention Is All You Need"],
                    "issued": {"date-parts": [[2017]]},
                    "author": [{"given": "Ashish", "family": "Vaswani"}],
                    "URL": "https://doi.org/10.foo/bar",
                }
            },
        )
    )
    r = Reference(id="r1", raw="x", doi="10.foo/bar")
    async with CrossrefResolver() as cr:
        out = await cr.resolve(r)
    assert len(out) == 1
    assert out[0].doi == "10.foo/bar"
    assert out[0].title.lower().startswith("attention")
    assert out[0].year == 2017


@pytest.mark.asyncio
async def test_crossref_doi_404_returns_empty(respx_mock: respx.Router) -> None:
    respx_mock.get("https://api.crossref.org/works/10.missing/x").mock(
        return_value=httpx.Response(404)
    )
    # And the title fallback should also miss.
    respx_mock.get("https://api.crossref.org/works").mock(
        return_value=httpx.Response(200, json={"message": {"items": []}})
    )
    r = Reference(id="r1", raw="x", doi="10.missing/x", title="Nonexistent")
    async with CrossrefResolver() as cr:
        out = await cr.resolve(r)
    assert out == []


@pytest.mark.asyncio
async def test_openalex_search(respx_mock: respx.Router) -> None:
    respx_mock.get("https://api.openalex.org/works").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "https://openalex.org/W123",
                        "title": "Attention Is All You Need",
                        "publication_year": 2017,
                        "doi": "https://doi.org/10.foo/bar",
                        "authorships": [{"author": {"display_name": "Ashish Vaswani"}}],
                        "ids": {"openalex": "https://openalex.org/W123"},
                    }
                ]
            },
        )
    )
    r = Reference(id="r1", raw="x", title="Attention is all you need", year=2017)
    async with OpenAlexResolver() as oa:
        out = await oa.resolve(r)
    assert len(out) == 1
    assert out[0].openalex_id == "W123"
    assert out[0].doi == "10.foo/bar"


@pytest.mark.asyncio
async def test_resolve_all_chooses_best_candidate(respx_mock: respx.Router) -> None:
    """End-to-end pipeline: DOI lookup hits Crossref+OpenAlex+S2; the best is returned."""
    # Crossref DOI hit
    respx_mock.get("https://api.crossref.org/works/10.foo/bar").mock(
        return_value=httpx.Response(
            200,
            json={
                "message": {
                    "DOI": "10.foo/bar",
                    "title": ["Attention Is All You Need"],
                    "issued": {"date-parts": [[2017]]},
                    "author": [{"given": "Ashish", "family": "Vaswani"}],
                }
            },
        )
    )
    # OpenAlex DOI hit
    respx_mock.get(url__regex=r"^https://api\.openalex\.org/works/doi:.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "https://openalex.org/W1",
                "title": "Attention Is All You Need",
                "publication_year": 2017,
                "doi": "https://doi.org/10.foo/bar",
                "ids": {"openalex": "https://openalex.org/W1"},
            },
        )
    )
    # S2 DOI hit
    respx_mock.get(url__regex=r"^https://api\.semanticscholar\.org/graph/v1/paper/DOI:.*").mock(
        return_value=httpx.Response(
            200,
            json={
                "paperId": "abc",
                "title": "Attention Is All You Need",
                "year": 2017,
                "externalIds": {"DOI": "10.foo/bar"},
                "authors": [{"name": "Ashish Vaswani"}],
            },
        )
    )

    refs = [Reference(id="r1", raw="x", doi="10.foo/bar", title="Attention Is All You Need", year=2017)]
    resolvers = build_resolvers()
    try:
        resolved = await resolve_all(refs, strategy="balanced", resolvers=resolvers)
    finally:
        for rsv in resolvers.values():
            await rsv.aclose()

    assert len(resolved) == 1
    assert resolved[0].confidence == 1.0
    assert resolved[0].doi == "10.foo/bar"
