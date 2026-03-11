# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Tests for Monte Carlo Risk Forecasting Engine (app.core.monte_carlo).

Covers:
  - Band classification (GREEN/YELLOW/ORANGE/RED)
  - Multiplier computation (tiered exponential)
  - Analytical failure probability
  - Chain error formula
  - Monte Carlo simulation (seeded for reproducibility)
  - Full forecast with derated scores
  - Horizon degradation
  - Chain forecasting
  - Risk threshold bypass
"""

import pytest

from app.core.monte_carlo import (
    ForecastBand,
    ForecastResult,
    analytical_failure_prob,
    classify_band,
    compute_chain_error,
    compute_multiplier,
    forecast,
    forecast_chain,
    run_monte_carlo,
    BAND_YELLOW,
    BAND_ORANGE,
    BAND_RED,
    MULTIPLIER_FLOOR,
    FORECAST_RISK_THRESHOLD,
)


# =============================================================================
# TestBandClassification
# =============================================================================

class TestBandClassification:
    def test_green(self):
        assert classify_band(0.0) == ForecastBand.GREEN
        assert classify_band(0.04) == ForecastBand.GREEN

    def test_yellow(self):
        assert classify_band(0.05) == ForecastBand.YELLOW
        assert classify_band(0.19) == ForecastBand.YELLOW

    def test_orange(self):
        assert classify_band(0.20) == ForecastBand.ORANGE
        assert classify_band(0.49) == ForecastBand.ORANGE

    def test_red(self):
        assert classify_band(0.50) == ForecastBand.RED
        assert classify_band(1.0) == ForecastBand.RED


# =============================================================================
# TestMultiplier
# =============================================================================

class TestMultiplier:
    def test_green_no_derate(self):
        assert compute_multiplier(0.0) == 1.0
        assert compute_multiplier(0.01) == 1.0

    def test_yellow_mild_derate(self):
        m = compute_multiplier(0.10)
        assert 0.7 < m < 1.0  # 0.90^1 = 0.90

    def test_orange_moderate_derate(self):
        m = compute_multiplier(0.30)
        assert 0.3 < m < 0.8

    def test_red_max_derate(self):
        m = compute_multiplier(0.80)
        assert m == 0.50

    def test_multiplier_never_below_floor(self):
        for prob in [0.1, 0.3, 0.5, 0.9, 1.0]:
            m = compute_multiplier(prob)
            assert m >= MULTIPLIER_FLOOR


# =============================================================================
# TestAnalyticalFailureProb
# =============================================================================

class TestAnalyticalFailureProb:
    def test_zero_epsilon(self):
        assert analytical_failure_prob(0.0, 100) == 0.0

    def test_zero_steps(self):
        assert analytical_failure_prob(0.05, 0) == 0.0

    def test_one_step(self):
        assert abs(analytical_failure_prob(0.05, 1) - 0.05) < 0.0001

    def test_epsilon_one(self):
        assert analytical_failure_prob(1.0, 1) == 1.0

    def test_24h_default(self):
        # 24 steps at ε=0.05 → 1 − 0.95^24 ≈ 0.708
        prob = analytical_failure_prob(0.05, 24)
        assert abs(prob - (1 - 0.95**24)) < 0.0001

    def test_compounding(self):
        # More steps → higher probability
        p10 = analytical_failure_prob(0.05, 10)
        p50 = analytical_failure_prob(0.05, 50)
        assert p50 > p10


# =============================================================================
# TestChainError
# =============================================================================

class TestChainError:
    def test_empty(self):
        assert compute_chain_error([]) == 0.0

    def test_single_step(self):
        assert abs(compute_chain_error([0.05]) - 0.05) < 0.0001

    def test_two_steps_same(self):
        # ε_chain = 1 − (1−0.05)² = 1 − 0.9025 = 0.0975
        err = compute_chain_error([0.05, 0.05])
        assert abs(err - 0.0975) < 0.0001

    def test_zero_epsilon(self):
        assert compute_chain_error([0.0, 0.0, 0.0]) == 0.0

    def test_one_epsilon(self):
        err = compute_chain_error([1.0, 0.5])
        assert err == 1.0  # One certain failure → chain fails

    def test_increasing(self):
        e1 = compute_chain_error([0.05])
        e3 = compute_chain_error([0.05, 0.05, 0.05])
        e5 = compute_chain_error([0.05, 0.05, 0.05, 0.05, 0.05])
        assert e1 < e3 < e5


# =============================================================================
# TestMonteCarlo
# =============================================================================

class TestMonteCarlo:
    def test_seeded_reproducibility(self):
        a = run_monte_carlo(epsilon=0.05, horizon_hours=24, trials=1000, seed=42)
        b = run_monte_carlo(epsilon=0.05, horizon_hours=24, trials=1000, seed=42)
        assert a == b

    def test_zero_epsilon(self):
        prob = run_monte_carlo(epsilon=0.0, horizon_hours=24, trials=500, seed=1)
        assert prob == 0.0

    def test_high_epsilon(self):
        prob = run_monte_carlo(epsilon=0.5, horizon_hours=24, trials=500, seed=1)
        assert prob > 0.90

    def test_converges_to_analytical(self):
        # With many trials, MC should be close to analytical.
        mc = run_monte_carlo(epsilon=0.05, horizon_hours=24, trials=5000, seed=123)
        analytical = analytical_failure_prob(0.05, 24)
        assert abs(mc - analytical) < 0.05  # Within 5%


# =============================================================================
# TestForecast
# =============================================================================

class TestForecast:
    def test_low_risk_bypass(self):
        result = forecast(trust_score=900, risk_score=30)
        assert result.band == ForecastBand.GREEN
        assert result.multiplier == 1.0
        assert result.derated_score == 900
        assert result.requires_action is False

    def test_high_epsilon_derates(self):
        result = forecast(trust_score=900, epsilon=0.10, horizon_hours=48, risk_score=90)
        assert result.derated_score < 900
        assert result.requires_action is True

    def test_low_epsilon_green(self):
        result = forecast(trust_score=900, epsilon=0.001, horizon_hours=1, risk_score=70)
        assert result.band == ForecastBand.GREEN
        assert result.derated_score == 900

    def test_horizon_degrades(self):
        result = forecast(trust_score=900, epsilon=0.10, horizon_hours=48, risk_score=90)
        assert result.effective_horizon_hours <= result.horizon_hours

    def test_score_never_negative(self):
        result = forecast(trust_score=100, epsilon=0.50, horizon_hours=72, risk_score=100)
        assert result.derated_score >= 0

    def test_score_never_exceeds_1000(self):
        result = forecast(trust_score=1000, epsilon=0.001, horizon_hours=1, risk_score=70)
        assert result.derated_score <= 1000

    def test_chain_error_populated(self):
        result = forecast(trust_score=900, epsilon=0.05, horizon_hours=24, risk_score=80)
        assert result.chain_error > 0

    def test_mc_mode(self):
        result = forecast(
            trust_score=900, epsilon=0.10, horizon_hours=24,
            risk_score=90, use_analytical=False, seed=42,
        )
        assert result.derated_score < 900
        assert result.trials > 0


# =============================================================================
# TestChainForecast
# =============================================================================

class TestChainForecast:
    def test_single_step(self):
        result = forecast_chain(trust_score=900, epsilons=[0.05], risk_score=90)
        assert result.steps == 1
        assert abs(result.chain_error - 0.05) < 0.01

    def test_multi_step(self):
        result = forecast_chain(
            trust_score=900, epsilons=[0.05, 0.10, 0.03], risk_score=90,
        )
        assert result.steps == 3
        assert result.chain_error > 0.05  # Compounded

    def test_high_chain_derates(self):
        epsilons = [0.10] * 20
        result = forecast_chain(trust_score=900, epsilons=epsilons, risk_score=90)
        assert result.derated_score < 900
        assert result.band != ForecastBand.GREEN

    def test_low_risk_bypass(self):
        result = forecast_chain(trust_score=900, epsilons=[0.5, 0.5], risk_score=30)
        assert result.derated_score == 900
        assert result.requires_action is False
