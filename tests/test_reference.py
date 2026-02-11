"""
Tests for the Reference Data API Router.

Covers all /v1/reference/* endpoints for tiers, capabilities,
errors, rate limits, versions, products, and domains.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
class TestTiers:
    """Test tier reference endpoints."""

    async def test_list_tiers(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/tiers")
        assert resp.status_code == 200
        data = resp.json()
        assert "tiers" in data
        assert data["count"] == 8
        assert data["tiers"][0]["code"] == "T0"
        assert data["tiers"][7]["code"] == "T7"

    async def test_get_tier_by_number(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/tiers/3")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == 3
        assert data["code"] == "T3"
        assert "name" in data

    async def test_get_tier_by_code(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/tiers/T5")
        assert resp.status_code == 200
        assert resp.json()["tier"] == 5

    async def test_get_tier_by_name(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/tiers/TRUSTED")
        assert resp.status_code == 200
        assert resp.json()["tier"] == 5

    async def test_get_tier_not_found(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/tiers/T99")
        assert resp.status_code == 404

    async def test_lookup_tier_by_score(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/tiers/lookup/650")
        assert resp.status_code == 200
        data = resp.json()
        assert data["score"] == 650
        assert data["tier"] == 4

    async def test_lookup_tier_by_score_zero(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/tiers/lookup/0")
        assert resp.status_code == 200
        assert resp.json()["tier"] == 0

    async def test_lookup_tier_by_score_max(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/tiers/lookup/1000")
        assert resp.status_code == 200
        assert resp.json()["tier"] == 7

    async def test_lookup_tier_invalid_score(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/tiers/lookup/-1")
        assert resp.status_code == 400

    async def test_lookup_tier_score_too_high(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/tiers/lookup/1001")
        assert resp.status_code == 400


@pytest.mark.anyio
class TestCapabilities:
    """Test capability reference endpoints."""

    async def test_list_capabilities(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert "capabilities" in data
        assert data["count"] > 0

    async def test_list_capabilities_filter_tier(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/capabilities?tier=0")
        assert resp.status_code == 200
        data = resp.json()
        # T0 should have fewer capabilities than full list
        all_resp = await async_client.get("/v1/reference/capabilities")
        assert data["count"] <= all_resp.json()["count"]

    async def test_list_capabilities_filter_category(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/capabilities?category=data_access")
        assert resp.status_code == 200
        for cap in resp.json()["capabilities"]:
            assert cap["category"] == "data_access"

    async def test_get_capability_not_found(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/capabilities/NONEXISTENT")
        assert resp.status_code == 404


@pytest.mark.anyio
class TestErrors:
    """Test error code reference endpoints."""

    async def test_list_errors(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/errors")
        assert resp.status_code == 200
        data = resp.json()
        assert "errors" in data
        assert data["count"] > 0

    async def test_list_errors_filter_category(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/errors?category=auth")
        assert resp.status_code == 200
        for err in resp.json()["errors"]:
            assert err["category"] == "auth"

    async def test_list_errors_filter_retryable(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/errors?retryable=true")
        assert resp.status_code == 200
        for err in resp.json()["errors"]:
            assert err["retryable"] is True

    async def test_get_error_not_found(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/errors/E9999")
        assert resp.status_code == 404


@pytest.mark.anyio
class TestRateLimits:
    """Test rate limit reference endpoints."""

    async def test_list_rate_limits(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/rate-limits")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 8
        for item in data["rateLimits"]:
            assert "rateLimits" in item
            assert "quotas" in item

    async def test_get_rate_limits_for_tier(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/rate-limits/T4")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == 4
        assert "rateLimits" in data

    async def test_get_rate_limits_invalid_tier(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/rate-limits/T99")
        assert resp.status_code == 404


@pytest.mark.anyio
class TestVersions:
    """Test version reference endpoints."""

    async def test_list_versions(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert "versions" in data
        assert "currentVersions" in data


@pytest.mark.anyio
class TestProducts:
    """Test product catalog endpoints."""

    async def test_list_all_products(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/products")
        assert resp.status_code == 200
        assert "products" in resp.json()

    async def test_list_products_by_org(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/products?organization=vorion")
        assert resp.status_code == 200
        data = resp.json()
        assert data["organization"] == "vorion"

    async def test_list_products_invalid_org(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/products?organization=fake")
        assert resp.status_code == 404


@pytest.mark.anyio
class TestDomains:
    """Test domain registry endpoints."""

    async def test_list_domains(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/reference/domains")
        assert resp.status_code == 200
        assert "domains" in resp.json()
