# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Monte Carlo Risk Forecasting Engine.

Inspired by JPL's trajectory optimization (Europa Clipper, Perseverance),
this module runs Monte Carlo rollouts to forecast failure probabilities
over configurable horizons before gating decisions.  When forecasted
failure probability exceeds threshold bands, it applies precautionary
multipliers that derate trust and shorten operational horizons.

Architecture:
  Pre-Action Gating → classify risk → if ρ ≥ threshold → run N trials
  → compute avg failure probability → apply tiered multiplier →
  return derated trust + recommended horizon.

Forecasting bands (graceful degradation):
  Band       Prob Range     Multiplier Formula        Action
  ─────────────────────────────────────────────────────────────
  GREEN      [0, 0.05)      1.00                      Full speed
  YELLOW     [0.05, 0.20)   0.90^(prob/0.10)          Minor slowdown
  ORANGE     [0.20, 0.50)   0.70^(prob/0.20)          Shorten horizon
  RED        [0.50, 1.00]   0.50                      Max derate

Horizon degradation (from requested):
  GREEN   → 100% of requested horizon
  YELLOW  → 75% of requested horizon
  ORANGE  → 50% of requested horizon
  RED     → 25% of requested horizon

The per-step failure rate ε can be calibrated from:
  - Static config (defaults)
  - Canary probe history (real-time)
  - RepE/SAE feature shifts (Layer 1 interpretability)

Chain error formula: ε_chain = 1 − ∏(1 − ε_i) for multi-agent chains.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default per-step failure rate.
DEFAULT_EPSILON: float = 0.05

# Default number of Monte Carlo trials.
DEFAULT_TRIALS: int = 2000

# Default forecast horizon in hours.
DEFAULT_HORIZON_HOURS: int = 24

# Minimum risk score to trigger forecasting.
FORECAST_RISK_THRESHOLD: int = 60

# Band thresholds.
BAND_YELLOW: float = 0.05
BAND_ORANGE: float = 0.20
BAND_RED: float = 0.50

# Floor multiplier (never derate below this).
MULTIPLIER_FLOOR: float = 0.30


class ForecastBand(str, Enum):
    """Risk band classification for forecasted failure probability."""
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"


# Band → horizon retention fraction.
BAND_HORIZON_FRACTION: dict[ForecastBand, float] = {
    ForecastBand.GREEN: 1.00,
    ForecastBand.YELLOW: 0.75,
    ForecastBand.ORANGE: 0.50,
    ForecastBand.RED: 0.25,
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ForecastResult:
    """Result of a Monte Carlo risk forecast."""
    avg_failure_prob: float
    band: ForecastBand
    multiplier: float
    derated_score: int
    raw_score: int
    horizon_hours: int
    effective_horizon_hours: float
    trials: int
    epsilon: float
    steps: int
    chain_error: float       # ε_chain for the full chain
    requires_action: bool    # True if not GREEN
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def classify_band(prob: float) -> ForecastBand:
    """Classify a failure probability into a forecast band."""
    if prob < BAND_YELLOW:
        return ForecastBand.GREEN
    if prob < BAND_ORANGE:
        return ForecastBand.YELLOW
    if prob < BAND_RED:
        return ForecastBand.ORANGE
    return ForecastBand.RED


def compute_multiplier(prob: float) -> float:
    """
    Compute the precautionary trust multiplier from failure probability.

    GREEN:  1.00 (no derate)
    YELLOW: 0.90^(prob/0.10)  — mild exponential derate
    ORANGE: 0.70^(prob/0.20)  — moderate exponential derate
    RED:    0.50              — maximum derate

    Returns
    -------
    float
        Multiplier in [MULTIPLIER_FLOOR, 1.0].
    """
    band = classify_band(prob)
    if band == ForecastBand.GREEN:
        return 1.0
    if band == ForecastBand.YELLOW:
        m = 0.90 ** (prob / 0.10)
        return max(m, MULTIPLIER_FLOOR)
    if band == ForecastBand.ORANGE:
        m = 0.70 ** (prob / 0.20)
        return max(m, MULTIPLIER_FLOOR)
    # RED
    return max(0.50, MULTIPLIER_FLOOR)


def compute_chain_error(epsilons: list[float]) -> float:
    """
    Compute composite chain error: ε_chain = 1 − ∏(1 − ε_i).

    For a sequence of steps each with independent failure rate ε_i,
    the probability of at least one failure over the chain.

    Parameters
    ----------
    epsilons : list[float]
        Per-step failure rates.

    Returns
    -------
    float
        Chain failure probability in [0, 1].
    """
    if not epsilons:
        return 0.0
    product = 1.0
    for e in epsilons:
        product *= (1.0 - max(0.0, min(1.0, e)))
    return 1.0 - product


def run_monte_carlo(
    epsilon: float = DEFAULT_EPSILON,
    horizon_hours: int = DEFAULT_HORIZON_HOURS,
    steps_per_hour: int = 1,
    trials: int = DEFAULT_TRIALS,
    seed: Optional[int] = None,
) -> float:
    """
    Run Monte Carlo simulation to estimate average failure probability.

    Each trial simulates ``horizon_hours × steps_per_hour`` steps.
    A trial "fails" if at least one step fails (Bernoulli with prob ε).

    Parameters
    ----------
    epsilon : float
        Per-step failure probability.
    horizon_hours : int
        Forecast horizon in hours.
    steps_per_hour : int
        Steps per hour (default 1).
    trials : int
        Number of Monte Carlo trials.
    seed : int, optional
        Random seed for reproducibility.

    Returns
    -------
    float
        Average failure probability across all trials.
    """
    if seed is not None:
        random.seed(seed)

    total_steps = horizon_hours * steps_per_hour
    if total_steps <= 0:
        return 0.0

    # Fast path: analytical solution when ε is constant per step.
    # P(at least one failure) = 1 − (1 − ε)^steps
    # Monte Carlo for validation and when ε varies.
    failures = 0
    for _ in range(trials):
        # Each step: fail with probability ε.
        trial_ok = True
        for _ in range(total_steps):
            if random.random() < epsilon:
                trial_ok = False
                break  # One failure — trial fails
        if not trial_ok:
            failures += 1

    return failures / max(trials, 1)


def analytical_failure_prob(epsilon: float, steps: int) -> float:
    """
    Compute the analytical failure probability for constant ε.

    P(fail) = 1 − (1 − ε)^steps

    This is the exact solution; Monte Carlo converges to this.
    """
    if steps <= 0 or epsilon <= 0:
        return 0.0
    if epsilon >= 1.0:
        return 1.0
    return 1.0 - (1.0 - epsilon) ** steps


def forecast(
    trust_score: int,
    epsilon: float = DEFAULT_EPSILON,
    horizon_hours: int = DEFAULT_HORIZON_HOURS,
    steps_per_hour: int = 1,
    trials: int = DEFAULT_TRIALS,
    risk_score: float = 0.0,
    seed: Optional[int] = None,
    use_analytical: bool = True,
) -> ForecastResult:
    """
    Run a full risk forecast and compute derated trust.

    Parameters
    ----------
    trust_score : int
        Current trust score (0-1000).
    epsilon : float
        Per-step failure rate.
    horizon_hours : int
        Forecast horizon in hours.
    steps_per_hour : int
        Steps per hour.
    trials : int
        Monte Carlo trial count (used only if use_analytical=False).
    risk_score : float
        Pre-action risk score (ρ).
    seed : int, optional
        Random seed.
    use_analytical : bool
        If True, use exact formula instead of Monte Carlo.

    Returns
    -------
    ForecastResult
        Full forecast with derated score, band, and horizon.
    """
    total_steps = horizon_hours * steps_per_hour

    # Bypass if risk is low.
    if risk_score < FORECAST_RISK_THRESHOLD:
        return ForecastResult(
            avg_failure_prob=0.0,
            band=ForecastBand.GREEN,
            multiplier=1.0,
            derated_score=trust_score,
            raw_score=trust_score,
            horizon_hours=horizon_hours,
            effective_horizon_hours=float(horizon_hours),
            trials=0,
            epsilon=epsilon,
            steps=total_steps,
            chain_error=0.0,
            requires_action=False,
            details={"bypassed": True, "reason": "risk_below_threshold"},
        )

    # Compute failure probability.
    if use_analytical:
        prob = analytical_failure_prob(epsilon, total_steps)
    else:
        prob = run_monte_carlo(
            epsilon=epsilon,
            horizon_hours=horizon_hours,
            steps_per_hour=steps_per_hour,
            trials=trials,
            seed=seed,
        )

    # Chain error (all steps at same ε for this forecast).
    chain_err = compute_chain_error([epsilon] * total_steps)

    # Classify and compute multiplier.
    band = classify_band(prob)
    mult = compute_multiplier(prob)

    # Derate trust.
    derated = int(trust_score * mult)
    derated = max(0, min(1000, derated))

    # Effective horizon.
    horizon_frac = BAND_HORIZON_FRACTION.get(band, 1.0)
    eff_horizon = round(horizon_hours * horizon_frac, 1)

    return ForecastResult(
        avg_failure_prob=round(prob, 6),
        band=band,
        multiplier=round(mult, 6),
        derated_score=derated,
        raw_score=trust_score,
        horizon_hours=horizon_hours,
        effective_horizon_hours=eff_horizon,
        trials=trials if not use_analytical else 0,
        epsilon=epsilon,
        steps=total_steps,
        chain_error=round(chain_err, 6),
        requires_action=(band != ForecastBand.GREEN),
        details={
            "analytical": use_analytical,
            "horizon_fraction": horizon_frac,
        },
    )


def forecast_chain(
    trust_score: int,
    epsilons: list[float],
    horizon_hours: int = DEFAULT_HORIZON_HOURS,
    risk_score: float = 100.0,
) -> ForecastResult:
    """
    Forecast for a multi-agent chain with varying per-step ε.

    Each entry in ``epsilons`` represents one step's failure rate.
    Uses the chain error formula: ε_chain = 1 − ∏(1 − ε_i).

    Parameters
    ----------
    trust_score : int
        Current trust score.
    epsilons : list[float]
        Per-step failure rates for each step in the chain.
    horizon_hours : int
        Nominal horizon.
    risk_score : float
        Pre-action risk score.

    Returns
    -------
    ForecastResult
        Forecast result with chain error.
    """
    if risk_score < FORECAST_RISK_THRESHOLD:
        return ForecastResult(
            avg_failure_prob=0.0,
            band=ForecastBand.GREEN,
            multiplier=1.0,
            derated_score=trust_score,
            raw_score=trust_score,
            horizon_hours=horizon_hours,
            effective_horizon_hours=float(horizon_hours),
            trials=0,
            epsilon=0.0,
            steps=len(epsilons),
            chain_error=0.0,
            requires_action=False,
            details={"bypassed": True, "reason": "risk_below_threshold"},
        )

    chain_err = compute_chain_error(epsilons)
    band = classify_band(chain_err)
    mult = compute_multiplier(chain_err)
    derated = max(0, min(1000, int(trust_score * mult)))

    horizon_frac = BAND_HORIZON_FRACTION.get(band, 1.0)
    eff_horizon = round(horizon_hours * horizon_frac, 1)

    return ForecastResult(
        avg_failure_prob=round(chain_err, 6),
        band=band,
        multiplier=round(mult, 6),
        derated_score=derated,
        raw_score=trust_score,
        horizon_hours=horizon_hours,
        effective_horizon_hours=eff_horizon,
        trials=0,
        epsilon=statistics_mean(epsilons) if epsilons else 0.0,
        steps=len(epsilons),
        chain_error=round(chain_err, 6),
        requires_action=(band != ForecastBand.GREEN),
        details={
            "chain_epsilons": epsilons,
            "horizon_fraction": horizon_frac,
        },
    )


def statistics_mean(values: list[float]) -> float:
    """Safe mean that handles empty lists."""
    if not values:
        return 0.0
    return sum(values) / len(values)
