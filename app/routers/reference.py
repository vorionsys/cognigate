"""
Reference Data API Router

Exposes all shared-constants as live API endpoints with auto-documentation.
Developers can query tiers, capabilities, error codes, rate limits, versions,
products, and domains programmatically.
"""

from fastapi import APIRouter, HTTPException

from app.constants_bridge import (
    TIER_THRESHOLDS,
    TrustTier,
    score_to_tier,
    CAPABILITIES,
    get_capabilities_for_tier,
    get_capability,
    ALL_ERROR_CODES,
    get_error_by_code,
    RATE_LIMITS,
    TIER_QUOTAS,
    API_VERSIONS,
    CURRENT_VERSIONS,
    ALL_PRODUCTS,
    ALL_DOMAINS,
)

router = APIRouter()


# =============================================================================
# TIERS
# =============================================================================

@router.get("/reference/tiers", summary="List all trust tiers")
async def list_tiers() -> dict:
    """
    Returns all 8 trust tiers (T0-T7) with thresholds, colors, and descriptions.

    The BASIS trust model uses scores from 0-1000 mapped to 8 tiers,
    each unlocking progressively more capabilities.
    """
    tiers = []
    for tier_enum in TrustTier:
        threshold = TIER_THRESHOLDS[tier_enum]
        tiers.append({
            "tier": tier_enum.value,
            "code": f"T{tier_enum.value}",
            "enumName": tier_enum.name,
            **threshold,
        })
    return {"tiers": tiers, "count": len(tiers)}


@router.get("/reference/tiers/{tier}", summary="Get single tier detail")
async def get_tier(tier: str) -> dict:
    """
    Get details for a single trust tier by code (T0-T7) or number (0-7).

    Returns threshold range, color, description, available capabilities,
    rate limits, and quotas for the tier.
    """
    # Parse tier input
    tier_value = _parse_tier(tier)
    if tier_value is None:
        raise HTTPException(status_code=404, detail=f"Tier not found: {tier}")

    threshold = TIER_THRESHOLDS[tier_value]
    capabilities = get_capabilities_for_tier(tier_value)
    rate_limits = RATE_LIMITS[tier_value]
    quotas = TIER_QUOTAS[tier_value]

    return {
        "tier": tier_value,
        "code": f"T{tier_value}",
        **threshold,
        "capabilities": capabilities,
        "capabilityCount": len(capabilities),
        "rateLimits": rate_limits,
        "quotas": quotas,
    }


@router.get("/reference/tiers/lookup/{score}", summary="Lookup tier by score")
async def lookup_tier_by_score(score: int) -> dict:
    """
    Given a trust score (0-1000), returns the corresponding tier and its details.
    """
    if score < 0 or score > 1000:
        raise HTTPException(status_code=400, detail="Score must be between 0 and 1000")

    tier_value = score_to_tier(score)
    threshold = TIER_THRESHOLDS[tier_value]

    return {
        "score": score,
        "tier": tier_value,
        "code": f"T{tier_value}",
        **threshold,
    }


# =============================================================================
# CAPABILITIES
# =============================================================================

@router.get("/reference/capabilities", summary="List all capabilities")
async def list_capabilities(tier: int | None = None, category: str | None = None) -> dict:
    """
    Returns all 24 capability definitions with tier requirements.

    Optional filters:
    - **tier**: Filter to capabilities available at this tier level (0-7)
    - **category**: Filter by category (data_access, api_access, code_execution, etc.)
    """
    caps = CAPABILITIES

    if tier is not None:
        caps = [c for c in caps if c["unlockTier"] <= tier]

    if category is not None:
        caps = [c for c in caps if c["category"] == category]

    return {"capabilities": caps, "count": len(caps)}


@router.get("/reference/capabilities/{code}", summary="Get single capability")
async def get_capability_detail(code: str) -> dict:
    """
    Get a single capability by its code (e.g. CAP-READ-PUBLIC).
    """
    cap = get_capability(code.upper())
    if cap is None:
        raise HTTPException(status_code=404, detail=f"Capability not found: {code}")
    return cap


# =============================================================================
# ERROR CODES
# =============================================================================

@router.get("/reference/errors", summary="List all error codes")
async def list_errors(category: str | None = None, retryable: bool | None = None) -> dict:
    """
    Returns all 35+ standardized error codes across 7 categories.

    Optional filters:
    - **category**: Filter by category (auth, validation, rate_limit, not_found, trust, server, external)
    - **retryable**: Filter by retryable flag (true/false)
    """
    errors = ALL_ERROR_CODES

    if category is not None:
        errors = [e for e in errors if e["category"] == category]

    if retryable is not None:
        errors = [e for e in errors if e["retryable"] == retryable]

    return {"errors": errors, "count": len(errors)}


@router.get("/reference/errors/{code}", summary="Get single error code")
async def get_error_detail(code: str) -> dict:
    """
    Get a single error definition by code (e.g. E1001, E2003).
    """
    error = get_error_by_code(code.upper())
    if error is None:
        raise HTTPException(status_code=404, detail=f"Error code not found: {code}")
    return error


# =============================================================================
# RATE LIMITS
# =============================================================================

@router.get("/reference/rate-limits", summary="List rate limits by tier")
async def list_rate_limits() -> dict:
    """
    Returns rate limits for all 8 trust tiers.

    Higher trust tiers receive progressively higher rate limits,
    payload sizes, and timeout allowances.
    """
    limits = []
    for tier_enum in TrustTier:
        threshold = TIER_THRESHOLDS[tier_enum]
        limits.append({
            "tier": tier_enum.value,
            "code": f"T{tier_enum.value}",
            "name": threshold["name"],
            "rateLimits": RATE_LIMITS[tier_enum],
            "quotas": TIER_QUOTAS[tier_enum],
        })
    return {"rateLimits": limits, "count": len(limits)}


@router.get("/reference/rate-limits/{tier}", summary="Get rate limits for a tier")
async def get_rate_limits_for_tier(tier: str) -> dict:
    """
    Get rate limits and quotas for a specific tier (T0-T7 or 0-7).
    """
    tier_value = _parse_tier(tier)
    if tier_value is None:
        raise HTTPException(status_code=404, detail=f"Tier not found: {tier}")

    threshold = TIER_THRESHOLDS[tier_value]
    return {
        "tier": tier_value,
        "code": f"T{tier_value}",
        "name": threshold["name"],
        "rateLimits": RATE_LIMITS[tier_value],
        "quotas": TIER_QUOTAS[tier_value],
    }


# =============================================================================
# API VERSIONS
# =============================================================================

@router.get("/reference/versions", summary="List all API versions")
async def list_versions() -> dict:
    """
    Returns the version registry for all services:
    cognigate, trust, logic, basis, and carSpec.
    """
    return {
        "versions": API_VERSIONS,
        "currentVersions": CURRENT_VERSIONS,
    }


# =============================================================================
# PRODUCTS
# =============================================================================

@router.get("/reference/products", summary="List product catalog")
async def list_products(organization: str | None = None) -> dict:
    """
    Returns the full Vorion ecosystem product catalog.

    Optional filter:
    - **organization**: Filter by organization (vorion, agentAnchor)
    """
    if organization is not None:
        products = ALL_PRODUCTS.get(organization)
        if products is None:
            raise HTTPException(
                status_code=404,
                detail=f"Organization not found: {organization}. Use 'vorion' or 'agentAnchor'.",
            )
        return {"products": products, "organization": organization}

    return {"products": ALL_PRODUCTS}


# =============================================================================
# DOMAINS
# =============================================================================

@router.get("/reference/domains", summary="List domain registry")
async def list_domains() -> dict:
    """
    Returns the complete domain registry for the Vorion ecosystem:
    websites, API endpoints, GitHub orgs, and NPM packages.
    """
    return {"domains": ALL_DOMAINS}


# =============================================================================
# HELPERS
# =============================================================================

def _parse_tier(tier_input: str) -> int | None:
    """Parse tier from string (e.g. 'T3', '3', 't3')."""
    normalized = tier_input.upper().strip()

    # Try T# format
    if normalized.startswith("T"):
        normalized = normalized[1:]

    try:
        value = int(normalized)
        if 0 <= value <= 7:
            return value
    except ValueError:
        pass

    # Try name format
    name_map = {
        "SANDBOX": 0,
        "OBSERVED": 1,
        "PROVISIONAL": 2,
        "MONITORED": 3,
        "STANDARD": 4,
        "TRUSTED": 5,
        "CERTIFIED": 6,
        "AUTONOMOUS": 7,
    }
    return name_map.get(tier_input.upper().strip())
