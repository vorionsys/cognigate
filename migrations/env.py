"""
Alembic migration environment for Cognigate.

Supports both sync (offline) and async (online) migrations.
Database URL is resolved from the same config as the application.
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.db.database import Base

# Import all models so Alembic can detect them
from app.db.models import (  # noqa: F401
    ChainStateDB,
    IntentRecordDB,
    ProofRecordDB,
    TrustSignalDB,
    TrustStateDB,
)
from app.db.evidence_models import (  # noqa: F401
    ComplianceSnapshotDB,
    ControlEvidenceDB,
    ControlHealthDB,
)

# Alembic Config object
config = context.config

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate
target_metadata = Base.metadata


def _resolve_database_url() -> str:
    """
    Resolve the database URL for migrations.

    Priority:
    1. DATABASE_URL environment variable
    2. Default local SQLite
    """
    url = os.environ.get("DATABASE_URL", "sqlite:///./cognigate.db")

    # Convert async drivers to sync equivalents for Alembic
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    elif url.startswith("sqlite+aiosqlite://"):
        url = url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    return url


def _resolve_async_database_url() -> str:
    """Resolve database URL with async drivers for online migrations."""
    url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///./cognigate.db")

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif url.startswith("sqlite://") and "+aiosqlite" not in url:
        url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)

    return url


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Generates SQL scripts without connecting to the database.
    """
    url = _resolve_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with an active connection."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in async mode for PostgreSQL."""
    url = _resolve_async_database_url()

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    Connects to the database and applies migrations directly.
    Uses async engine for PostgreSQL compatibility.
    """
    url = _resolve_database_url()

    # For SQLite, use sync engine directly
    if "sqlite" in url:
        from sqlalchemy import create_engine

        connectable = create_engine(url, poolclass=pool.NullPool)
        with connectable.connect() as connection:
            do_run_migrations(connection)
        connectable.dispose()
    else:
        # PostgreSQL: use async engine
        asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
