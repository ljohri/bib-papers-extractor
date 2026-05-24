"""Shared base class for async metadata resolvers.

Provides:
  - a single shared `httpx.AsyncClient` per resolver instance
  - a per-resolver `aiolimiter.AsyncLimiter` for polite-pool rate limiting
  - tenacity-based exponential-backoff retries for 5xx/429/network errors
  - polite User-Agent / mailto headers from settings
  - a small SQLite read-through cache for response bodies
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from aiolimiter import AsyncLimiter
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config import get_settings
from ..logging_config import get_logger
from ..models import Reference, ResolvedWork

log = get_logger(__name__)

_RETRYABLE_STATUSES = {408, 425, 429, 500, 502, 503, 504}
# Cap on how long we'll honor a server-provided Retry-After before giving up
# and letting tenacity's exponential schedule decide instead.
_MAX_RETRY_AFTER_SECONDS = 60.0


def _parse_retry_after(header: str | None) -> float:
    """Parse a Retry-After header into seconds.

    Accepts both delta-seconds (RFC 7231 §7.1.3) and HTTP-date formats. Returns
    0.0 for missing/unparseable headers. Negative values are clamped to 0.
    """
    if not header:
        return 0.0
    raw = header.strip()
    try:
        return max(0.0, float(raw))
    except ValueError:
        pass
    try:
        target = parsedate_to_datetime(raw)
        if target.tzinfo is None:
            target = target.replace(tzinfo=UTC)
        return max(0.0, (target - datetime.now(UTC)).total_seconds())
    except (TypeError, ValueError):
        return 0.0


class _RetryableHTTPError(Exception):
    """Wrapped HTTP error that triggers a tenacity retry."""


class BaseResolver(ABC):
    """Common interface and helpers for all metadata resolvers."""

    source: str = "base"
    base_url: str = ""
    rate_limit_per_sec: float = 5.0
    timeout_seconds: float = 20.0
    cache_ttl_days: int = 30

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        cache: Any | None = None,
    ) -> None:
        self.settings = get_settings()
        self._owns_client = client is None
        self._client = client or self._build_client()
        self._limiter = AsyncLimiter(max_rate=self.rate_limit_per_sec, time_period=1.0)
        self._cache = cache  # bibpdf_mcp.storage.cache.JsonCache | None

    def _build_client(self) -> httpx.AsyncClient:
        headers: dict[str, str] = {"User-Agent": self.settings.user_agent}
        if self.settings.crossref_mailto and self.source in {"crossref", "openalex"}:
            headers["From"] = self.settings.crossref_mailto
        return httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds, connect=10.0),
            headers=headers,
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> BaseResolver:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    # --- HTTP / cache helpers ----------------------------------------------

    async def _get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        cache_key: str | None = None,
    ) -> dict[str, Any] | None:
        """GET with retries and optional read-through cache. Returns None on 404."""
        if cache_key and self._cache is not None:
            cached = self._cache.get(self.source, cache_key)
            if cached is not None:
                log.debug("cache hit %s/%s", self.source, cache_key)
                return cached

        async def _attempt() -> dict[str, Any] | None:
            async with self._limiter:
                resp = await self._client.get(url, params=params)
            return await self._handle_json_response(resp)

        return await self._retry_loop(_attempt, op=f"GET {url}", cache_key=cache_key)

    async def _post_json(
        self,
        url: str,
        *,
        json_body: Any,
        params: dict[str, Any] | None = None,
        cache_key: str | None = None,
    ) -> dict[str, Any] | list[Any] | None:
        """POST with retries and optional read-through cache.

        Used for endpoints like Semantic Scholar's ``/paper/batch`` which take
        a JSON body. Returns parsed JSON (dict or list), or None on 404 / total
        failure.
        """
        if cache_key and self._cache is not None:
            cached = self._cache.get(self.source, cache_key)
            if cached is not None:
                log.debug("cache hit %s/%s", self.source, cache_key)
                return cached

        async def _attempt() -> dict[str, Any] | list[Any] | None:
            async with self._limiter:
                resp = await self._client.post(url, params=params, json=json_body)
            return await self._handle_json_response(resp)

        return await self._retry_loop(_attempt, op=f"POST {url}", cache_key=cache_key)

    async def _get_text(self, url: str, *, params: dict[str, Any] | None = None) -> str | None:
        async def _attempt() -> str | None:
            async with self._limiter:
                resp = await self._client.get(url, params=params)
            if resp.status_code == 404:
                return None
            if resp.status_code in _RETRYABLE_STATUSES:
                await self._maybe_sleep_retry_after(resp)
                raise _RetryableHTTPError(f"{self.source} {resp.status_code}")
            resp.raise_for_status()
            return resp.text

        return await self._retry_loop(_attempt, op=f"GET {url}", cache_key=None)

    # --- Internal helpers ---------------------------------------------------

    async def _maybe_sleep_retry_after(self, resp: httpx.Response) -> None:
        """If the response carries a Retry-After header, sleep that long.

        Bounded by ``_MAX_RETRY_AFTER_SECONDS`` to avoid pathological values.
        """
        delta = _parse_retry_after(resp.headers.get("Retry-After"))
        if delta <= 0:
            return
        delta = min(delta, _MAX_RETRY_AFTER_SECONDS)
        log.info(
            "%s honoring Retry-After: %.2fs (status=%d)",
            self.source,
            delta,
            resp.status_code,
        )
        await asyncio.sleep(delta)

    async def _handle_json_response(
        self, resp: httpx.Response
    ) -> dict[str, Any] | list[Any] | None:
        if resp.status_code == 404:
            return None
        if resp.status_code in _RETRYABLE_STATUSES:
            await self._maybe_sleep_retry_after(resp)
            raise _RetryableHTTPError(
                f"{self.source} {resp.status_code} for {resp.request.url}"
            )
        resp.raise_for_status()
        try:
            return resp.json()
        except json.JSONDecodeError as e:
            raise _RetryableHTTPError(f"invalid JSON from {self.source}: {e}") from e

    async def _retry_loop(
        self,
        attempt_fn: Any,
        *,
        op: str,
        cache_key: str | None,
    ) -> Any:
        retrier = AsyncRetrying(
            stop=stop_after_attempt(4),
            wait=wait_exponential(multiplier=1.5, min=1.0, max=20.0),
            retry=retry_if_exception_type(
                (_RetryableHTTPError, httpx.TransportError, httpx.RemoteProtocolError)
            ),
            reraise=True,
        )

        payload: Any = None
        try:
            async for attempt in retrier:
                with attempt:
                    payload = await attempt_fn()
        except Exception as e:
            log.warning("%s %s failed: %s", self.source, op, e)
            return None

        if cache_key and self._cache is not None and payload is not None:
            ttl = timedelta(days=self.cache_ttl_days)
            self._cache.set(
                self.source,
                cache_key,
                payload,
                expires_at=datetime.now(UTC) + ttl,
            )
        return payload

    # --- Public API --------------------------------------------------------

    @abstractmethod
    async def resolve(self, reference: Reference) -> list[ResolvedWork]:
        """Return zero or more candidate ResolvedWork entries for the reference."""
        raise NotImplementedError
