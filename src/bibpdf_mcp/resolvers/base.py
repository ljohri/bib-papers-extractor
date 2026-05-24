"""Shared base class for async metadata resolvers.

Provides:
  - a single shared `httpx.AsyncClient` per resolver instance
  - a per-resolver `aiolimiter.AsyncLimiter` for polite-pool rate limiting
  - tenacity-based exponential-backoff retries for 5xx/429/network errors
  - polite User-Agent / mailto headers from settings
  - a small SQLite read-through cache for response bodies
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
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
            if resp.status_code == 404:
                return None
            if resp.status_code in _RETRYABLE_STATUSES:
                raise _RetryableHTTPError(
                    f"{self.source} {resp.status_code} for {resp.request.url}"
                )
            resp.raise_for_status()
            try:
                return resp.json()
            except json.JSONDecodeError as e:
                raise _RetryableHTTPError(f"invalid JSON from {self.source}: {e}") from e

        retrier = AsyncRetrying(
            stop=stop_after_attempt(4),
            wait=wait_exponential(multiplier=1.5, min=1.0, max=20.0),
            retry=retry_if_exception_type(
                (_RetryableHTTPError, httpx.TransportError, httpx.RemoteProtocolError)
            ),
            reraise=True,
        )

        try:
            async for attempt in retrier:
                with attempt:
                    payload = await _attempt()
        except Exception as e:
            log.warning("%s GET %s failed: %s", self.source, url, e)
            return None

        if cache_key and self._cache is not None and payload is not None:
            ttl = timedelta(days=self.cache_ttl_days)
            self._cache.set(self.source, cache_key, payload, expires_at=datetime.now(UTC) + ttl)

        return payload

    async def _get_text(self, url: str, *, params: dict[str, Any] | None = None) -> str | None:
        async def _attempt() -> str | None:
            async with self._limiter:
                resp = await self._client.get(url, params=params)
            if resp.status_code == 404:
                return None
            if resp.status_code in _RETRYABLE_STATUSES:
                raise _RetryableHTTPError(f"{self.source} {resp.status_code}")
            resp.raise_for_status()
            return resp.text

        retrier = AsyncRetrying(
            stop=stop_after_attempt(4),
            wait=wait_exponential(multiplier=1.5, min=1.0, max=20.0),
            retry=retry_if_exception_type(
                (_RetryableHTTPError, httpx.TransportError, httpx.RemoteProtocolError)
            ),
            reraise=True,
        )

        try:
            async for attempt in retrier:
                with attempt:
                    return await _attempt()
        except Exception as e:
            log.warning("%s GET %s failed: %s", self.source, url, e)
            return None
        return None

    # --- Public API --------------------------------------------------------

    @abstractmethod
    async def resolve(self, reference: Reference) -> list[ResolvedWork]:
        """Return zero or more candidate ResolvedWork entries for the reference."""
        raise NotImplementedError
