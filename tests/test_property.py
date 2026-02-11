"""
Property-based tests using Hypothesis.

Tests invariants of the trust scoring system, policy evaluation
determinism, and proof chain integrity guarantees.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume

from app.constants_bridge import (
    TrustTier,
    TIER_THRESHOLDS,
    score_to_tier,
    get_capabilities_for_tier,
    CAPABILITIES,
)
from app.core.tripwires import check_tripwires, TripwireResult
from app.routers.proof import calculate_hash


# =============================================================================
# TRUST SCORING INVARIANTS
# =============================================================================


class TestTrustScoringProperties:
    """Property: trust scoring maps are total and monotonic."""

    @given(score=st.integers(min_value=0, max_value=1000))
    def test_any_valid_score_maps_to_tier(self, score: int):
        """Every score 0-1000 must map to exactly one tier."""
        tier = score_to_tier(score)
        assert 0 <= tier <= 7

    @given(score=st.integers(min_value=0, max_value=1000))
    def test_tier_thresholds_contain_score(self, score: int):
        """The mapped tier's threshold range must contain the score."""
        tier = score_to_tier(score)
        threshold = TIER_THRESHOLDS[TrustTier(tier)]
        assert threshold["min"] <= score <= threshold["max"]

    @given(
        score_a=st.integers(min_value=0, max_value=1000),
        score_b=st.integers(min_value=0, max_value=1000),
    )
    def test_higher_score_never_lower_tier(self, score_a: int, score_b: int):
        """Higher trust score must never result in a lower tier (monotonicity)."""
        assume(score_a <= score_b)
        tier_a = score_to_tier(score_a)
        tier_b = score_to_tier(score_b)
        assert tier_a <= tier_b

    @given(
        tier_a=st.integers(min_value=0, max_value=7),
        tier_b=st.integers(min_value=0, max_value=7),
    )
    def test_higher_tier_more_capabilities(self, tier_a: int, tier_b: int):
        """Higher tiers must unlock at least as many capabilities."""
        assume(tier_a <= tier_b)
        caps_a = get_capabilities_for_tier(tier_a)
        caps_b = get_capabilities_for_tier(tier_b)
        assert len(caps_a) <= len(caps_b)


class TestTierThresholdProperties:
    """Property: tier thresholds are complete and non-overlapping."""

    def test_thresholds_cover_full_range(self):
        """Tiers must cover the entire 0-1000 range with no gaps."""
        for score in range(0, 1001):
            tier = score_to_tier(score)
            assert 0 <= tier <= 7, f"Score {score} mapped to invalid tier {tier}"

    def test_thresholds_non_overlapping(self):
        """No score should be claimed by multiple tiers."""
        for tier_enum in TrustTier:
            threshold = TIER_THRESHOLDS[tier_enum]
            for other_enum in TrustTier:
                if tier_enum == other_enum:
                    continue
                other = TIER_THRESHOLDS[other_enum]
                # Ranges should not overlap
                assert (
                    threshold["max"] < other["min"]
                    or threshold["min"] > other["max"]
                ), f"{tier_enum.name} overlaps with {other_enum.name}"

    def test_thresholds_contiguous(self):
        """Each tier's max should be exactly one less than the next tier's min."""
        sorted_tiers = sorted(TrustTier, key=lambda t: TIER_THRESHOLDS[t]["min"])
        for i in range(len(sorted_tiers) - 1):
            current = TIER_THRESHOLDS[sorted_tiers[i]]
            next_tier = TIER_THRESHOLDS[sorted_tiers[i + 1]]
            assert current["max"] + 1 == next_tier["min"], (
                f"Gap between {sorted_tiers[i].name} (max={current['max']}) "
                f"and {sorted_tiers[i+1].name} (min={next_tier['min']})"
            )


# =============================================================================
# PROOF CHAIN INTEGRITY
# =============================================================================


class TestProofHashProperties:
    """Property: proof hashes are deterministic and collision-resistant."""

    @given(data=st.fixed_dictionaries({
        "key": st.text(min_size=1, max_size=50),
        "value": st.integers(),
    }))
    def test_hash_deterministic(self, data: dict):
        """Same data must always produce the same hash."""
        assert calculate_hash(data) == calculate_hash(data)

    @given(
        key=st.text(min_size=1, max_size=20),
        val_a=st.integers(),
        val_b=st.integers(),
    )
    def test_different_values_different_hashes(self, key: str, val_a: int, val_b: int):
        """Different values should produce different hashes (probabilistic)."""
        assume(val_a != val_b)
        h1 = calculate_hash({key: val_a})
        h2 = calculate_hash({key: val_b})
        assert h1 != h2

    @given(data=st.fixed_dictionaries({
        "a": st.integers(),
        "b": st.text(max_size=20),
    }))
    def test_hash_is_valid_sha256(self, data: dict):
        """Hash output must always be a valid 64-char hex string."""
        h = calculate_hash(data)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


# =============================================================================
# TRIPWIRE DETECTION
# =============================================================================


class TestTripwireProperties:
    """Property: tripwire detection is pure and deterministic."""

    @given(text=st.text(max_size=200))
    @settings(max_examples=50)
    def test_tripwire_returns_valid_result(self, text: str):
        """check_tripwires must always return a TripwireResult."""
        result = check_tripwires(text)
        assert isinstance(result, TripwireResult)
        assert isinstance(result.triggered, bool)
        assert result.severity in ("info", "warning", "critical")

    @given(text=st.text(max_size=200))
    @settings(max_examples=50)
    def test_tripwire_deterministic(self, text: str):
        """Same input must always give same result."""
        r1 = check_tripwires(text)
        r2 = check_tripwires(text)
        assert r1.triggered == r2.triggered
        assert r1.pattern_name == r2.pattern_name

    def test_safe_inputs_not_triggered(self):
        """Normal business text should never trigger tripwires."""
        safe_inputs = [
            "Please read the quarterly report",
            "Update the customer database record",
            "Send the weekly summary email",
            "Calculate the monthly revenue",
        ]
        for text in safe_inputs:
            result = check_tripwires(text)
            assert not result.triggered, f"False positive on: {text}"
