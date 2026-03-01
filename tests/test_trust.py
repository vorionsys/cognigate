"""
Tests for trust management - admission, scoring, signals, and revocation.

Tests observation tiers (BLACK_BOX, GRAY_BOX, WHITE_BOX), signal
processing, score clamping, ceiling enforcement, and revocation.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.routers.trust import _trust_state, _trust_signals


@pytest_asyncio.fixture
async def client():
    """Create test client and clear trust state between tests."""
    _trust_state.clear()
    _trust_signals.clear()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
class TestAdmission:
    """Test agent admission through Gate Trust."""

    async def test_admit_gray_box(self, client):
        resp = await client.post("/v1/trust/admit", json={
            "agentId": "agent_gray",
            "name": "Test Agent",
            "observationTier": "GRAY_BOX",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["admitted"]
        assert data["initialScore"] == 200
        assert data["initialTier"] == 1  # T1 Observed

    async def test_admit_black_box(self, client):
        resp = await client.post("/v1/trust/admit", json={
            "agentId": "agent_black",
            "name": "Black Box Agent",
            "observationTier": "BLACK_BOX",
        })
        data = resp.json()
        assert data["initialScore"] == 100
        assert data["initialTier"] == 0  # T0 Sandbox

    async def test_admit_white_box(self, client):
        resp = await client.post("/v1/trust/admit", json={
            "agentId": "agent_white",
            "name": "White Box Agent",
            "observationTier": "WHITE_BOX",
        })
        data = resp.json()
        assert data["initialScore"] == 350
        assert data["initialTier"] == 2  # T2 Provisional

    async def test_admit_with_capabilities(self, client):
        resp = await client.post("/v1/trust/admit", json={
            "agentId": "agent_cap",
            "name": "Cap Agent",
            "capabilities": ["read", "write", "compute"],
        })
        data = resp.json()
        assert data["capabilities"] == ["read", "write", "compute"]


@pytest.mark.asyncio
class TestTrustScoring:
    """Test trust signal processing and score changes."""

    async def _admit_agent(self, client, agent_id="agent_test"):
        await client.post("/v1/trust/admit", json={
            "agentId": agent_id,
            "name": "Test Agent",
            "observationTier": "GRAY_BOX",
        })

    async def test_success_signal_increases_score(self, client):
        await self._admit_agent(client)
        resp = await client.post("/v1/trust/agent_test/signal", json={
            "type": "success",
            "source": "test",
            "weight": 1.0,
        })
        data = resp.json()
        assert data["accepted"]
        assert data["scoreAfter"] > data["scoreBefore"]
        assert data["change"] > 0

    async def test_failure_signal_decreases_score(self, client):
        await self._admit_agent(client)
        resp = await client.post("/v1/trust/agent_test/signal", json={
            "type": "failure",
            "source": "test",
            "weight": 1.0,
        })
        data = resp.json()
        assert data["scoreAfter"] < data["scoreBefore"]
        assert data["change"] < 0

    async def test_violation_signal_severe_decrease(self, client):
        await self._admit_agent(client)
        resp = await client.post("/v1/trust/agent_test/signal", json={
            "type": "violation",
            "source": "test",
            "weight": 1.0,
        })
        data = resp.json()
        # Violation weight is -3.0, so delta = -3 * 1.0 * 50 = -150
        assert data["change"] == -150

    async def test_neutral_signal_no_change(self, client):
        await self._admit_agent(client)
        resp = await client.post("/v1/trust/agent_test/signal", json={
            "type": "neutral",
            "source": "test",
            "weight": 1.0,
        })
        data = resp.json()
        assert data["change"] == 0

    async def test_score_clamped_to_zero(self, client):
        await self._admit_agent(client)
        # Heavy violation should not go below 0
        for _ in range(5):
            await client.post("/v1/trust/agent_test/signal", json={
                "type": "violation",
                "source": "test",
                "weight": 1.0,
            })
        resp = await client.get("/v1/trust/agent_test")
        data = resp.json()
        assert data["score"] >= 0

    async def test_score_capped_by_observation_ceiling(self, client):
        """GRAY_BOX ceiling is T4 (max 799)."""
        await self._admit_agent(client)
        # Many successes to try to push past ceiling
        for _ in range(100):
            await client.post("/v1/trust/agent_test/signal", json={
                "type": "success",
                "source": "test",
                "weight": 1.0,
            })
        resp = await client.get("/v1/trust/agent_test")
        data = resp.json()
        assert data["score"] <= 799  # T4 Standard max

    async def test_black_box_ceiling_caps_at_t2(self, client):
        """BLACK_BOX ceiling is T2 (max 499)."""
        await client.post("/v1/trust/admit", json={
            "agentId": "agent_bb",
            "name": "Black Box",
            "observationTier": "BLACK_BOX",
        })
        for _ in range(100):
            await client.post("/v1/trust/agent_bb/signal", json={
                "type": "success",
                "source": "test",
                "weight": 1.0,
            })
        resp = await client.get("/v1/trust/agent_bb")
        data = resp.json()
        assert data["score"] <= 499  # T2 Provisional max

    async def test_white_box_ceiling_allows_full_range(self, client):
        """WHITE_BOX ceiling is T7 (max 1000)."""
        await client.post("/v1/trust/admit", json={
            "agentId": "agent_wb",
            "name": "White Box",
            "observationTier": "WHITE_BOX",
        })
        for _ in range(100):
            await client.post("/v1/trust/agent_wb/signal", json={
                "type": "success",
                "source": "test",
                "weight": 1.0,
            })
        resp = await client.get("/v1/trust/agent_wb")
        data = resp.json()
        # WHITE_BOX ceiling is T7=1000, so score only limited by max 1000
        assert data["score"] <= 1000

    async def test_signal_on_unknown_agent_404(self, client):
        resp = await client.post("/v1/trust/nonexistent/signal", json={
            "type": "success",
            "source": "test",
        })
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestTrustRetrieval:
    """Test trust score retrieval."""

    async def test_get_trust_for_admitted_agent(self, client):
        await client.post("/v1/trust/admit", json={
            "agentId": "agent_get",
            "name": "Get Test",
        })
        resp = await client.get("/v1/trust/agent_get")
        data = resp.json()
        assert data["agentId"] == "agent_get"
        assert data["score"] == 200
        assert data["tier"] == 1
        assert not data["isRevoked"]

    async def test_get_trust_unknown_agent(self, client):
        resp = await client.get("/v1/trust/unknown_agent")
        data = resp.json()
        assert data["score"] is None
        assert "not admitted" in data["message"].lower()


@pytest.mark.asyncio
class TestRevocation:
    """Test agent trust revocation."""

    async def test_revoke_sets_score_to_zero(self, client):
        await client.post("/v1/trust/admit", json={
            "agentId": "agent_revoke",
            "name": "Revoke Test",
        })
        resp = await client.post("/v1/trust/agent_revoke/revoke", json={
            "reason": "misbehavior",
        })
        data = resp.json()
        assert data["revoked"]

        # Verify score is 0 and revoked
        resp = await client.get("/v1/trust/agent_revoke")
        data = resp.json()
        assert data["score"] == 0
        assert data["isRevoked"]

    async def test_signal_on_revoked_agent_forbidden(self, client):
        await client.post("/v1/trust/admit", json={
            "agentId": "agent_r",
            "name": "R",
        })
        await client.post("/v1/trust/agent_r/revoke", json={"reason": "test"})
        resp = await client.post("/v1/trust/agent_r/signal", json={
            "type": "success",
            "source": "test",
        })
        assert resp.status_code == 403

    async def test_revoke_unknown_agent_404(self, client):
        resp = await client.post("/v1/trust/nonexistent/revoke", json={
            "reason": "test",
        })
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestTrustHistory:
    """Test trust signal history retrieval."""

    async def test_history_empty_initially(self, client):
        await client.post("/v1/trust/admit", json={
            "agentId": "agent_hist",
            "name": "History Test",
        })
        resp = await client.get("/v1/trust/agent_hist/history")
        data = resp.json()
        assert data["count"] == 0
        assert data["signals"] == []

    async def test_history_records_signals(self, client):
        await client.post("/v1/trust/admit", json={
            "agentId": "agent_hist2",
            "name": "History Test 2",
        })
        await client.post("/v1/trust/agent_hist2/signal", json={
            "type": "success", "source": "test",
        })
        await client.post("/v1/trust/agent_hist2/signal", json={
            "type": "failure", "source": "test",
        })
        resp = await client.get("/v1/trust/agent_hist2/history")
        data = resp.json()
        assert data["count"] == 2


@pytest.mark.asyncio
class TestTierDefinitions:
    """Test tier definitions endpoint."""

    async def test_get_tiers(self, client):
        resp = await client.get("/v1/trust/tiers")
        data = resp.json()
        assert "tiers" in data
        assert len(data["tiers"]) == 8  # T0-T7
