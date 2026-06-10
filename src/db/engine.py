"""
Async SQLAlchemy engine + session factory.

One connection pool, shared across the entire application.
Injected via FastAPI dependency — never instantiated directly in business logic.

Think of this as the plumbing behind the wall:
the rest of the codebase only touches the tap (repositories),
never the pipes (engine/session).
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def build_engine(dsn: str | None = None, testing: bool = False) -> AsyncEngine:
    """
    Build the async engine.
    - Production: uses a persistent pool (pool_size=10, max_overflow=20)
    - Testing: NullPool — no connection reuse, clean slate per test
    """
    url = dsn or os.environ["POSTGRES_DSN"]

    if testing:
        return create_async_engine(url, poolclass=NullPool, echo=False)

    return create_async_engine(
        url,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,        # evicts stale connections
        pool_recycle=3600,         # recycle after 1h
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    )


def init_db(dsn: str | None = None, testing: bool = False) -> None:
    """Call once at application startup (lifespan)."""
    global _engine, _session_factory
    _engine = build_engine(dsn, testing=testing)
    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,    # frozen dataclasses don't need lazy loading
        autoflush=False,
    )


async def close_db() -> None:
    """Call at application shutdown (lifespan)."""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """
    Async context manager that yields a session and handles
    commit/rollback automatically.

    Usage in repositories:
        async with get_session() as session:
            await session.execute(...)
    """
    if _session_factory is None:
        raise RuntimeError("Database not initialised — call init_db() first")

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session_dep() -> AsyncIterator[AsyncSession]:
    """
    FastAPI dependency version — yields a session per request.
    Injected via Depends(get_session_dep).
    """
    async with get_session() as session:
        yield session


async def check_postgres_health() -> bool:
    """Return True if the Postgres pool can execute a simple query."""
    if _engine is None:
        return False
    try:
        from sqlalchemy import text
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
