"""
Pytest fixtures for Cognigate tests.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.db.database import Base
from app.core.policy_engine import policy_engine


@pytest.fixture(scope="session")
def anyio_backend():
    """Use asyncio backend for async tests."""
    return "asyncio"


@pytest_asyncio.fixture
async def async_client():
    """Create an async HTTP client for testing endpoints."""
    # Initialize policy engine for tests
    if not policy_engine.list_policies():
        policy_engine.load_default_policies()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def test_db():
    """Create a test database with in-memory SQLite."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def sample_plan():
    """Create a sample structured plan for testing."""
    return {
        "plan_id": "plan_test123",
        "intent_id": "int_test123",
        "entity_id": "agent_test",
        "primary_action": "read_file",
        "steps": [
            {"action": "read_file", "target": "/tmp/test.txt"}
        ],
        "tools_required": ["file_read"],
        "data_classifications": [],
        "risk_score": 0.2,
        "estimated_duration": "5m",
    }


@pytest.fixture
def high_risk_plan():
    """Create a high-risk plan for testing."""
    return {
        "plan_id": "plan_highrisk",
        "intent_id": "int_highrisk",
        "entity_id": "agent_test",
        "primary_action": "shell_exec",
        "steps": [
            {"action": "shell_exec", "command": "rm -rf /tmp/test"}
        ],
        "tools_required": ["shell", "file_delete"],
        "data_classifications": ["pii_email"],
        "risk_score": 0.9,
        "estimated_duration": "1m",
    }
