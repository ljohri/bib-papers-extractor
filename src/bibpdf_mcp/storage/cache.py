"""Tiny SQLite-backed JSON cache for API responses.

Phase 1 stub: schema declared, real DAO methods land in Phase 5.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ApiCacheEntry(Base):
    __tablename__ = "api_cache"
    __table_args__ = (UniqueConstraint("source", "key", name="uq_source_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    key: Mapped[str] = mapped_column(String(512), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[Any] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)
