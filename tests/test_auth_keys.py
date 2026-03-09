# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Tests for the API Key Management Router.

Covers key creation, listing, deletion, and hash security.
"""

import pytest
from httpx import AsyncClient

from app.routers.auth_keys import _hash_key, _api_keys


class TestHashKey:
    """Test the key hashing utility."""

    def test_deterministic(self):
        assert _hash_key("test") == _hash_key("test")

    def test_different_keys_different_hashes(self):
        assert _hash_key("key1") != _hash_key("key2")

    def test_sha256_format(self):
        h = _hash_key("test")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


@pytest.mark.anyio
class TestKeyLifecycle:
    """Test full API key lifecycle."""

    async def test_create_key(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/v1/auth/keys", json={"name": "test-key"}
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "keyId" in data
        assert data["name"] == "test-key"
        assert data["key"].startswith("cg_")
        assert "warning" in data

    async def test_list_keys(self, async_client: AsyncClient):
        # Create a key first
        await async_client.post("/v1/auth/keys", json={"name": "list-test"})

        resp = await async_client.get("/v1/auth/keys")
        assert resp.status_code == 200
        data = resp.json()
        assert "keys" in data
        assert data["count"] > 0
        # Raw key should NOT be in list response
        for key in data["keys"]:
            assert "key" not in key
            assert "hashedKey" not in key

    async def test_delete_key(self, async_client: AsyncClient):
        # Create
        resp = await async_client.post(
            "/v1/auth/keys", json={"name": "delete-me"}
        )
        key_id = resp.json()["keyId"]

        # Delete
        resp = await async_client.delete(f"/v1/auth/keys/{key_id}")
        assert resp.status_code == 204

    async def test_delete_nonexistent_key(self, async_client: AsyncClient):
        resp = await async_client.delete("/v1/auth/keys/nonexistent")
        assert resp.status_code == 404

    async def test_custom_scopes(self, async_client: AsyncClient):
        resp = await async_client.post(
            "/v1/auth/keys",
            json={"name": "readonly", "scopes": ["read"]},
        )
        assert resp.json()["scopes"] == ["read"]
