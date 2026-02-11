"""
Tests for the Admin API Router.

Covers circuit breaker management, entity control, velocity
management, and system status endpoints.
"""

import pytest
from httpx import AsyncClient

ADMIN_KEY = "CHANGE_ME_IN_PRODUCTION"
ADMIN_HEADERS = {"X-Admin-Key": ADMIN_KEY}


@pytest.mark.anyio
class TestAdminAuth:
    """Test admin authentication."""

    async def test_missing_admin_key(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/admin/circuit")
        assert resp.status_code == 401

    async def test_invalid_admin_key(self, async_client: AsyncClient):
        resp = await async_client.get(
            "/v1/admin/circuit", headers={"X-Admin-Key": "wrong-key"}
        )
        assert resp.status_code == 403

    async def test_valid_admin_key(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/admin/circuit", headers=ADMIN_HEADERS)
        assert resp.status_code == 200


@pytest.mark.anyio
class TestCircuitBreaker:
    """Test circuit breaker admin endpoints."""

    async def test_get_circuit_status(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/admin/circuit", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert "state" in data

    async def test_get_circuit_history(self, async_client: AsyncClient):
        resp = await async_client.get(
            "/v1/admin/circuit/history", headers=ADMIN_HEADERS
        )
        assert resp.status_code == 200
        assert "trips" in resp.json()

    async def test_manual_halt_and_reset(self, async_client: AsyncClient):
        # Halt
        resp = await async_client.post(
            "/v1/admin/circuit/halt",
            json={"reason": "test halt"},
            headers=ADMIN_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "halted"

        # Reset
        resp = await async_client.post(
            "/v1/admin/circuit/reset", headers=ADMIN_HEADERS
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "reset"


@pytest.mark.anyio
class TestEntityControl:
    """Test entity halt/unhalt endpoints."""

    async def test_halt_and_unhalt_entity(self, async_client: AsyncClient):
        # Halt
        resp = await async_client.post(
            "/v1/admin/entity/halt",
            json={"entity_id": "agent_bad", "reason": "testing"},
            headers=ADMIN_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "halted"
        assert resp.json()["entity_id"] == "agent_bad"

        # Unhalt
        resp = await async_client.post(
            "/v1/admin/entity/unhalt",
            json={"entity_id": "agent_bad"},
            headers=ADMIN_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "unhalted"

    async def test_cascade_halt(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/v1/admin/entity/cascade-halt",
            json={"parent_id": "parent_agent", "reason": "cascade test"},
            headers=ADMIN_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cascade_halted"


@pytest.mark.anyio
class TestVelocityAdmin:
    """Test velocity admin endpoints."""

    async def test_get_all_velocity_stats(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/admin/velocity", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert "entities" in resp.json()

    async def test_get_entity_velocity_not_found(self, async_client: AsyncClient):
        resp = await async_client.get(
            "/v1/admin/velocity/nonexistent", headers=ADMIN_HEADERS
        )
        assert resp.status_code == 404

    async def test_throttle_and_unthrottle(self, async_client: AsyncClient):
        # Throttle
        resp = await async_client.post(
            "/v1/admin/velocity/throttle",
            json={"entity_id": "agent_fast", "duration_seconds": 60},
            headers=ADMIN_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "throttled"

        # Unthrottle
        resp = await async_client.post(
            "/v1/admin/velocity/unthrottle",
            json={"entity_id": "agent_fast"},
            headers=ADMIN_HEADERS,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "unthrottled"


@pytest.mark.anyio
class TestSystemStatus:
    """Test system status endpoint."""

    async def test_system_status_healthy(self, async_client: AsyncClient):
        # Ensure circuit is reset and no entities are halted from prior tests
        await async_client.post("/v1/admin/circuit/reset", headers=ADMIN_HEADERS)
        for eid in ["agent_bad", "bad_agent", "parent_agent"]:
            await async_client.post(
                "/v1/admin/entity/unhalt",
                json={"entity_id": eid},
                headers=ADMIN_HEADERS,
            )

        resp = await async_client.get("/v1/admin/status", headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        data = resp.json()
        assert data["health"] == "healthy"
        assert "circuit_breaker" in data
        assert "velocity" in data
        assert "security_layers" in data

    async def test_system_status_critical_when_halted(self, async_client: AsyncClient):
        # Halt circuit
        await async_client.post(
            "/v1/admin/circuit/halt",
            json={"reason": "test"},
            headers=ADMIN_HEADERS,
        )

        resp = await async_client.get("/v1/admin/status", headers=ADMIN_HEADERS)
        data = resp.json()
        assert data["health"] == "critical"

        # Clean up
        await async_client.post("/v1/admin/circuit/reset", headers=ADMIN_HEADERS)

    async def test_system_status_warning_with_halted_entities(
        self, async_client: AsyncClient
    ):
        # Halt an entity
        await async_client.post(
            "/v1/admin/entity/halt",
            json={"entity_id": "bad_agent", "reason": "test"},
            headers=ADMIN_HEADERS,
        )

        resp = await async_client.get("/v1/admin/status", headers=ADMIN_HEADERS)
        data = resp.json()
        assert data["health"] == "warning"

        # Clean up
        await async_client.post(
            "/v1/admin/entity/unhalt",
            json={"entity_id": "bad_agent"},
            headers=ADMIN_HEADERS,
        )
