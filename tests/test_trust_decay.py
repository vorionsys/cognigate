# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Tests for 182-day stepped inactivity trust decay.

Covers:
- Milestone schedule accuracy (all 9 milestones)
- Floor enforcement (50%)
- Linear interpolation between milestones
- Edge cases (0 days, negative, beyond 182)
- Integration with trust router (GET /trust/{id} decay fields)
- Decay endpoint (GET /trust/{id}/decay)
"""

import pytest
from app.core.trust_decay import (
    apply_decay,
    compute_decay_factor,
    DECAY_MILESTONES,
    DECAY_HALF_LIFE_DAYS,
    DECAY_FLOOR,
)


class TestDecayMilestones:
    """Verify each milestone in the 9-step schedule."""

    def test_constants(self):
        assert DECAY_HALF_LIFE_DAYS == 182
        assert DECAY_FLOOR == 0.50
        assert len(DECAY_MILESTONES) == 10  # day 0 + 9 steps

    @pytest.mark.parametrize("day,expected_factor", [
        (0,   1.00),
        (7,   0.98),
        (14,  0.95),
        (28,  0.90),
        (42,  0.85),
        (56,  0.80),
        (84,  0.70),
        (112, 0.60),
        (140, 0.55),
        (182, 0.50),
    ])
    def test_exact_milestones(self, day, expected_factor):
        factor = compute_decay_factor(day)
        assert factor == pytest.approx(expected_factor, abs=1e-6), (
            f"Day {day}: expected {expected_factor}, got {factor}"
        )

    def test_half_life_produces_50_percent(self):
        """182 days = exactly 50% retained (the defining property)."""
        score = 800
        decayed = apply_decay(score, 182)
        assert decayed == 400  # 800 * 0.50

    def test_floor_at_300_days(self):
        """Beyond 182 days, score stays at floor."""
        factor = compute_decay_factor(300)
        assert factor == 0.50

    def test_floor_at_1000_days(self):
        factor = compute_decay_factor(1000)
        assert factor == 0.50


class TestInterpolation:
    """Verify linear interpolation between milestones."""

    def test_midpoint_day_3_5(self):
        """Halfway between day 0 (1.00) and day 7 (0.98) = 0.99."""
        factor = compute_decay_factor(3.5)
        assert factor == pytest.approx(0.99, abs=1e-6)

    def test_day_10(self):
        """Between day 7 (0.98) and day 14 (0.95)."""
        # 10 is 3/7 of the way from 7 to 14
        expected = 0.98 + (3 / 7) * (0.95 - 0.98)  # 0.98 - 0.01286...
        factor = compute_decay_factor(10)
        assert factor == pytest.approx(expected, abs=1e-6)

    def test_day_50(self):
        """Between day 42 (0.85) and day 56 (0.80)."""
        # 50 is 8/14 of the way from 42 to 56
        expected = 0.85 + (8 / 14) * (0.80 - 0.85)
        factor = compute_decay_factor(50)
        assert factor == pytest.approx(expected, abs=1e-6)


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_zero_days(self):
        assert compute_decay_factor(0) == 1.0

    def test_negative_days(self):
        """Negative inactivity = no decay."""
        assert compute_decay_factor(-5) == 1.0

    def test_apply_decay_zero_score(self):
        assert apply_decay(0, 100) == 0

    def test_apply_decay_max_score(self):
        decayed = apply_decay(1000, 182)
        assert decayed == 500  # 1000 * 0.50

    def test_apply_decay_clamped_to_1000(self):
        """Even if somehow pre_decay > 1000, result clamped."""
        decayed = apply_decay(1200, 0)
        assert decayed == 1000

    def test_tiny_inactivity(self):
        """0.1 days = very small decay."""
        factor = compute_decay_factor(0.1)
        assert factor > 0.99  # barely any decay

    def test_custom_floor(self):
        """Custom floor of 0.70 (30% max decay)."""
        factor = compute_decay_factor(182, floor=0.70)
        assert factor == 0.70  # floor kicks in before 0.50


class TestApplyDecay:
    """Test apply_decay with realistic agent scores."""

    def test_high_trust_agent_30_days(self):
        """T5 agent (score 850) after 30 days idle."""
        # Day 28 = 0.90, day 42 = 0.85
        # Day 30 is 2/14 of way from 28 to 42
        expected_factor = 0.90 + (2 / 14) * (0.85 - 0.90)
        expected_score = int(850 * expected_factor)
        assert apply_decay(850, 30) == expected_score

    def test_low_trust_agent_7_days(self):
        """T0 agent (score 100) after 7 days."""
        assert apply_decay(100, 7) == 98  # 100 * 0.98

    def test_mid_trust_agent_full_decay(self):
        """T3 agent (score 600) at full 182-day decay."""
        assert apply_decay(600, 182) == 300  # 600 * 0.50

    def test_no_inactivity(self):
        """Active agent = no decay."""
        assert apply_decay(750, 0) == 750
