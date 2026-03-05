"""
Database connection and session management for Cognigate.

Supports PostgreSQL (Neon) for production and SQLite for local development.
The driver is selected automatically based on DATABASE_URL:
  - postgresql+asyncpg://... → Neon PostgreSQL (production, persistent)
  - sqlite+aiosqlite://...   → SQLite (local dev)
"""

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# Global engine and session factory
_engine = None
_session_factory = None


def _resolve_database_url(url: str) -> str:
    """
    Resolve the database URL to the correct async driver format.

    Neon/Supabase often provide postgres:// or postgresql:// URLs.
    SQLAlchemy async requires postgresql+asyncpg:// for PostgreSQL.
    """
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


async def init_db() -> None:
    """
    Initialize the database connection and create tables.

    Call this during application startup.
    """
    global _engine, _session_factory

    settings = get_settings()
    db_url = _resolve_database_url(settings.database_url)
    is_postgres = "postgresql" in db_url or "asyncpg" in db_url

    # PostgreSQL (Neon serverless): use NullPool for serverless compatibility.
    # SQLite: default pool is fine for local dev.
    engine_kwargs = {
        "echo": settings.debug,
        "future": True,
    }
    if is_postgres:
        engine_kwargs["poolclass"] = NullPool

    _engine = create_async_engine(db_url, **engine_kwargs)

    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Schema management:
    # - Production (PostgreSQL): use Alembic migrations (alembic upgrade head)
    # - Development (SQLite): auto-create tables for convenience
    if is_postgres:
        logger.info(
            "database_initialized",
            extra={
                "database_type": "postgresql (Neon)",
                "schema_management": "alembic",
            },
        )
    else:
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info(
            "database_initialized",
            extra={
                "database_type": "sqlite",
                "schema_management": "create_all",
            },
        )


async def close_db() -> None:
    """
    Close the database connection.

    Call this during application shutdown.
    """
    global _engine, _session_factory

    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("database_closed")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get an async database session.

    Usage:
        async with get_session() as session:
            # use session

    Or as a FastAPI dependency:
        async def endpoint(session: AsyncSession = Depends(get_session)):
            # use session
    """
    if not _session_factory:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
