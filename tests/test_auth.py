# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Tests for the Auth module.

Covers API key verification, error classes, and key generation.
"""

import pytest
from unittest.mock import patch, AsyncMock

from app.core.auth import (
    verify_admin_key,
    optional_admin_key,
    generate_api_key,
    AuthError,
    ForbiddenError,
)


class TestAuthErrors:
    """Test custom auth exception classes."""

    def test_auth_error_status_code(self):
        err = AuthError("test")
        assert err.status_code == 401
        assert err.detail == "test"
        assert err.headers == {"WWW-Authenticate": "ApiKey"}

    def test_forbidden_error_status_code(self):
        err = ForbiddenError("test")
        assert err.status_code == 403
        assert err.detail == "test"


@pytest.mark.anyio
class TestVerifyAdminKey:
    """Test admin key verification."""

    async def test_missing_key_raises_401(self):
        with pytest.raises(AuthError):
            await verify_admin_key(api_key=None)

    async def test_invalid_key_raises_403(self):
        with pytest.raises(ForbiddenError):
            await verify_admin_key(api_key="wrong-key")

    async def test_valid_key_returns_key(self):
        result = await verify_admin_key(api_key="CHANGE_ME_IN_PRODUCTION")
        assert result == "CHANGE_ME_IN_PRODUCTION"


@pytest.mark.anyio
class TestOptionalAdminKey:
    """Test optional admin key verification."""

    async def test_no_key_returns_none(self):
        result = await optional_admin_key(api_key=None)
        assert result is None

    async def test_valid_key_returns_key(self):
        result = await optional_admin_key(api_key="CHANGE_ME_IN_PRODUCTION")
        assert result == "CHANGE_ME_IN_PRODUCTION"

    async def test_invalid_key_raises_403(self):
        with pytest.raises(ForbiddenError):
            await optional_admin_key(api_key="wrong-key")


class TestGenerateApiKey:
    """Test API key generation."""

    def test_default_length(self):
        key = generate_api_key()
        assert len(key) == 64  # 32 bytes = 64 hex chars

    def test_custom_length(self):
        key = generate_api_key(length=16)
        assert len(key) == 32  # 16 bytes = 32 hex chars

    def test_unique_keys(self):
        key1 = generate_api_key()
        key2 = generate_api_key()
        assert key1 != key2
