# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Tests for developer tools HTML pages and theme voting endpoints.
"""

import pytest
from unittest.mock import patch
from httpx import AsyncClient


@pytest.mark.anyio
class TestToolPages:
    """Test that all tool HTML pages render successfully."""

    async def test_calculator_page(self, async_client: AsyncClient):
        resp = await async_client.get("/tools/calculator")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Trust Tier Calculator" in resp.text

    async def test_errors_page(self, async_client: AsyncClient):
        resp = await async_client.get("/tools/errors")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Error Code Reference" in resp.text

    async def test_sdks_page(self, async_client: AsyncClient):
        resp = await async_client.get("/tools/sdks")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "SDK Quickstart" in resp.text

    async def test_playground_page(self, async_client: AsyncClient):
        resp = await async_client.get("/tools/playground")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "API Playground" in resp.text

    async def test_themes_page(self, async_client: AsyncClient):
        resp = await async_client.get("/tools/themes")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Theme Preview" in resp.text


@pytest.mark.anyio
class TestThemeVoting:
    """Test theme voting API endpoints."""

    async def test_cast_vote(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/v1/themes/vote",
            json={"theme_id": "midnight_cyan", "voter": "tester"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "voted"
        assert data["vote"]["theme_id"] == "midnight_cyan"
        assert data["vote"]["voter"] == "tester"
        assert "totals" in data

    async def test_cast_vote_unknown_theme(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/v1/themes/vote",
            json={"theme_id": "nonexistent_theme", "voter": "tester"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data
        assert "valid" in data

    async def test_get_votes(self, async_client: AsyncClient):
        resp = await async_client.get("/v1/themes/votes")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_votes" in data
        assert "themes" in data
        assert "leader" in data
