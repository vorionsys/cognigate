# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Self-Healing Autonomy via Evolutionary Algorithms.

Inspired by adaptive systems in long-duration space probes (Voyager's
self-repair scripts, Perseverance's adaptive firmware), this module
uses genetic algorithms (GA) to iteratively evolve trust parameters
(e.g., ATD r_g / r_l penalty ratios) in a sandboxed environment.

Architecture:
  Observation Tier O4+ activates → snapshot current params →
  run GA in sandbox → validate evolved params via Monte Carlo sim →
  phase-apply (10% incremental blends) → monitor via Paramesphere →
  rollback if drift exceeds threshold.

The GA targets an asymmetry fitness function:
  fitness = 1 / (1 + |actual_ratio − target_ratio|)

where target_ratio is the desired r_l/r_g ratio (default 10:1,
matching Vorion's 2×-10× asymmetric penalty design).

Graceful degradation in parameter evolution:
  - Full apply:    fitness ≥ 0.95 — direct parameter update
  - Partial blend:  0.80 ≤ fitness < 0.95 — 50% blend with current
  - Minimal blend:  0.60 ≤ fitness < 0.80 — 10% blend
  - Reject:         fitness < 0.60 — no change, log for review

Batch frequency: Weekly (168h = 7 days), aligned with cooldown window.
Human veto: Required for T7 actions and any param touching TIER_FAILURE_MULTIPLIERS.
"""

from __future__ import annotations

import math
import random
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default target asymmetry ratio (r_l / r_g).
DEFAULT_TARGET_RATIO: float = 10.0

# Parameter bounds.
PARAM_MIN: float = 0.001
PARAM_MAX: float = 0.300

# GA defaults.
DEFAULT_POPULATION: int = 20
DEFAULT_GENERATIONS: int = 25
DEFAULT_MUTATION_RATE: float = 0.08
DEFAULT_MUTATION_SIGMA: float = 0.015
DEFAULT_CROSSOVER_RATE: float = 0.70
DEFAULT_ELITISM: int = 2

# Batch frequency in hours (7 days).
EVOLUTION_BATCH_HOURS: int = 168

# Blend thresholds.
BLEND_FULL_THRESHOLD: float = 0.95
BLEND_PARTIAL_THRESHOLD: float = 0.80
BLEND_MINIMAL_THRESHOLD: float = 0.60


class BlendLevel(str, Enum):
    """How much to blend evolved parameters into the live system."""
    FULL = "FULL"            # fitness ≥ 0.95 — direct update
    PARTIAL = "PARTIAL"      # fitness ∈ [0.80, 0.95) — 50% blend
    MINIMAL = "MINIMAL"      # fitness ∈ [0.60, 0.80) — 10% blend
    REJECTED = "REJECTED"    # fitness < 0.60 — no change


BLEND_FRACTIONS: dict[BlendLevel, float] = {
    BlendLevel.FULL: 1.00,
    BlendLevel.PARTIAL: 0.50,
    BlendLevel.MINIMAL: 0.10,
    BlendLevel.REJECTED: 0.00,
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TrustParams:
    """Trust parameters subject to evolutionary optimization."""
    r_g: float = 0.05   # Gain rate
    r_l: float = 0.15   # Loss rate

    @property
    def ratio(self) -> float:
        """Asymmetry ratio r_l / r_g."""
        if self.r_g <= 0:
            return float('inf')
        return self.r_l / self.r_g

    def blend(self, other: "TrustParams", fraction: float) -> "TrustParams":
        """
        Blend this param set with another.

        fraction=0.0 → keep self entirely.
        fraction=1.0 → use other entirely.
        """
        f = max(0.0, min(1.0, fraction))
        return TrustParams(
            r_g=self.r_g + f * (other.r_g - self.r_g),
            r_l=self.r_l + f * (other.r_l - self.r_l),
        )

    def clamped(self) -> "TrustParams":
        """Return a copy with values clamped to valid bounds."""
        return TrustParams(
            r_g=max(PARAM_MIN, min(PARAM_MAX, self.r_g)),
            r_l=max(PARAM_MIN, min(PARAM_MAX, self.r_l)),
        )


@dataclass
class Individual:
    """A single individual in the GA population."""
    params: TrustParams
    fitness: float = 0.0


@dataclass
class EvolutionResult:
    """Result of an evolutionary optimization run."""
    best_params: TrustParams
    best_fitness: float
    blend_level: BlendLevel
    blend_fraction: float
    blended_params: TrustParams
    original_params: TrustParams
    generations_run: int
    population_size: int
    target_ratio: float
    achieved_ratio: float
    fitness_history: list[float]   # best fitness per generation
    requires_human_veto: bool
    details: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Fitness functions
# ---------------------------------------------------------------------------

def asymmetry_fitness(
    params: TrustParams,
    target_ratio: float = DEFAULT_TARGET_RATIO,
) -> float:
    """
    Compute fitness based on how close the asymmetry ratio is to target.

    fitness = 1 / (1 + |actual_ratio − target_ratio|)

    Returns a value in (0, 1] where 1.0 is a perfect match.
    """
    if params.r_g <= 0:
        return 0.0
    actual = params.r_l / params.r_g
    return 1.0 / (1.0 + abs(actual - target_ratio))


def composite_fitness(
    params: TrustParams,
    target_ratio: float = DEFAULT_TARGET_RATIO,
    penalty_weight: float = 0.3,
) -> float:
    """
    Composite fitness that also penalizes extreme parameter values.

    Combines asymmetry fitness with a penalty for params near bounds.
    """
    base = asymmetry_fitness(params, target_ratio)

    # Penalty for params too close to bounds (0 or MAX).
    penalty = 0.0
    for v in [params.r_g, params.r_l]:
        if v < PARAM_MIN * 2:
            penalty += 0.5
        if v > PARAM_MAX * 0.9:
            penalty += 0.3
    penalty = min(penalty, 1.0)

    return base * (1.0 - penalty_weight * penalty)


# ---------------------------------------------------------------------------
# GA operators
# ---------------------------------------------------------------------------

def _random_params() -> TrustParams:
    """Generate random trust parameters within bounds."""
    return TrustParams(
        r_g=random.uniform(PARAM_MIN, PARAM_MAX),
        r_l=random.uniform(PARAM_MIN, PARAM_MAX),
    )


def _crossover(a: TrustParams, b: TrustParams) -> TrustParams:
    """Arithmetic crossover between two parent param sets."""
    alpha = random.random()
    return TrustParams(
        r_g=a.r_g * alpha + b.r_g * (1 - alpha),
        r_l=a.r_l * alpha + b.r_l * (1 - alpha),
    ).clamped()


def _mutate(
    p: TrustParams,
    rate: float = DEFAULT_MUTATION_RATE,
    sigma: float = DEFAULT_MUTATION_SIGMA,
) -> TrustParams:
    """Gaussian mutation of trust parameters."""
    r_g = p.r_g
    r_l = p.r_l
    if random.random() < rate:
        r_g += random.gauss(0, sigma)
    if random.random() < rate:
        r_l += random.gauss(0, sigma)
    return TrustParams(r_g=r_g, r_l=r_l).clamped()


def _tournament_select(
    population: list[Individual],
    tournament_size: int = 3,
) -> Individual:
    """Tournament selection for parent picking."""
    candidates = random.sample(population, min(tournament_size, len(population)))
    return max(candidates, key=lambda ind: ind.fitness)


# ---------------------------------------------------------------------------
# Main evolution function
# ---------------------------------------------------------------------------

def evolve(
    current_params: TrustParams | None = None,
    target_ratio: float = DEFAULT_TARGET_RATIO,
    population_size: int = DEFAULT_POPULATION,
    generations: int = DEFAULT_GENERATIONS,
    mutation_rate: float = DEFAULT_MUTATION_RATE,
    mutation_sigma: float = DEFAULT_MUTATION_SIGMA,
    crossover_rate: float = DEFAULT_CROSSOVER_RATE,
    elitism: int = DEFAULT_ELITISM,
    fitness_fn: Callable[[TrustParams], float] | None = None,
    seed: Optional[int] = None,
    requires_human_veto: bool = False,
) -> EvolutionResult:
    """
    Run genetic algorithm to evolve trust parameters.

    Parameters
    ----------
    current_params : TrustParams, optional
        Current live parameters (default: r_g=0.05, r_l=0.15).
    target_ratio : float
        Target asymmetry ratio (r_l / r_g).
    population_size : int
        Population size per generation.
    generations : int
        Number of generations to evolve.
    mutation_rate : float
        Per-gene mutation probability.
    mutation_sigma : float
        Standard deviation for Gaussian mutation.
    crossover_rate : float
        Probability of crossover vs. pure mutation.
    elitism : int
        Number of top individuals to carry forward unchanged.
    fitness_fn : Callable, optional
        Custom fitness function. Defaults to ``asymmetry_fitness``.
    seed : int, optional
        Random seed for reproducibility.
    requires_human_veto : bool
        Whether T7 or sensitive params require human approval.

    Returns
    -------
    EvolutionResult
        Best evolved parameters with blend recommendation.
    """
    if seed is not None:
        random.seed(seed)

    if current_params is None:
        current_params = TrustParams(r_g=0.05, r_l=0.15)

    original = deepcopy(current_params)

    if fitness_fn is None:
        fitness_fn = lambda p: asymmetry_fitness(p, target_ratio)

    # Initialize population.
    population: list[Individual] = []

    # Seed population with current params and random individuals.
    population.append(Individual(params=deepcopy(current_params)))
    for _ in range(population_size - 1):
        population.append(Individual(params=_random_params()))

    fitness_history: list[float] = []

    for gen in range(generations):
        # Evaluate fitness.
        for ind in population:
            ind.fitness = fitness_fn(ind.params)

        # Sort by fitness (descending).
        population.sort(key=lambda i: i.fitness, reverse=True)
        fitness_history.append(population[0].fitness)

        # Early termination if perfect fitness.
        if population[0].fitness >= 0.999:
            break

        # Create next generation.
        new_pop: list[Individual] = []

        # Elitism: carry forward top individuals.
        for i in range(min(elitism, len(population))):
            new_pop.append(Individual(params=deepcopy(population[i].params)))

        # Fill remaining slots with crossover/mutation.
        while len(new_pop) < population_size:
            if random.random() < crossover_rate:
                p1 = _tournament_select(population)
                p2 = _tournament_select(population)
                child_params = _crossover(p1.params, p2.params)
            else:
                parent = _tournament_select(population)
                child_params = deepcopy(parent.params)

            child_params = _mutate(child_params, mutation_rate, mutation_sigma)
            new_pop.append(Individual(params=child_params))

        population = new_pop

    # Final evaluation.
    for ind in population:
        ind.fitness = fitness_fn(ind.params)
    population.sort(key=lambda i: i.fitness, reverse=True)

    best = population[0]

    # Determine blend level.
    if best.fitness >= BLEND_FULL_THRESHOLD:
        blend_level = BlendLevel.FULL
    elif best.fitness >= BLEND_PARTIAL_THRESHOLD:
        blend_level = BlendLevel.PARTIAL
    elif best.fitness >= BLEND_MINIMAL_THRESHOLD:
        blend_level = BlendLevel.MINIMAL
    else:
        blend_level = BlendLevel.REJECTED

    blend_fraction = BLEND_FRACTIONS[blend_level]
    blended = original.blend(best.params, blend_fraction)

    return EvolutionResult(
        best_params=best.params.clamped(),
        best_fitness=round(best.fitness, 6),
        blend_level=blend_level,
        blend_fraction=blend_fraction,
        blended_params=blended.clamped(),
        original_params=original,
        generations_run=len(fitness_history),
        population_size=population_size,
        target_ratio=target_ratio,
        achieved_ratio=round(best.params.ratio, 4),
        fitness_history=[round(f, 4) for f in fitness_history],
        requires_human_veto=requires_human_veto,
        details={
            "mutation_rate": mutation_rate,
            "crossover_rate": crossover_rate,
            "elitism": elitism,
        },
    )


def quick_evolve(
    r_g: float = 0.05,
    r_l: float = 0.15,
    target_ratio: float = DEFAULT_TARGET_RATIO,
    generations: int = DEFAULT_GENERATIONS,
    seed: Optional[int] = None,
) -> EvolutionResult:
    """
    Convenience wrapper for running evolution with minimal args.
    """
    return evolve(
        current_params=TrustParams(r_g=r_g, r_l=r_l),
        target_ratio=target_ratio,
        generations=generations,
        seed=seed,
    )


def validate_evolved_params(
    evolved: TrustParams,
    max_ratio: float = 20.0,
    min_r_g: float = 0.01,
    min_r_l: float = 0.01,
) -> tuple[bool, list[str]]:
    """
    Validate evolved parameters against safety constraints.

    Returns
    -------
    tuple[bool, list[str]]
        (is_valid, list_of_issues)
    """
    issues: list[str] = []

    if evolved.r_g < min_r_g:
        issues.append(f"r_g ({evolved.r_g:.4f}) below minimum ({min_r_g})")
    if evolved.r_l < min_r_l:
        issues.append(f"r_l ({evolved.r_l:.4f}) below minimum ({min_r_l})")
    if evolved.ratio > max_ratio:
        issues.append(
            f"ratio ({evolved.ratio:.2f}) exceeds maximum ({max_ratio})"
        )
    if evolved.r_g > PARAM_MAX:
        issues.append(f"r_g ({evolved.r_g:.4f}) exceeds PARAM_MAX ({PARAM_MAX})")
    if evolved.r_l > PARAM_MAX:
        issues.append(f"r_l ({evolved.r_l:.4f}) exceeds PARAM_MAX ({PARAM_MAX})")

    return (len(issues) == 0, issues)
