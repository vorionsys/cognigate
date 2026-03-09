# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Tests for agent management - CRUD operations and Gate Trust admission.

Tests registration, listing, retrieval, update, deletion (revocation),
observation tiers, and duplicate agent handling.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.routers.agents import _agents


@pytest_asyncio.fixture
async def client():
    """Create test client and clear agent state between tests."""
    _agents.clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
class TestAgentRegistration:
    """Test agent registration through Gate Trust."""

    async def test_register_agent(self, client):
        resp = await client.post("/v1/agents", json={
            "name": "Test Agent",
            "capabilities": ["read", "write"],
            "observationTier": "GRAY_BOX",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "agentId" in data
        assert data["name"] == "Test Agent"
        assert data["trustScore"] == 200
        assert data["trustTier"] == 1

    async def test_register_with_custom_id(self, client):
        resp = await client.post("/v1/agents", json={
            "agentId": "custom_agent",
            "name": "Custom Agent",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["agentId"] == "custom_agent"

    async def test_register_black_box_agent(self, client):
        resp = await client.post("/v1/agents", json={
            "name": "Black Box Agent",
            "observationTier": "BLACK_BOX",
        })
        data = resp.json()
        assert data["trustScore"] == 100
        assert data["trustTier"] == 0  # T0 Sandbox

    async def test_register_white_box_agent(self, client):
        resp = await client.post("/v1/agents", json={
            "name": "White Box Agent",
            "observationTier": "WHITE_BOX",
        })
        data = resp.json()
        assert data["trustScore"] == 350
        assert data["trustTier"] == 2  # T2 Provisional

    async def test_duplicate_agent_rejected(self, client):
        await client.post("/v1/agents", json={
            "agentId": "dup_agent",
            "name": "First",
        })
        resp = await client.post("/v1/agents", json={
            "agentId": "dup_agent",
            "name": "Second",
        })
        assert resp.status_code == 409

    async def test_expires_at_set(self, client):
        resp = await client.post("/v1/agents", json={
            "name": "Expiring Agent",
        })
        data = resp.json()
        assert data["expiresAt"] is not None


@pytest.mark.asyncio
class TestAgentListing:
    """Test listing agents."""

    async def test_list_empty(self, client):
        resp = await client.get("/v1/agents")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_agents(self, client):
        await client.post("/v1/agents", json={"name": "A1"})
        await client.post("/v1/agents", json={"name": "A2"})
        resp = await client.get("/v1/agents")
        data = resp.json()
        assert len(data) == 2

    async def test_list_excludes_revoked(self, client):
        resp = await client.post("/v1/agents", json={
            "agentId": "to_revoke",
            "name": "Revoke Me",
        })
        await client.delete("/v1/agents/to_revoke")
        resp = await client.get("/v1/agents")
        assert len(resp.json()) == 0

    async def test_list_with_limit(self, client):
        for i in range(5):
            await client.post("/v1/agents", json={"name": f"A{i}"})
        resp = await client.get("/v1/agents?limit=2")
        assert len(resp.json()) == 2


@pytest.mark.asyncio
class TestAgentRetrieval:
    """Test getting agent details."""

    async def test_get_agent_details(self, client):
        await client.post("/v1/agents", json={
            "agentId": "detail_agent",
            "name": "Detail Agent",
            "capabilities": ["compute"],
            "observationTier": "WHITE_BOX",
        })
        resp = await client.get("/v1/agents/detail_agent")
        data = resp.json()
        assert data["agentId"] == "detail_agent"
        assert data["name"] == "Detail Agent"
        assert data["capabilities"] == ["compute"]
        assert data["observationTier"] == "WHITE_BOX"
        assert data["trustScore"] == 350

    async def test_get_agent_not_found(self, client):
        resp = await client.get("/v1/agents/nonexistent")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestAgentUpdate:
    """Test updating agent properties."""

    async def test_update_name(self, client):
        await client.post("/v1/agents", json={
            "agentId": "upd_agent",
            "name": "Original",
        })
        resp = await client.patch("/v1/agents/upd_agent", json={
            "name": "Updated Name",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Name"

    async def test_update_capabilities(self, client):
        await client.post("/v1/agents", json={
            "agentId": "cap_agent",
            "name": "Cap Agent",
            "capabilities": ["read"],
        })
        resp = await client.patch("/v1/agents/cap_agent", json={
            "capabilities": ["read", "write", "admin"],
        })
        data = resp.json()
        assert data["capabilities"] == ["read", "write", "admin"]

    async def test_update_nonexistent_agent_404(self, client):
        resp = await client.patch("/v1/agents/ghost", json={"name": "Ghost"})
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestAgentDeletion:
    """Test agent revocation (soft delete)."""

    async def test_delete_agent(self, client):
        await client.post("/v1/agents", json={
            "agentId": "del_agent",
            "name": "Delete Me",
        })
        resp = await client.delete("/v1/agents/del_agent")
        assert resp.status_code == 204

    async def test_deleted_agent_excluded_from_list(self, client):
        await client.post("/v1/agents", json={
            "agentId": "soft_del",
            "name": "Soft Delete",
        })
        await client.delete("/v1/agents/soft_del")
        agents = (await client.get("/v1/agents")).json()
        assert not any(a["agentId"] == "soft_del" for a in agents)

    async def test_delete_nonexistent_agent_404(self, client):
        resp = await client.delete("/v1/agents/nonexistent")
        assert resp.status_code == 404

    async def test_can_re_register_revoked_agent(self, client):
        """Revoked agents can be re-registered."""
        await client.post("/v1/agents", json={
            "agentId": "reuse",
            "name": "First Life",
        })
        await client.delete("/v1/agents/reuse")
        resp = await client.post("/v1/agents", json={
            "agentId": "reuse",
            "name": "Second Life",
        })
        assert resp.status_code == 201
