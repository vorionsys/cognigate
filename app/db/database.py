"""
Database connection and session management for Cognigate.

Uses SQLAlchemy async with SQLite by default (configurable).
"""

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# Global engine and session factory
_engine = None
_session_factory = None


async def init_db() -> None:
    """
    Initialize the database connection and create tables.

    Call this during application startup.
    """
    global _engine, _session_factory

    settings = get_settings()

    _engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        future=True,
    )

    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Create tables
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info(
        "database_initialized",
        extra={"database_url": settings.database_url}
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
