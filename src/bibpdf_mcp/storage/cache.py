"""SQLite-backed JSON cache for API responses (and other small payloads).

Schema (single table):

    api_cache(
        id INTEGER PK,
        source TEXT NOT NULL,
        key TEXT NOT NULL,
        payload JSON NOT NULL,
        created_at DATETIME NOT NULL,
        expires_at DATETIME NULL,
        UNIQUE(source, key)
    )

Used as a read-through cache by all resolvers and by the Unpaywall lookup. The
implementation is synchronous (SQLAlchemy 2.0 sync core); resolvers call
`get`/`set` from async code, but each call is a sub-millisecond local hit.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from ..logging_config import get_logger

log = get_logger(__name__)


class _Base(DeclarativeBase):
    pass


class ApiCacheEntry(_Base):
    __tablename__ = "api_cache"
    __table_args__ = (UniqueConstraint("source", "key", name="uq_source_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    key: Mapped[str] = mapped_column(String(512), index=True)
    payload: Mapped[Any] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class JsonCache:
    """Thin synchronous DAO around `api_cache`."""

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path).expanduser().resolve()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{self._path}"
        self._engine = create_engine(url, future=True)
        _Base.metadata.create_all(self._engine)

    @property
    def path(self) -> Path:
        return self._path

    def get(self, source: str, key: str) -> Any | None:
        now = datetime.now(UTC)
        with Session(self._engine) as session:
            stmt = select(ApiCacheEntry).where(
                ApiCacheEntry.source == source,
                ApiCacheEntry.key == key,
            )
            row = session.execute(stmt).scalar_one_or_none()
            if row is None:
                return None
            if row.expires_at is not None and row.expires_at <= now:
                session.delete(row)
                session.commit()
                return None
            return row.payload

    def set(
        self,
        source: str,
        key: str,
        payload: Any,
        *,
        expires_at: datetime | None = None,
    ) -> None:
        now = datetime.now(UTC)
        with Session(self._engine) as session:
            stmt = select(ApiCacheEntry).where(
                ApiCacheEntry.source == source,
                ApiCacheEntry.key == key,
            )
            row = session.execute(stmt).scalar_one_or_none()
            if row is None:
                row = ApiCacheEntry(
                    source=source,
                    key=key,
                    payload=payload,
                    created_at=now,
                    expires_at=expires_at,
                )
                session.add(row)
            else:
                row.payload = payload
                row.created_at = now
                row.expires_at = expires_at
            session.commit()

    def purge_expired(self) -> int:
        now = datetime.now(UTC)
        with Session(self._engine) as session:
            stmt = select(ApiCacheEntry).where(
                ApiCacheEntry.expires_at.is_not(None),
                ApiCacheEntry.expires_at <= now,
            )
            rows = list(session.execute(stmt).scalars())
            for r in rows:
                session.delete(r)
            session.commit()
            return len(rows)
