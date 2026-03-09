# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Authentication for Cognigate Endpoints.

Provides API key authentication for admin and pipeline operations.
Production deployments should use strong, rotated API keys.

IA-5(1) Compliance: API key strength validation ensures minimum
authenticator complexity (128-bit entropy, mixed character classes,
no weak/default patterns). See validate_api_key_strength().
"""

import logging
import re
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


# ---------------------------------------------------------------------------
# IA-5(1) — Authenticator Strength Validation [IMPLEMENTED]
# ---------------------------------------------------------------------------

# Known weak/default values that MUST be rejected regardless of length.
_KNOWN_WEAK_VALUES: set[str] = {
    "CHANGE_ME_IN_PRODUCTION",
    "changeme",
    "secret",
    "password",
    "admin",
    "test",
    "default",
    "0" * 32,
    "0" * 64,
    "1234567890abcdef" * 2,
    "1234567890abcdef" * 4,
    "abcdef1234567890" * 2,
    "abcdef1234567890" * 4,
}

# Patterns indicating insufficient entropy (sequential, repeated, etc.)
_WEAK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^(.)\1+$"),                    # All same character (e.g., "aaa...a")
    re.compile(r"^(..)\1+$"),                   # Two-char repeat (e.g., "abababab")
    re.compile(r"^0123456789abcdef", re.I),     # Sequential hex ascending
    re.compile(r"^fedcba9876543210", re.I),     # Sequential hex descending
    re.compile(r"^(0+|f+)$", re.I),             # All zeros or all f's
    re.compile(r"^(.{1,4})\1{7,}$"),            # Short pattern repeated 8+ times
]

# Minimum key length: 32 characters = 128-bit entropy minimum for hex keys.
_MIN_KEY_LENGTH: int = 32


def validate_api_key_strength(key: str) -> tuple[bool, str]:
    """
    Validate that an API key meets minimum authenticator complexity requirements.

    Enforces IA-5(1) authenticator management controls adapted for API keys:
    - Minimum length: 32 characters (128-bit entropy minimum)
    - Must not be a known weak/default value
    - Must not match common weak patterns (all zeros, sequential, repeated)
    - Must contain mixed character classes (hex keys naturally satisfy this
      with digits + letters when generated via secrets.token_hex)

    Args:
        key: The API key string to validate.

    Returns:
        Tuple of (is_valid, reason). If is_valid is True, reason is empty.
        If is_valid is False, reason describes the specific weakness.
    """
    if not key:
        return False, "API key is empty"

    # --- Length check (128-bit minimum entropy) ---
    if len(key) < _MIN_KEY_LENGTH:
        return False, (
            f"API key too short: {len(key)} characters "
            f"(minimum {_MIN_KEY_LENGTH} for 128-bit entropy)"
        )

    # --- Known weak/default values ---
    if key in _KNOWN_WEAK_VALUES or key.lower() in _KNOWN_WEAK_VALUES:
        return False, "API key matches a known weak or default value"

    # --- Weak pattern detection ---
    for pattern in _WEAK_PATTERNS:
        if pattern.match(key):
            return False, (
                f"API key matches a weak pattern: {pattern.pattern}"
            )

    # --- Character class diversity ---
    # For hex-encoded keys, we expect both digits and letters.
    # For prefixed keys (e.g., "cg_..."), the prefix satisfies diversity.
    has_digit = bool(re.search(r"\d", key))
    has_alpha = bool(re.search(r"[a-zA-Z]", key))

    if not (has_digit and has_alpha):
        return False, (
            "API key lacks character class diversity "
            "(must contain both letters and digits)"
        )

    logger.debug("api_key_strength_validated", key_length=len(key))
    return True, ""


def generate_api_key(length: int = 32, max_attempts: int = 5) -> str:
    """
    Generate a secure random API key that passes strength validation.

    Uses secrets.token_hex() for cryptographic randomness. Validates the
    generated key against IA-5(1) strength requirements and regenerates
    if necessary (extremely unlikely with proper CSPRNG, but provides
    defense-in-depth).

    Args:
        length: Number of bytes (will be hex-encoded, so 2x characters).
                Must be >= 16 (128-bit minimum entropy).
        max_attempts: Maximum regeneration attempts before raising an error.

    Returns:
        Hex-encoded random string that passes strength validation.

    Raises:
        ValueError: If length is below the minimum (16 bytes / 32 hex chars).
        RuntimeError: If key generation fails strength validation after
                      max_attempts (indicates CSPRNG failure — should never
                      happen in practice).
    """
    if length < 16:
        raise ValueError(
            f"Key length must be >= 16 bytes (128-bit minimum). Got: {length}"
        )

    for attempt in range(1, max_attempts + 1):
        key = secrets.token_hex(length)
        is_valid, reason = validate_api_key_strength(key)

        if is_valid:
            return key

        # This should essentially never happen with a healthy CSPRNG
        logger.warning(
            "api_key_generation_weak_key_rejected",
            attempt=attempt,
            reason=reason,
        )

    raise RuntimeError(
        f"Failed to generate a strong API key after {max_attempts} attempts. "
        "This may indicate a CSPRNG failure — investigate immediately."
    )


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
