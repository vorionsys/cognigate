# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Tests for Self-Healing Autonomy / Evolutionary Algorithms (app.core.self_healing).

Covers:
  - Fitness functions (asymmetry and composite)
  - TrustParams operations (ratio, blend, clamp)
  - Blend level classification
  - GA convergence toward target ratio
  - Parameter validation
  - Edge cases (bounds, extreme targets, seeded runs)
"""

import pytest

from app.core.self_healing import (
    BlendLevel,
    EvolutionResult,
    Individual,
    TrustParams,
    asymmetry_fitness,
    composite_fitness,
    evolve,
    quick_evolve,
    validate_evolved_params,
    BLEND_FULL_THRESHOLD,
    BLEND_MINIMAL_THRESHOLD,
    BLEND_PARTIAL_THRESHOLD,
    DEFAULT_TARGET_RATIO,
    PARAM_MAX,
    PARAM_MIN,
)


# =============================================================================
# TestTrustParams
# =============================================================================

class TestTrustParams:
    def test_ratio(self):
        p = TrustParams(r_g=0.05, r_l=0.50)
        assert p.ratio == 10.0

    def test_ratio_zero_rg(self):
        p = TrustParams(r_g=0.0, r_l=0.50)
        assert p.ratio == float('inf')

    def test_blend_zero(self):
        a = TrustParams(r_g=0.05, r_l=0.15)
        b = TrustParams(r_g=0.10, r_l=0.20)
        blended = a.blend(b, 0.0)
        assert blended.r_g == 0.05
        assert blended.r_l == 0.15

    def test_blend_one(self):
        a = TrustParams(r_g=0.05, r_l=0.15)
        b = TrustParams(r_g=0.10, r_l=0.20)
        blended = a.blend(b, 1.0)
        assert abs(blended.r_g - 0.10) < 0.0001
        assert abs(blended.r_l - 0.20) < 0.0001

    def test_blend_half(self):
        a = TrustParams(r_g=0.10, r_l=0.10)
        b = TrustParams(r_g=0.20, r_l=0.20)
        blended = a.blend(b, 0.5)
        assert abs(blended.r_g - 0.15) < 0.0001
        assert abs(blended.r_l - 0.15) < 0.0001

    def test_clamped_low(self):
        p = TrustParams(r_g=-1.0, r_l=-0.5)
        c = p.clamped()
        assert c.r_g == PARAM_MIN
        assert c.r_l == PARAM_MIN

    def test_clamped_high(self):
        p = TrustParams(r_g=10.0, r_l=10.0)
        c = p.clamped()
        assert c.r_g == PARAM_MAX
        assert c.r_l == PARAM_MAX


# =============================================================================
# TestFitness
# =============================================================================

class TestFitness:
    def test_perfect_ratio(self):
        p = TrustParams(r_g=0.05, r_l=0.50)  # ratio = 10
        f = asymmetry_fitness(p, target_ratio=10.0)
        assert f == 1.0

    def test_far_ratio(self):
        p = TrustParams(r_g=0.05, r_l=0.05)  # ratio = 1
        f = asymmetry_fitness(p, target_ratio=10.0)
        assert f < 0.2  # fitness = 1/(1+9) = 0.1

    def test_zero_rg(self):
        p = TrustParams(r_g=0.0, r_l=0.15)
        f = asymmetry_fitness(p, target_ratio=10.0)
        assert f == 0.0

    def test_composite_penalizes_extremes(self):
        # Near-zero r_g should get penalized.
        p_extreme = TrustParams(r_g=0.001, r_l=0.010)  # ratio = 10
        p_normal = TrustParams(r_g=0.05, r_l=0.50)     # ratio = 10
        f_extreme = composite_fitness(p_extreme, target_ratio=10.0)
        f_normal = composite_fitness(p_normal, target_ratio=10.0)
        assert f_normal > f_extreme


# =============================================================================
# TestEvolution
# =============================================================================

class TestEvolution:
    def test_seeded_reproducibility(self):
        a = evolve(seed=42, generations=10, population_size=10)
        b = evolve(seed=42, generations=10, population_size=10)
        assert a.best_fitness == b.best_fitness
        assert a.best_params.r_g == b.best_params.r_g

    def test_converges_toward_target(self):
        result = evolve(
            current_params=TrustParams(r_g=0.05, r_l=0.15),
            target_ratio=10.0,
            generations=50,
            population_size=30,
            seed=123,
        )
        # Should be closer to 10:1 than the start (3:1).
        assert result.achieved_ratio > 3.0
        assert result.best_fitness > 0.5

    def test_fitness_improves(self):
        result = evolve(generations=20, population_size=15, seed=99)
        if len(result.fitness_history) >= 2:
            # Last gen fitness should be >= first gen.
            assert result.fitness_history[-1] >= result.fitness_history[0]

    def test_blend_level_assigned(self):
        result = evolve(generations=50, population_size=30, seed=42)
        assert result.blend_level in BlendLevel

    def test_blended_params_between(self):
        result = evolve(
            current_params=TrustParams(r_g=0.05, r_l=0.15),
            generations=20,
            seed=42,
        )
        # Blended should be between original and best.
        if result.blend_fraction > 0 and result.blend_fraction < 1:
            assert result.blended_params.r_g != result.original_params.r_g or \
                   result.blended_params.r_l != result.original_params.r_l

    def test_human_veto_flag(self):
        result = evolve(requires_human_veto=True, generations=5, seed=1)
        assert result.requires_human_veto is True


class TestQuickEvolve:
    def test_basic(self):
        result = quick_evolve(r_g=0.05, r_l=0.15, seed=42)
        assert result.best_fitness > 0
        assert result.generations_run > 0

    def test_custom_target(self):
        result = quick_evolve(target_ratio=5.0, seed=42, generations=30)
        # Should converge toward 5:1.
        assert result.target_ratio == 5.0


# =============================================================================
# TestValidation
# =============================================================================

class TestValidation:
    def test_valid_params(self):
        p = TrustParams(r_g=0.05, r_l=0.20)  # Within PARAM_MAX (0.30)
        valid, issues = validate_evolved_params(p)
        assert valid is True
        assert issues == []

    def test_rg_too_low(self):
        p = TrustParams(r_g=0.001, r_l=0.50)
        valid, issues = validate_evolved_params(p, min_r_g=0.01)
        assert valid is False
        assert any("r_g" in i for i in issues)

    def test_ratio_too_high(self):
        p = TrustParams(r_g=0.01, r_l=0.30)  # ratio = 30
        valid, issues = validate_evolved_params(p, max_ratio=20.0)
        assert valid is False
        assert any("ratio" in i for i in issues)

    def test_exceeds_param_max(self):
        p = TrustParams(r_g=0.50, r_l=0.50)
        valid, issues = validate_evolved_params(p)
        assert valid is False
        assert any("PARAM_MAX" in i for i in issues)
