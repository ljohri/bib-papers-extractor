"""Unpaywall lookup for OA PDF locations.

Unpaywall is the preferred DOI -> OA-PDF source. The free API requires an
``email`` query parameter (we use ``UNPAYWALL_EMAIL`` from settings).

Endpoint:
  GET https://api.unpaywall.org/v2/{doi}?email=<email>
"""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config import get_settings
from ..logging_config import get_logger
from ..models import PdfCandidate

log = get_logger(__name__)

UNPAYWALL_API = "https://api.unpaywall.org/v2"
_RETRYABLE = {408, 425, 429, 500, 502, 503, 504}


class _RetryableHTTPError(Exception):
    pass


async def lookup_unpaywall(
    doi: str,
    *,
    reference_id: str,
    client: httpx.AsyncClient | None = None,
    cache: object | None = None,
) -> list[PdfCandidate]:
    """Return PdfCandidate(s) from Unpaywall for the given DOI.

    Always returns OA-flagged candidates only; non-OA records are filtered out.
    """
    settings = get_settings()
    if not settings.unpaywall_email:
        log.warning("UNPAYWALL_EMAIL not set; Unpaywall lookups will be skipped.")
        return []

    own_client = client is None
    client = client or httpx.AsyncClient(
        timeout=httpx.Timeout(20.0, connect=10.0),
        headers={"User-Agent": settings.user_agent},
        follow_redirects=True,
    )

    try:
        cache_key = f"doi:{doi.lower()}"
        if cache is not None and hasattr(cache, "get"):
            cached = cache.get("unpaywall", cache_key)
            if cached is not None:
                return _to_candidates(cached, reference_id=reference_id)

        url = f"{UNPAYWALL_API}/{doi.lower()}"
        params = {"email": settings.unpaywall_email}

        async def _attempt() -> dict[str, Any] | None:
            resp = await client.get(url, params=params)
            if resp.status_code == 404:
                return None
            if resp.status_code in _RETRYABLE:
                raise _RetryableHTTPError(f"unpaywall {resp.status_code}")
            resp.raise_for_status()
            return resp.json()

        retrier = AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1.5, min=1.0, max=15.0),
            retry=retry_if_exception_type((_RetryableHTTPError, httpx.TransportError)),
            reraise=True,
        )

        try:
            payload: dict[str, Any] | None = None
            async for attempt in retrier:
                with attempt:
                    payload = await _attempt()
        except Exception as e:
            log.warning("Unpaywall lookup for %s failed: %s", doi, e)
            return []

        if payload is None:
            return []

        if cache is not None and hasattr(cache, "set"):
            cache.set("unpaywall", cache_key, payload)

        return _to_candidates(payload, reference_id=reference_id)
    finally:
        if own_client:
            await client.aclose()


def _to_candidates(payload: dict[str, Any], *, reference_id: str) -> list[PdfCandidate]:
    if not payload.get("is_oa", False):
        return []

    out: list[PdfCandidate] = []
    seen_urls: set[str] = set()

    locations: list[dict[str, Any]] = []
    if payload.get("best_oa_location"):
        locations.append(payload["best_oa_location"])
    locations.extend(payload.get("oa_locations", []) or [])

    for loc in locations:
        if not isinstance(loc, dict):
            continue
        url = loc.get("url_for_pdf") or loc.get("url")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        out.append(
            PdfCandidate(
                reference_id=reference_id,
                url=url,
                source="unpaywall",
                license=loc.get("license"),
                is_oa=True,
                confidence=0.92 if loc is payload.get("best_oa_location") else 0.75,
                evidence={
                    "host_type": loc.get("host_type"),
                    "version": loc.get("version"),
                    "is_best": loc is payload.get("best_oa_location"),
                    "doi": payload.get("doi"),
                },
            )
        )
    return out
