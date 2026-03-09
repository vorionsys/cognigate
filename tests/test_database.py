# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Tests for database initialization, session management, and URL resolution.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import _resolve_database_url, init_db, close_db, get_session, Base


class TestResolveDatabaseUrl:
    """Test database URL resolution for async drivers."""

    def test_postgres_to_asyncpg(self):
        url = "postgres://user:pass@host/db"
        assert _resolve_database_url(url) == "postgresql+asyncpg://user:pass@host/db"

    def test_postgresql_to_asyncpg(self):
        url = "postgresql://user:pass@host/db"
        assert _resolve_database_url(url) == "postgresql+asyncpg://user:pass@host/db"

    def test_sqlite_unchanged(self):
        url = "sqlite+aiosqlite:///test.db"
        assert _resolve_database_url(url) == url

    def test_already_asyncpg_unchanged(self):
        url = "postgresql+asyncpg://user:pass@host/db"
        assert _resolve_database_url(url) == url


@pytest.mark.anyio
class TestInitAndCloseDb:
    """Test DB lifecycle."""

    async def test_init_creates_engine(self):
        from app.db import database
        old_engine = database._engine
        old_factory = database._session_factory
        try:
            await init_db()
            assert database._engine is not None
            assert database._session_factory is not None
        finally:
            await close_db()
            database._engine = old_engine
            database._session_factory = old_factory

    async def test_close_disposes_engine(self):
        from app.db import database
        old_engine = database._engine
        old_factory = database._session_factory
        try:
            await init_db()
            await close_db()
            assert database._engine is None
            assert database._session_factory is None
        finally:
            database._engine = old_engine
            database._session_factory = old_factory

    async def test_get_session_without_init_raises(self):
        from app.db import database
        old_factory = database._session_factory
        try:
            database._session_factory = None
            gen = get_session()
            with pytest.raises(RuntimeError, match="not initialized"):
                await gen.__anext__()
        finally:
            database._session_factory = old_factory

    async def test_get_session_yields_session(self):
        from app.db import database
        old_engine = database._engine
        old_factory = database._session_factory
        try:
            await init_db()
            gen = get_session()
            session = await gen.__anext__()
            assert isinstance(session, AsyncSession)
            # Clean up
            try:
                await gen.__anext__()
            except StopAsyncIteration:
                pass
        finally:
            await close_db()
            database._engine = old_engine
            database._session_factory = old_factory
