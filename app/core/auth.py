"""
Authentication for Cognigate Endpoints.

Provides API key authentication for admin and pipeline operations.
Production deployments should use strong, rotated API keys.
"""

import logging
import secrets
import time
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


# TOTP MFA header
totp_header = APIKeyHeader(
    name="X-TOTP-Code",
    auto_error=False,
    description="TOTP one-time code for MFA-protected admin endpoints"
)


def verify_totp(code: str) -> bool:
    """
    Verify a TOTP code against the configured secret.

    Uses a constant-time comparison and accepts codes within
    the configured window (default ±1 time step = ±30 seconds).

    Returns True if valid, False otherwise.
    """
    settings = get_settings()

    if not settings.mfa_totp_secret:
        logger.warning("mfa_totp_no_secret_configured")
        return False

    try:
        import pyotp
        totp = pyotp.TOTP(settings.mfa_totp_secret)
        return totp.verify(code, valid_window=settings.mfa_totp_window)
    except ImportError:
        logger.error("mfa_totp_pyotp_not_installed")
        return False
    except Exception as e:
        logger.error("mfa_totp_verification_error", error=str(e))
        return False


async def verify_admin_key_with_mfa(
    api_key: Optional[str] = Security(api_key_header),
    totp_code: Optional[str] = Security(totp_header),
) -> str:
    """
    Verify admin API key with optional TOTP MFA.

    When MFA is enabled (settings.mfa_enabled = True):
    - Both X-Admin-Key and X-TOTP-Code headers are required
    - The TOTP code must be valid

    When MFA is disabled:
    - Falls back to admin key only (existing behavior)

    Returns the validated API key.
    """
    settings = get_settings()

    # First factor: API key
    if not api_key:
        logger.warning("admin_auth_missing_key")
        raise AuthError("Admin API key required")

    if not secrets.compare_digest(api_key, settings.admin_api_key):
        logger.warning("admin_auth_invalid_key")
        raise ForbiddenError("Invalid admin API key")

    # Second factor: TOTP (if MFA enabled)
    if settings.mfa_enabled:
        if not totp_code:
            logger.warning("admin_auth_missing_totp")
            raise AuthError("TOTP code required (MFA is enabled). Provide X-TOTP-Code header.")

        if not verify_totp(totp_code):
            logger.warning("admin_auth_invalid_totp")
            raise ForbiddenError("Invalid or expired TOTP code")

        logger.info("admin_auth_mfa_success")

    return api_key
