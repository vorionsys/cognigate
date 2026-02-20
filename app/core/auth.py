"""
Authentication for Cognigate Endpoints.

Provides API key authentication for admin and pipeline operations.
Production deployments should use strong, rotated API keys.
"""

import logging
import secrets
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import get_settings

logger = logging.getLogger(__name__)

# API Key header configuration — Admin endpoints
api_key_header = APIKeyHeader(
    name="X-Admin-Key",
    auto_error=False,
    description="Admin API key for protected endpoints"
)

# API Key header configuration — Pipeline endpoints
pipeline_api_key_header = APIKeyHeader(
    name="X-API-Key",
    auto_error=False,
    description="API key for pipeline endpoints"
)


class AuthError(HTTPException):
    """Authentication error with standard format."""

    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "ApiKey"},
        )


class ForbiddenError(HTTPException):
    """Authorization error - authenticated but not permitted."""

    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


async def verify_admin_key(
    api_key: Optional[str] = Security(api_key_header),
) -> str:
    """
    Verify the admin API key.

    This dependency should be used on all admin endpoints.
    Raises 401 if no key provided, 403 if key is invalid.

    Returns:
        The validated API key (for logging purposes)
    """
    settings = get_settings()

    if not api_key:
        logger.warning("admin_auth_missing_key")
        raise AuthError("Admin API key required")

    # Compare using constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(api_key, settings.admin_api_key):
        logger.warning("admin_auth_invalid_key")
        raise ForbiddenError("Invalid admin API key")

    return api_key


async def optional_admin_key(
    api_key: Optional[str] = Security(api_key_header),
) -> Optional[str]:
    """
    Optionally verify admin key.

    Returns the key if valid, None if not provided.
    Raises 403 if key is provided but invalid.

    Use this for endpoints that have different behavior for admins.
    """
    if not api_key:
        return None

    settings = get_settings()

    if not secrets.compare_digest(api_key, settings.admin_api_key):
        logger.warning("admin_auth_invalid_key")
        raise ForbiddenError("Invalid admin API key")

    return api_key


async def verify_api_key(
    api_key: Optional[str] = Security(pipeline_api_key_header),
) -> str:
    """
    Verify the pipeline API key (X-API-Key header).

    This dependency should be used on all pipeline endpoints
    (intent, enforce, proof, trust, auth_keys).
    Raises 401 if no key provided, 403 if key is invalid.

    Returns:
        The validated API key (for logging purposes)
    """
    settings = get_settings()

    if not api_key:
        logger.warning("pipeline_auth_missing_key")
        raise AuthError("API key required")

    # Compare using constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(api_key, settings.api_key):
        logger.warning("pipeline_auth_invalid_key")
        raise ForbiddenError("Invalid API key")

    return api_key


def generate_api_key(length: int = 32) -> str:
    """
    Generate a secure random API key.

    Use this to generate keys for production deployments.

    Args:
        length: Number of bytes (will be hex-encoded, so 2x characters)

    Returns:
        Hex-encoded random string
    """
    return secrets.token_hex(length)
