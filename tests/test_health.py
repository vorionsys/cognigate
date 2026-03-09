# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Tests for health check endpoints.

Tests /health (full status with subsystems), /health/live (liveness probe),
and /ready (readiness check).
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app


@pytest_asyncio.fixture
async def client():
    """Create test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
class TestHealthCheck:
    """Test /health endpoint with subsystem status."""

    async def test_health_returns_200(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200

    async def test_health_has_required_fields(self, client):
        data = (await client.get("/health")).json()
        assert "status" in data
        assert "service" in data
        assert "version" in data
        assert "timestamp" in data
        assert "uptime_seconds" in data
        assert "subsystems" in data

    async def test_health_service_name(self, client):
        data = (await client.get("/health")).json()
        assert data["service"] == "cognigate-engine"

    async def test_health_version_format(self, client):
        data = (await client.get("/health")).json()
        assert data["version"] == "0.1.0"

    async def test_health_uptime_is_positive(self, client):
        data = (await client.get("/health")).json()
        assert data["uptime_seconds"] > 0

    async def test_health_subsystems_are_list(self, client):
        data = (await client.get("/health")).json()
        assert isinstance(data["subsystems"], list)
        assert len(data["subsystems"]) == 3  # database, cache, signatures

    async def test_health_subsystem_names(self, client):
        data = (await client.get("/health")).json()
        names = {s["name"] for s in data["subsystems"]}
        assert names == {"database", "cache", "signatures"}

    async def test_health_subsystem_has_status(self, client):
        data = (await client.get("/health")).json()
        for sub in data["subsystems"]:
            assert "name" in sub
            assert "status" in sub
            assert sub["status"] in ("ok", "degraded", "unavailable")

    async def test_health_status_is_valid(self, client):
        data = (await client.get("/health")).json()
        assert data["status"] in ("healthy", "degraded", "unhealthy")


@pytest.mark.asyncio
class TestLivenessProbe:
    """Test /health/live endpoint."""

    async def test_live_returns_200(self, client):
        resp = await client.get("/health/live")
        assert resp.status_code == 200

    async def test_live_returns_alive(self, client):
        data = (await client.get("/health/live")).json()
        assert data["status"] == "alive"

    async def test_live_is_fast(self, client):
        """Liveness probe must not check subsystems -- should be near-instant."""
        import time
        start = time.monotonic()
        await client.get("/health/live")
        elapsed = time.monotonic() - start
        assert elapsed < 1.0  # Under 1 second


@pytest.mark.asyncio
class TestReadinessCheck:
    """Test /ready endpoint."""

    async def test_ready_returns_200(self, client):
        resp = await client.get("/ready")
        assert resp.status_code == 200

    async def test_ready_returns_ready(self, client):
        data = (await client.get("/ready")).json()
        assert data["status"] == "ready"


@pytest.mark.asyncio
class TestAppRoutes:
    """Test app-level routes defined in main.py."""

    async def test_root_landing_page(self, client):
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "Cognigate" in resp.text

    async def test_robots_txt(self, client):
        resp = await client.get("/robots.txt")
        assert resp.status_code == 200
        assert "User-agent" in resp.text

    async def test_sitemap_xml(self, client):
        resp = await client.get("/sitemap.xml")
        assert resp.status_code == 200
        assert "urlset" in resp.text

    async def test_openapi_json(self, client):
        resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert "openapi" in data
        assert "paths" in data

    async def test_status_page(self, client):
        resp = await client.get("/status")
        assert resp.status_code == 200
