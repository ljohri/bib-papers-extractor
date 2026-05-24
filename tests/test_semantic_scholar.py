"""Comprehensive tests for the unauthenticated Semantic Scholar resolver.

Covers:
  - all six endpoints (search, search/bulk, {paper_id}, batch,
    {paper_id}/references, {paper_id}/citations) without an API key
  - 1 request-per-second rate limit when no API key is configured
  - SQLite read-through cache (second identical lookup skips the network)
  - de-duplication by DOI / S2 paperId / arXiv id
  - Retry-After honoring on HTTP 429
  - exponential backoff on transient 5xx
  - 404 lookups return None
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import httpx
import pytest
import respx
from aiolimiter import AsyncLimiter

from bibpdf_mcp.resolvers import semantic_scholar
from bibpdf_mcp.resolvers.semantic_scholar import (
    S2_API,
    SemanticScholarResolver,
    _dedupe_ids,
    _identity_keys,
    _normalize_id,
    dedupe_papers,
)
from bibpdf_mcp.storage.cache import JsonCache


def _paper_payload(paper_id: str = "abc", doi: str | None = "10.foo/bar") -> dict[str, object]:
    ext: dict[str, str] = {}
    if doi:
        ext["DOI"] = doi
    return {
        "paperId": paper_id,
        "title": "Attention Is All You Need",
        "year": 2017,
        "externalIds": ext,
        "authors": [{"name": "Ashish Vaswani"}],
        "openAccessPdf": None,
        "url": f"https://www.semanticscholar.org/paper/{paper_id}",
    }


# ---------------------------------------------------------------------------
# Endpoint coverage (all unauthenticated)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lookup_paper_by_doi(respx_mock: respx.Router) -> None:
    respx_mock.get(f"{S2_API}/DOI:10.foo/bar").mock(
        return_value=httpx.Response(200, json=_paper_payload())
    )
    async with SemanticScholarResolver() as s2:
        item = await s2.lookup_paper("DOI:10.foo/bar")
    assert item is not None
    assert item["paperId"] == "abc"
    assert item["externalIds"]["DOI"] == "10.foo/bar"


@pytest.mark.asyncio
async def test_lookup_paper_by_arxiv(respx_mock: respx.Router) -> None:
    respx_mock.get(f"{S2_API}/arXiv:1706.03762").mock(
        return_value=httpx.Response(200, json=_paper_payload())
    )
    async with SemanticScholarResolver() as s2:
        item = await s2.lookup_paper("arXiv:1706.03762")
    assert item is not None
    assert item["paperId"] == "abc"


@pytest.mark.asyncio
async def test_lookup_paper_by_s2_id(respx_mock: respx.Router) -> None:
    respx_mock.get(f"{S2_API}/abc123").mock(
        return_value=httpx.Response(200, json=_paper_payload(paper_id="abc123"))
    )
    async with SemanticScholarResolver() as s2:
        item = await s2.lookup_paper("abc123")
    assert item is not None
    assert item["paperId"] == "abc123"


@pytest.mark.asyncio
async def test_lookup_paper_404_returns_none(respx_mock: respx.Router) -> None:
    respx_mock.get(f"{S2_API}/DOI:10.does/not/exist").mock(
        return_value=httpx.Response(404)
    )
    async with SemanticScholarResolver() as s2:
        item = await s2.lookup_paper("DOI:10.does/not/exist")
    assert item is None


@pytest.mark.asyncio
async def test_search_papers(respx_mock: respx.Router) -> None:
    respx_mock.get(f"{S2_API}/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "total": 1,
                "offset": 0,
                "next": 1,
                "data": [_paper_payload()],
            },
        )
    )
    async with SemanticScholarResolver() as s2:
        out = await s2.search_papers("attention is all you need", year=2017)
    assert out is not None
    assert out["total"] == 1
    assert out["data"][0]["paperId"] == "abc"


@pytest.mark.asyncio
async def test_search_bulk_paginates_via_token(respx_mock: respx.Router) -> None:
    captured_tokens: list[str | None] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        captured_tokens.append(request.url.params.get("token"))
        if request.url.params.get("token") == "page-2-token":
            return httpx.Response(200, json={"total": 2, "data": []})
        return httpx.Response(
            200,
            json={
                "total": 2,
                "token": "page-2-token",
                "data": [_paper_payload("a"), _paper_payload("b", doi="10.foo/2")],
            },
        )

    respx_mock.get(f"{S2_API}/search/bulk").mock(side_effect=_handler)

    async with SemanticScholarResolver() as s2:
        page1 = await s2.search_bulk("attention")
        page2 = await s2.search_bulk("attention", token="page-2-token")

    assert page1 is not None
    assert page1["token"] == "page-2-token"
    assert len(page1["data"]) == 2

    assert page2 == {"total": 2, "data": []}
    assert captured_tokens == [None, "page-2-token"]


@pytest.mark.asyncio
async def test_batch_lookup_posts_unique_ids(respx_mock: respx.Router) -> None:
    """``batch_lookup`` must dedupe input ids before POSTing."""
    seen_bodies: list[dict[str, object]] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        import json as _json

        seen_bodies.append(_json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json=[
                _paper_payload("a", doi="10.foo/1"),
                _paper_payload("b", doi="10.foo/2"),
                None,
            ],
        )

    respx_mock.post(f"{S2_API}/batch").mock(side_effect=_capture)

    async with SemanticScholarResolver() as s2:
        # Same paper expressed three different ways + one nonsense id; we
        # expect dedup down to two unique entries.
        results = await s2.batch_lookup(
            [
                "DOI:10.foo/1",
                "doi:10.foo/1",  # case-insensitive dup
                "ARXIV:1706.03762v3",  # different paper, normalized to v-stripped
                "arxiv:1706.03762",  # dup of the above
                "DOI:10.foo/2",  # third unique
            ]
        )

    assert len(seen_bodies) == 1
    body_ids = seen_bodies[0]["ids"]
    # Three unique ids preserved in original order.
    assert body_ids == ["DOI:10.foo/1", "ARXIV:1706.03762v3", "DOI:10.foo/2"]
    # And we get back the list S2 returned (None for the missing one).
    assert len(results) == 3
    assert results[0] is not None and results[0]["paperId"] == "a"
    assert results[2] is None


@pytest.mark.asyncio
async def test_get_references(respx_mock: respx.Router) -> None:
    respx_mock.get(f"{S2_API}/abc/references").mock(
        return_value=httpx.Response(
            200,
            json={
                "offset": 0,
                "next": 100,
                "data": [
                    {"citedPaper": _paper_payload("r1", doi="10.ref/1")},
                    {"citedPaper": _paper_payload("r2", doi="10.ref/2")},
                ],
            },
        )
    )
    async with SemanticScholarResolver() as s2:
        out = await s2.get_references("abc", limit=100, offset=0)
    assert out is not None
    assert out["offset"] == 0
    assert len(out["data"]) == 2
    assert out["data"][0]["citedPaper"]["paperId"] == "r1"


@pytest.mark.asyncio
async def test_get_citations(respx_mock: respx.Router) -> None:
    respx_mock.get(f"{S2_API}/abc/citations").mock(
        return_value=httpx.Response(
            200,
            json={
                "offset": 0,
                "next": 100,
                "data": [{"citingPaper": _paper_payload("c1", doi="10.cit/1")}],
            },
        )
    )
    async with SemanticScholarResolver() as s2:
        out = await s2.get_citations("abc", limit=50, offset=0)
    assert out is not None
    assert out["data"][0]["citingPaper"]["paperId"] == "c1"


# ---------------------------------------------------------------------------
# Compliance: rate limit, cache, dedup, Retry-After, backoff
# ---------------------------------------------------------------------------


def test_unauthenticated_rate_limit_is_one_per_second(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without an API key the limiter must be exactly 1 r/s."""
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "")
    from bibpdf_mcp import config

    config.get_settings.cache_clear()

    s2 = SemanticScholarResolver()
    try:
        assert isinstance(s2._limiter, AsyncLimiter)
        assert s2._limiter.max_rate == 1.0
        assert s2._limiter.time_period == 1.0
        assert s2.rate_limit_per_sec == 1.0
        assert "x-api-key" not in s2._client.headers
    finally:
        asyncio.run(s2.aclose())


def test_authenticated_rate_limit_is_higher(monkeypatch: pytest.MonkeyPatch) -> None:
    """With an API key, the limiter is bumped above 1 r/s."""
    monkeypatch.setenv("SEMANTIC_SCHOLAR_API_KEY", "secret-key")
    from bibpdf_mcp import config

    config.get_settings.cache_clear()

    s2 = SemanticScholarResolver()
    try:
        assert s2._limiter.max_rate > 1.0
        assert s2._client.headers.get("x-api-key") == "secret-key"
    finally:
        asyncio.run(s2.aclose())


@pytest.mark.asyncio
async def test_rate_limit_enforces_one_per_second_in_practice(
    respx_mock: respx.Router,
) -> None:
    """Two consecutive calls take >= ~1s thanks to the 1 r/s limiter."""
    respx_mock.get(f"{S2_API}/DOI:10.foo/a").mock(
        return_value=httpx.Response(200, json=_paper_payload("a", doi="10.foo/a"))
    )
    respx_mock.get(f"{S2_API}/DOI:10.foo/b").mock(
        return_value=httpx.Response(200, json=_paper_payload("b", doi="10.foo/b"))
    )

    async with SemanticScholarResolver() as s2:
        start = time.monotonic()
        await s2.lookup_paper("DOI:10.foo/a")
        await s2.lookup_paper("DOI:10.foo/b")
        elapsed = time.monotonic() - start

    # First request consumes the burst token; second waits ~1s for the next.
    # Allow generous CI slack but still meaningful.
    assert elapsed >= 0.85, f"expected >= ~1s between calls, got {elapsed:.3f}s"


@pytest.mark.asyncio
async def test_cache_hit_skips_network(respx_mock: respx.Router, tmp_path: Path) -> None:
    cache = JsonCache(tmp_path / "s2-cache.sqlite")
    route = respx_mock.get(f"{S2_API}/DOI:10.cache/me").mock(
        return_value=httpx.Response(200, json=_paper_payload(doi="10.cache/me"))
    )

    async with SemanticScholarResolver(cache=cache) as s2:
        first = await s2.lookup_paper("DOI:10.cache/me")
        second = await s2.lookup_paper("DOI:10.cache/me")

    assert first == second
    assert route.call_count == 1, "second lookup should hit the cache, not the network"


def test_dedupe_papers_by_doi_arxiv_paperid() -> None:
    """A reference indexed by three different ids must collapse to one record."""
    by_doi = {
        "paperId": "id-doi",
        "title": "Same paper",
        "externalIds": {"DOI": "10.foo/bar"},
    }
    by_arxiv = {
        "paperId": "id-doi",  # same S2 id
        "title": "Same paper",
        "externalIds": {"ArXiv": "1706.03762v2"},
    }
    by_s2_only = {
        "paperId": "id-doi",
        "title": "Same paper",
        "externalIds": {},
    }
    different = {
        "paperId": "other",
        "title": "Other paper",
        "externalIds": {"DOI": "10.something/else"},
    }

    out = dedupe_papers([by_doi, by_arxiv, by_s2_only, different])
    assert len(out) == 2
    assert out[0]["paperId"] == "id-doi"
    assert out[1]["paperId"] == "other"


def test_dedupe_papers_collapses_via_overlapping_doi() -> None:
    """Two records that share a DOI but different paperIds still collapse."""
    a = {"paperId": "p1", "externalIds": {"DOI": "10.foo/x"}}
    b = {"paperId": "p2", "externalIds": {"DOI": "10.foo/x"}}
    out = dedupe_papers([a, b])
    assert len(out) == 1


def test_dedupe_papers_collapses_via_arxiv_version_strip() -> None:
    a = {"paperId": "p1", "externalIds": {"ArXiv": "1706.03762"}}
    b = {"paperId": "p2", "externalIds": {"ArXiv": "1706.03762v3"}}
    out = dedupe_papers([a, b])
    assert len(out) == 1


def test_normalize_id_and_dedupe_ids() -> None:
    assert _normalize_id("DOI:10.Foo/Bar") == "doi:10.foo/bar"
    assert _normalize_id("ARXIV:1706.03762v3") == "arxiv:1706.03762"
    assert _normalize_id("plainSha1Id") == "plainsha1id"

    out = _dedupe_ids(["DOI:10.foo/x", "doi:10.foo/x", "arxiv:1706.03762v1", "ARXIV:1706.03762"])
    # First occurrences are kept verbatim, dups removed.
    assert out == ["DOI:10.foo/x", "arxiv:1706.03762v1"]


def test_identity_keys_handles_missing_fields() -> None:
    assert _identity_keys({}) == set()
    assert _identity_keys({"paperId": "X"}) == {"s2:x"}
    assert _identity_keys({"externalIds": {"DOI": "10.A/B"}}) == {"doi:10.a/b"}


@pytest.mark.asyncio
async def test_retry_after_is_honored_on_429(
    respx_mock: respx.Router,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 429 with ``Retry-After: 1`` should result in an asyncio.sleep(>=1) call."""
    sleeps: list[float] = []
    real_sleep = asyncio.sleep

    async def _record_sleep(delay: float) -> None:
        sleeps.append(delay)
        await real_sleep(0)  # don't actually sleep — keep tests fast

    monkeypatch.setattr(
        "bibpdf_mcp.resolvers.base.asyncio.sleep",
        _record_sleep,
        raising=True,
    )

    route = respx_mock.get(f"{S2_API}/DOI:10.rate/limit")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "1"}, json={"error": "rate"}),
        httpx.Response(200, json=_paper_payload(doi="10.rate/limit")),
    ]

    async with SemanticScholarResolver() as s2:
        out = await s2.lookup_paper("DOI:10.rate/limit")

    assert out is not None
    assert out["paperId"] == "abc"
    assert any(s >= 1.0 for s in sleeps), (
        f"expected an asyncio.sleep(>=1.0) for Retry-After, got {sleeps!r}"
    )


@pytest.mark.asyncio
async def test_exponential_backoff_on_transient_5xx(respx_mock: respx.Router) -> None:
    """A transient 503 followed by a 200 must succeed via tenacity retry."""
    route = respx_mock.get(f"{S2_API}/DOI:10.flaky/svc")
    route.side_effect = [
        httpx.Response(503, text="busy"),
        httpx.Response(200, json=_paper_payload(doi="10.flaky/svc")),
    ]
    async with SemanticScholarResolver() as s2:
        out = await s2.lookup_paper("DOI:10.flaky/svc")

    assert out is not None
    assert route.call_count == 2


@pytest.mark.asyncio
async def test_resolve_does_not_require_api_key(respx_mock: respx.Router) -> None:
    """The high-level resolve() path works fully unauthenticated."""
    respx_mock.get(f"{S2_API}/DOI:10.foo/bar").mock(
        return_value=httpx.Response(200, json=_paper_payload())
    )
    from bibpdf_mcp.models import Reference

    ref = Reference(id="r1", raw="x", doi="10.foo/bar", title="t")
    async with SemanticScholarResolver() as s2:
        # Sanity: no API key in headers.
        assert "x-api-key" not in s2._client.headers
        works = await s2.resolve(ref)

    assert len(works) == 1
    assert works[0].doi == "10.foo/bar"
    assert works[0].source == "semantic_scholar"


def test_module_exposes_dedupe_helper() -> None:
    """dedupe_papers is part of the public module surface."""
    assert callable(semantic_scholar.dedupe_papers)
