# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Integration tests for PROOF endpoints with database.

Tests the full proof lifecycle: create, query, verify, and stats.
Uses in-memory SQLite via dependency override.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.db.database import Base, get_session
from app.core.auth import verify_api_key
from app.core.policy_engine import policy_engine


async def _bypass_auth() -> str:
    return "test-key"


@pytest_asyncio.fixture
async def db_session():
    """Create an in-memory SQLite test database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def proof_client(db_session):
    """Client with overridden DB session and auth for proof endpoints."""
    if not policy_engine.list_policies():
        policy_engine.load_default_policies()

    async def override_session():
        yield db_session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[verify_api_key] = _bypass_auth
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(verify_api_key, None)


@pytest.mark.anyio
class TestProofLifecycle:
    """Test the full proof lifecycle via API."""

    async def _create_enforcement(self, client: AsyncClient) -> dict:
        """Helper: run enforce to get a verdict."""
        plan = {
            "plan_id": "plan_proof_test",
            "goal": "Read test file",
            "tools_required": ["file_read"],
            "data_classifications": [],
            "risk_score": 0.1,
            "reasoning_trace": "Simple read",
        }
        resp = await client.post("/v1/enforce", json={
            "entity_id": "agent_proof",
            "trust_level": 3,
            "trust_score": 500,
            "plan": plan,
        })
        assert resp.status_code == 200
        return resp.json()

    async def test_create_proof_record(self, proof_client):
        verdict = await self._create_enforcement(proof_client)
        resp = await proof_client.post("/v1/proof", json=verdict)
        assert resp.status_code == 200
        data = resp.json()
        assert "proof_id" in data
        assert "hash" in data
        assert data["chain_position"] == 0

    async def test_proof_chain_grows(self, proof_client):
        verdict = await self._create_enforcement(proof_client)
        r1 = await proof_client.post("/v1/proof", json=verdict)
        r2 = await proof_client.post("/v1/proof", json=verdict)
        assert r1.json()["chain_position"] == 0
        assert r2.json()["chain_position"] == 1
        # Second record should reference first record's hash
        assert r2.json()["previous_hash"] == r1.json()["hash"]

    async def test_get_proof_stats(self, proof_client):
        verdict = await self._create_enforcement(proof_client)
        await proof_client.post("/v1/proof", json=verdict)
        resp = await proof_client.get("/v1/proof/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_records"] >= 1
        assert data["chain_length"] >= 1

    async def test_get_proof_by_id(self, proof_client):
        verdict = await self._create_enforcement(proof_client)
        create_resp = await proof_client.post("/v1/proof", json=verdict)
        proof_id = create_resp.json()["proof_id"]
        resp = await proof_client.get(f"/v1/proof/{proof_id}")
        assert resp.status_code == 200
        assert resp.json()["proof_id"] == proof_id

    async def test_get_proof_not_found(self, proof_client):
        resp = await proof_client.get("/v1/proof/nonexistent")
        assert resp.status_code == 404

    async def test_verify_proof(self, proof_client):
        verdict = await self._create_enforcement(proof_client)
        create_resp = await proof_client.post("/v1/proof", json=verdict)
        proof_id = create_resp.json()["proof_id"]
        resp = await proof_client.get(f"/v1/proof/{proof_id}/verify")
        assert resp.status_code == 200
        data = resp.json()
        assert data["proof_id"] == proof_id
        assert data["valid"] is True
        assert data["chain_valid"] is True

    async def test_verify_proof_not_found(self, proof_client):
        resp = await proof_client.get("/v1/proof/nonexistent/verify")
        assert resp.status_code == 404

    async def test_query_proofs(self, proof_client):
        verdict = await self._create_enforcement(proof_client)
        await proof_client.post("/v1/proof", json=verdict)
        resp = await proof_client.post("/v1/proof/query", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
