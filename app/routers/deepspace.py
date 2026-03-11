# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Deep Space Operations Router.

Exposes the three deep-space-trajectory-level modules as REST endpoints:
  1. TMR Consensus  — /deepspace/consensus
  2. Monte Carlo    — /deepspace/forecast
  3. Self-Healing   — /deepspace/evolve

All endpoints require API key authentication.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import verify_api_key
from app.core.tmr_consensus import (
    ConsensusResult,
    DegradationLevel,
    ReplicaOutput,
    quick_consensus,
    vote,
    CONSENSUS_RISK_THRESHOLD,
)
from app.core.monte_carlo import (
    ForecastBand,
    ForecastResult,
    forecast,
    forecast_chain,
    analytical_failure_prob,
    DEFAULT_EPSILON,
    DEFAULT_HORIZON_HOURS,
    DEFAULT_TRIALS,
    FORECAST_RISK_THRESHOLD,
)
from app.core.self_healing import (
    BlendLevel,
    EvolutionResult,
    TrustParams,
    evolve,
    quick_evolve,
    validate_evolved_params,
    DEFAULT_TARGET_RATIO,
    DEFAULT_GENERATIONS,
    DEFAULT_POPULATION,
)

router = APIRouter()


# =============================================================================
# REQUEST / RESPONSE MODELS
# =============================================================================

# --- TMR Consensus ---

class ReplicaInput(BaseModel):
    replicaId: str
    trustScore: int = Field(ge=0, le=1000)
    activationHash: str = ""
    metadata: dict[str, Any] = {}


class ConsensusRequest(BaseModel):
    replicas: list[ReplicaInput] = Field(..., min_length=3)
    threshold: float = Field(default=10.0, gt=0)
    riskScore: float = Field(default=100.0, ge=0, le=100)


class ConsensusResponse(BaseModel):
    compositeScore: int
    consensusFactor: float
    degradationLevel: str
    tierCap: Optional[int]
    avgDivergence: float
    maxDivergence: float
    replicaCount: int
    requiresHumanReview: bool
    blocked: bool
    scores: list[int]


# --- Monte Carlo ---

class ForecastRequest(BaseModel):
    trustScore: int = Field(ge=0, le=1000)
    epsilon: float = Field(default=DEFAULT_EPSILON, gt=0, le=1)
    horizonHours: int = Field(default=DEFAULT_HORIZON_HOURS, gt=0, le=720)
    stepsPerHour: int = Field(default=1, gt=0, le=60)
    riskScore: float = Field(default=100.0, ge=0, le=100)
    useAnalytical: bool = True


class ChainForecastRequest(BaseModel):
    trustScore: int = Field(ge=0, le=1000)
    epsilons: list[float] = Field(..., min_length=1)
    horizonHours: int = Field(default=DEFAULT_HORIZON_HOURS, gt=0, le=720)
    riskScore: float = Field(default=100.0, ge=0, le=100)


class ForecastResponse(BaseModel):
    avgFailureProb: float
    band: str
    multiplier: float
    deratedScore: int
    rawScore: int
    horizonHours: int
    effectiveHorizonHours: float
    epsilon: float
    steps: int
    chainError: float
    requiresAction: bool


# --- Self-Healing ---

class EvolveRequest(BaseModel):
    rG: float = Field(default=0.05, gt=0)
    rL: float = Field(default=0.15, gt=0)
    targetRatio: float = Field(default=DEFAULT_TARGET_RATIO, gt=0)
    populationSize: int = Field(default=DEFAULT_POPULATION, ge=4, le=200)
    generations: int = Field(default=DEFAULT_GENERATIONS, ge=1, le=500)
    mutationRate: float = Field(default=0.08, ge=0, le=1)
    seed: Optional[int] = None
    requiresHumanVeto: bool = False


class EvolveResponse(BaseModel):
    bestRG: float
    bestRL: float
    bestFitness: float
    achievedRatio: float
    blendLevel: str
    blendFraction: float
    blendedRG: float
    blendedRL: float
    generationsRun: int
    targetRatio: float
    requiresHumanVeto: bool
    fitnessHistory: list[float]
    validationPassed: bool
    validationIssues: list[str]


# =============================================================================
# ROUTES
# =============================================================================

@router.post(
    "/deepspace/consensus",
    summary="TMR multi-model consensus vote",
    tags=["Deep Space"],
)
async def run_consensus(
    body: ConsensusRequest,
    _: str = Depends(verify_api_key),
) -> ConsensusResponse:
    """
    Run fault-tolerant multi-model consensus.

    Requires ≥3 replica outputs.  Computes pairwise divergences,
    applies exponential derating, and returns a composite trust
    score with degradation level and tier cap.

    If risk score is below the threshold (80), consensus is bypassed.
    """
    replicas = [
        ReplicaOutput(
            replica_id=r.replicaId,
            trust_score=r.trustScore,
            activation_hash=r.activationHash,
            metadata=r.metadata,
        )
        for r in body.replicas
    ]

    result = vote(
        replicas=replicas,
        threshold=body.threshold,
        risk_score=body.riskScore,
    )

    return ConsensusResponse(
        compositeScore=result.composite_score,
        consensusFactor=result.consensus_factor,
        degradationLevel=result.degradation_level.value,
        tierCap=result.tier_cap,
        avgDivergence=result.avg_divergence,
        maxDivergence=result.max_divergence,
        replicaCount=result.replica_count,
        requiresHumanReview=result.requires_human_review,
        blocked=result.blocked,
        scores=result.details.get("scores", []),
    )


@router.post(
    "/deepspace/forecast",
    summary="Monte Carlo risk forecast",
    tags=["Deep Space"],
)
async def run_forecast(
    body: ForecastRequest,
    _: str = Depends(verify_api_key),
) -> ForecastResponse:
    """
    Run Monte Carlo risk forecasting over a configurable horizon.

    Computes failure probability for a series of steps,
    applies tiered precautionary multiplier, and returns a
    derated trust score with forecast band and effective horizon.

    Uses analytical formula by default for deterministic results.
    """
    result = forecast(
        trust_score=body.trustScore,
        epsilon=body.epsilon,
        horizon_hours=body.horizonHours,
        steps_per_hour=body.stepsPerHour,
        risk_score=body.riskScore,
        use_analytical=body.useAnalytical,
    )

    return ForecastResponse(
        avgFailureProb=result.avg_failure_prob,
        band=result.band.value,
        multiplier=result.multiplier,
        deratedScore=result.derated_score,
        rawScore=result.raw_score,
        horizonHours=result.horizon_hours,
        effectiveHorizonHours=result.effective_horizon_hours,
        epsilon=result.epsilon,
        steps=result.steps,
        chainError=result.chain_error,
        requiresAction=result.requires_action,
    )


@router.post(
    "/deepspace/forecast/chain",
    summary="Monte Carlo chain forecast",
    tags=["Deep Space"],
)
async def run_chain_forecast(
    body: ChainForecastRequest,
    _: str = Depends(verify_api_key),
) -> ForecastResponse:
    """
    Forecast failure probability for a multi-agent chain with
    varying per-step failure rates (ε_i).

    Uses the chain error formula: ε_chain = 1 − ∏(1 − ε_i).
    """
    result = forecast_chain(
        trust_score=body.trustScore,
        epsilons=body.epsilons,
        horizon_hours=body.horizonHours,
        risk_score=body.riskScore,
    )

    return ForecastResponse(
        avgFailureProb=result.avg_failure_prob,
        band=result.band.value,
        multiplier=result.multiplier,
        deratedScore=result.derated_score,
        rawScore=result.raw_score,
        horizonHours=result.horizon_hours,
        effectiveHorizonHours=result.effective_horizon_hours,
        epsilon=result.epsilon,
        steps=result.steps,
        chainError=result.chain_error,
        requiresAction=result.requires_action,
    )


@router.post(
    "/deepspace/evolve",
    summary="Evolutionary parameter optimization",
    tags=["Deep Space"],
)
async def run_evolution(
    body: EvolveRequest,
    _: str = Depends(verify_api_key),
) -> EvolveResponse:
    """
    Run genetic algorithm to evolve trust parameters (r_g, r_l).

    Targets the specified asymmetry ratio (default 10:1).
    Returns evolved parameters with blend recommendation
    (FULL/PARTIAL/MINIMAL/REJECTED) and safety validation.
    """
    result = evolve(
        current_params=TrustParams(r_g=body.rG, r_l=body.rL),
        target_ratio=body.targetRatio,
        population_size=body.populationSize,
        generations=body.generations,
        mutation_rate=body.mutationRate,
        seed=body.seed,
        requires_human_veto=body.requiresHumanVeto,
    )

    # Validate evolved params.
    valid, issues = validate_evolved_params(result.best_params)

    return EvolveResponse(
        bestRG=round(result.best_params.r_g, 6),
        bestRL=round(result.best_params.r_l, 6),
        bestFitness=result.best_fitness,
        achievedRatio=result.achieved_ratio,
        blendLevel=result.blend_level.value,
        blendFraction=result.blend_fraction,
        blendedRG=round(result.blended_params.r_g, 6),
        blendedRL=round(result.blended_params.r_l, 6),
        generationsRun=result.generations_run,
        targetRatio=result.target_ratio,
        requiresHumanVeto=result.requires_human_veto,
        fitnessHistory=result.fitness_history,
        validationPassed=valid,
        validationIssues=issues,
    )


@router.get(
    "/deepspace/status",
    summary="Deep space module status",
    tags=["Deep Space"],
)
async def deepspace_status(
    _: str = Depends(verify_api_key),
) -> dict:
    """
    Return the status and configuration of all three deep-space modules.
    """
    return {
        "modules": {
            "tmr_consensus": {
                "enabled": True,
                "riskThreshold": CONSENSUS_RISK_THRESHOLD,
                "minReplicas": 3,
                "degradationLevels": [d.value for d in DegradationLevel],
            },
            "monte_carlo": {
                "enabled": True,
                "riskThreshold": FORECAST_RISK_THRESHOLD,
                "defaultEpsilon": DEFAULT_EPSILON,
                "defaultHorizonHours": DEFAULT_HORIZON_HOURS,
                "defaultTrials": DEFAULT_TRIALS,
                "bands": [b.value for b in ForecastBand],
            },
            "self_healing": {
                "enabled": True,
                "defaultTargetRatio": DEFAULT_TARGET_RATIO,
                "defaultGenerations": DEFAULT_GENERATIONS,
                "defaultPopulation": DEFAULT_POPULATION,
                "batchFrequencyHours": 168,
                "blendLevels": [b.value for b in BlendLevel],
            },
        },
        "version": "1.0.0",
        "codename": "Deep Space Trajectory",
    }
