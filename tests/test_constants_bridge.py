"""
Tests for constants bridge - shared constants mirrored from TypeScript.

Tests trust tier mapping, score-to-tier conversion, capabilities,
error codes, and domain registry.
"""

import pytest

from app.constants_bridge import (
    TrustTier,
    TIER_THRESHOLDS,
    score_to_tier,
    CAPABILITIES,
    get_capabilities_for_tier,
    get_capability,
    ERROR_CODES,
    ALL_ERROR_CODES,
    get_error_by_code,
    get_errors_by_category,
    RATE_LIMITS,
    TIER_QUOTAS,
    VORION_DOMAINS,
    VORION_COMMERCIAL_DOMAINS,
    COGNIGATE_DOMAINS,
    API_VERSIONS,
    CURRENT_VERSIONS,
)


class TestTrustTierEnum:
    """Test TrustTier enum values."""

    def test_eight_tiers_defined(self):
        assert len(TrustTier) == 8

    def test_tier_values(self):
        assert TrustTier.T0_SANDBOX == 0
        assert TrustTier.T1_OBSERVED == 1
        assert TrustTier.T2_PROVISIONAL == 2
        assert TrustTier.T3_MONITORED == 3
        assert TrustTier.T4_STANDARD == 4
        assert TrustTier.T5_TRUSTED == 5
        assert TrustTier.T6_CERTIFIED == 6
        assert TrustTier.T7_AUTONOMOUS == 7


class TestScoreToTier:
    """Test score → tier mapping."""

    @pytest.mark.parametrize("score,expected_tier", [
        (0, TrustTier.T0_SANDBOX),
        (100, TrustTier.T0_SANDBOX),
        (199, TrustTier.T0_SANDBOX),
        (200, TrustTier.T1_OBSERVED),
        (349, TrustTier.T1_OBSERVED),
        (350, TrustTier.T2_PROVISIONAL),
        (499, TrustTier.T2_PROVISIONAL),
        (500, TrustTier.T3_MONITORED),
        (649, TrustTier.T3_MONITORED),
        (650, TrustTier.T4_STANDARD),
        (799, TrustTier.T4_STANDARD),
        (800, TrustTier.T5_TRUSTED),
        (875, TrustTier.T5_TRUSTED),
        (876, TrustTier.T6_CERTIFIED),
        (950, TrustTier.T6_CERTIFIED),
        (951, TrustTier.T7_AUTONOMOUS),
        (1000, TrustTier.T7_AUTONOMOUS),
    ])
    def test_score_maps_to_correct_tier(self, score, expected_tier):
        assert score_to_tier(score) == expected_tier

    def test_negative_score_raises(self):
        with pytest.raises(ValueError):
            score_to_tier(-1)

    def test_score_over_1000_raises(self):
        with pytest.raises(ValueError):
            score_to_tier(1001)

    def test_boundary_values(self):
        """Test every tier boundary."""
        assert score_to_tier(0) == TrustTier.T0_SANDBOX
        assert score_to_tier(200) == TrustTier.T1_OBSERVED
        assert score_to_tier(350) == TrustTier.T2_PROVISIONAL
        assert score_to_tier(500) == TrustTier.T3_MONITORED
        assert score_to_tier(650) == TrustTier.T4_STANDARD
        assert score_to_tier(800) == TrustTier.T5_TRUSTED
        assert score_to_tier(876) == TrustTier.T6_CERTIFIED
        assert score_to_tier(951) == TrustTier.T7_AUTONOMOUS


class TestTierThresholds:
    """Test tier threshold definitions."""

    def test_all_tiers_have_thresholds(self):
        for tier in TrustTier:
            assert tier in TIER_THRESHOLDS

    def test_thresholds_have_required_fields(self):
        for tier, info in TIER_THRESHOLDS.items():
            assert "min" in info
            assert "max" in info
            assert "name" in info
            assert "description" in info

    def test_thresholds_are_contiguous(self):
        """No gaps between tier ranges."""
        tiers = sorted(TIER_THRESHOLDS.items(), key=lambda x: x[1]["min"])
        for i in range(1, len(tiers)):
            prev_max = tiers[i - 1][1]["max"]
            curr_min = tiers[i][1]["min"]
            assert curr_min == prev_max + 1, (
                f"Gap between {tiers[i-1][0]} (max={prev_max}) "
                f"and {tiers[i][0]} (min={curr_min})"
            )

    def test_full_range_covered(self):
        """Score range 0-1000 is fully covered."""
        all_mins = [info["min"] for info in TIER_THRESHOLDS.values()]
        all_maxs = [info["max"] for info in TIER_THRESHOLDS.values()]
        assert min(all_mins) == 0
        assert max(all_maxs) == 1000


class TestCapabilities:
    """Test capability definitions."""

    def test_capabilities_exist(self):
        assert len(CAPABILITIES) > 0

    def test_capabilities_have_required_fields(self):
        for cap in CAPABILITIES:
            assert "code" in cap
            assert "name" in cap
            assert "category" in cap
            assert "unlockTier" in cap

    def test_get_capabilities_for_tier_0(self):
        t0_caps = get_capabilities_for_tier(0)
        assert len(t0_caps) >= 2  # CAP-READ-PUBLIC, CAP-GENERATE-TEXT
        assert all(cap["unlockTier"] <= 0 for cap in t0_caps)

    def test_higher_tiers_get_more_capabilities(self):
        for level in range(7):
            lower = get_capabilities_for_tier(level)
            higher = get_capabilities_for_tier(level + 1)
            assert len(higher) >= len(lower)

    def test_get_capability_by_code(self):
        cap = get_capability("CAP-READ-PUBLIC")
        assert cap is not None
        assert cap["name"] == "Read Public Data"

    def test_get_capability_not_found(self):
        cap = get_capability("NONEXISTENT")
        assert cap is None


class TestErrorCodes:
    """Test error code definitions."""

    def test_error_codes_exist(self):
        assert len(ERROR_CODES) > 0
        assert len(ALL_ERROR_CODES) > 0

    def test_error_codes_have_required_fields(self):
        for code_info in ALL_ERROR_CODES:
            assert "code" in code_info
            assert "httpStatus" in code_info
            assert "category" in code_info
            assert "message" in code_info

    def test_get_error_by_code(self):
        error = get_error_by_code("E1001")
        assert error is not None
        assert error["httpStatus"] == 401

    def test_get_error_by_code_not_found(self):
        error = get_error_by_code("E9999")
        assert error is None

    def test_get_errors_by_category(self):
        auth_errors = get_errors_by_category("auth")
        assert len(auth_errors) >= 5
        assert all(e["category"] == "auth" for e in auth_errors)

    def test_unique_error_codes(self):
        codes = [e["code"] for e in ALL_ERROR_CODES]
        assert len(codes) == len(set(codes)), "Duplicate error codes found"


class TestRateLimits:
    """Test rate limit definitions."""

    def test_all_tiers_have_rate_limits(self):
        for tier in TrustTier:
            assert tier in RATE_LIMITS

    def test_rate_limits_increase_with_tier(self):
        prev = 0
        for tier in TrustTier:
            rps = RATE_LIMITS[tier]["requestsPerSecond"]
            assert rps >= prev, f"T{tier} rps ({rps}) should be >= T{tier-1} ({prev})"
            prev = rps


class TestTierQuotas:
    """Test tier quota definitions."""

    def test_all_tiers_have_quotas(self):
        for tier in TrustTier:
            assert tier in TIER_QUOTAS

    def test_t7_has_unlimited_api_calls(self):
        assert TIER_QUOTAS[TrustTier.T7_AUTONOMOUS]["monthlyApiCalls"] == -1


class TestDomains:
    """Test domain registry."""

    def test_vorion_domains(self):
        assert "main" in VORION_DOMAINS
        assert "vorion.org" in VORION_DOMAINS["main"]

    def test_vorion_commercial_domains(self):
        assert "main" in VORION_COMMERCIAL_DOMAINS
        assert "vorion.org" in VORION_COMMERCIAL_DOMAINS["main"]

    def test_cognigate_domains(self):
        assert "main" in COGNIGATE_DOMAINS
        assert "cognigate.dev" in COGNIGATE_DOMAINS["main"]


class TestAPIVersions:
    """Test API version registry."""

    def test_cognigate_version_defined(self):
        assert "cognigate" in API_VERSIONS
        assert "v1" in API_VERSIONS["cognigate"]

    def test_current_versions_defined(self):
        assert "cognigate" in CURRENT_VERSIONS
        assert CURRENT_VERSIONS["cognigate"] == "v1"
