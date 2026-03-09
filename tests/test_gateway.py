# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Tests for the Gateway Router.

Covers gateway status endpoint and proxy routing validation.
"""

import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient

from app.routers.gateway import GATEWAY_DOMAINS


class TestGatewayDomains:
    """Test gateway domain configuration."""

    def test_gateway_domains_exist(self):
        assert len(GATEWAY_DOMAINS) == 8
        assert "compliance" in GATEWAY_DOMAINS
        assert "council" in GATEWAY_DOMAINS
        assert "dashboard" in GATEWAY_DOMAINS


@pytest.mark.anyio
class TestGatewayStatus:
    """Test gateway status endpoint."""

    async def test_gateway_status(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/gateway/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["gateway"] == "operational"
        assert "circuitBreaker" in data
        assert data["domains"] == GATEWAY_DOMAINS


@pytest.mark.anyio
class TestGatewayProxy:
    """Test gateway proxy routing."""

    async def test_unknown_domain_returns_404(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/gateway/fake-domain/test")
        assert resp.status_code == 404
        data = resp.json()
        assert "availableDomains" in data

    @patch("app.routers.gateway.forward_request", new_callable=AsyncMock)
    async def test_valid_domain_forwards_request(
        self, mock_forward, async_client: AsyncClient
    ):
        mock_forward.return_value = {
            "status": 200,
            "data": {"message": "ok"},
        }

        resp = await async_client.get("/v1/gateway/compliance/test")
        assert resp.status_code == 200
        mock_forward.assert_called_once()

        # Verify upstream path construction
        call_kwargs = mock_forward.call_args
        assert call_kwargs.kwargs["path"] == "/v1/compliance/test"
        assert call_kwargs.kwargs["method"] == "GET"

    @patch("app.routers.gateway.forward_request", new_callable=AsyncMock)
    async def test_post_forwards_body(
        self, mock_forward, async_client: AsyncClient
    ):
        mock_forward.return_value = {
            "status": 201,
            "data": {"id": "123"},
        }

        resp = await async_client.post(
            "/v1/gateway/council/votes",
            json={"vote": "approve"},
        )
        assert resp.status_code == 201

    @patch("app.routers.gateway.forward_request", new_callable=AsyncMock)
    async def test_api_key_forwarded(
        self, mock_forward, async_client: AsyncClient
    ):
        mock_forward.return_value = {
            "status": 200,
            "data": {},
        }

        await async_client.get(
            "/v1/gateway/dashboard/stats",
            headers={"Authorization": "Bearer test-key"},
        )

        call_kwargs = mock_forward.call_args
        assert call_kwargs.kwargs["api_key"] == "test-key"
