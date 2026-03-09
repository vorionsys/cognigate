# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Trust Management Router

Port of apps/cognigate-api/src/routes/trust.ts to Python/FastAPI.
Manages trust admission, scoring, signals, and revocation.
"""

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_api_key
from app.constants_bridge import (
    TIER_THRESHOLDS,
    TrustTier,
    score_to_tier,
)
from app.db import get_session
from app.db.models import TrustStateDB, TrustSignalDB

router = APIRouter()


# =============================================================================
# IN-MEMORY TRUST STORE
# =============================================================================

_trust_state: dict[str, dict[str, Any]] = {}
_trust_signals: dict[str, list[dict[str, Any]]] = {}


# =============================================================================
# REQUEST MODELS
# =============================================================================

class AdmitRequest(BaseModel):
    agentId: str
    name: str
    capabilities: list[str] = []
    observationTier: str = "GRAY_BOX"


class SignalRequest(BaseModel):
    type: str = Field(..., pattern="^(success|failure|violation|neutral)$")
    source: str
    weight: float = 0.5
    context: dict[str, Any] | None = None


class RevokeRequest(BaseModel):
    reason: str


# =============================================================================
# SIGNAL WEIGHTS
# =============================================================================

SIGNAL_WEIGHTS = {
    "success": 1.0,
    "neutral": 0.0,
    "failure": -1.0,
    "violation": -3.0,
}

# Tier-scaled failure multipliers.
# Lower tiers are more lenient so new agents can ascend more easily.
# Multiplier grows with trust level — earning trust is hard to lose at T0,
# but a high-trust agent pays a steep price for any failure.
TIER_FAILURE_MULTIPLIERS: dict[int, float] = {
    0: 2.0,   # T0 Sandbox      — very lenient, aids ascension
    1: 3.0,   # T1 Observed
    2: 4.0,   # T2 Provisional
    3: 5.0,   # T3 Monitored
    4: 7.0,   # T4 Standard
    5: 10.0,  # T5 Trusted
    6: 10.0,  # T6 Certified
    7: 10.0,  # T7 Autonomous
}


# =============================================================================
# ROUTES
# =============================================================================

@router.post("/trust/admit", summary="Admit agent (establish Gate Trust)")
async def admit_agent(
    body: AdmitRequest,
    _: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Admit an agent into the trust system, establishing initial Gate Trust.

    The initial score and tier are determined by the observation tier:
    - **BLACK_BOX**: Score 100 → T0 Sandbox (ceiling: T2)
    - **GRAY_BOX**: Score 200 → T1 Observed (ceiling: T4)
    - **WHITE_BOX**: Score 350 → T2 Provisional (ceiling: T7)
    """
    initial_scores = {
        "BLACK_BOX": 100,
        "GRAY_BOX": 200,
        "WHITE_BOX": 350,
    }
    ceilings = {
        "BLACK_BOX": TrustTier.T2_PROVISIONAL,
        "GRAY_BOX": TrustTier.T4_STANDARD,
        "WHITE_BOX": TrustTier.T7_AUTONOMOUS,
    }

    initial_score = initial_scores.get(body.observationTier, 200)
    ceiling = ceilings.get(body.observationTier, TrustTier.T4_STANDARD)
    initial_tier = score_to_tier(initial_score)

    _trust_state[body.agentId] = {
        "agentId": body.agentId,
        "name": body.name,
        "score": initial_score,
        "tier": initial_tier,
        "ceiling": ceiling,
        "capabilities": body.capabilities,
        "observationTier": body.observationTier,
        "isRevoked": False,
        "admittedAt": datetime.utcnow().isoformat(),
    }
    _trust_signals[body.agentId] = []

    # Persist to database
    db_state = TrustStateDB(
        agent_id=body.agentId,
        name=body.name,
        score=initial_score,
        tier=initial_tier,
        ceiling=ceiling,
        capabilities=json.dumps(body.capabilities),
        observation_tier=body.observationTier,
    )
    session.add(db_state)
    # session commits via get_session context manager

    return {
        "admitted": True,
        "initialTier": initial_tier,
        "initialScore": initial_score,
        "observationCeiling": ceiling,
        "capabilities": body.capabilities,
        "expiresAt": None,
        "reason": None,
    }


@router.get("/trust/tiers", summary="Get tier definitions", include_in_schema=True)
async def get_tiers() -> dict:
    """
    Get all trust tier definitions (delegates to reference/tiers).
    """
    tiers = []
    for tier_enum in TrustTier:
        threshold = TIER_THRESHOLDS[tier_enum]
        tiers.append({
            "tier": tier_enum.value,
            "code": f"T{tier_enum.value}",
            **threshold,
        })
    return {"tiers": tiers}


@router.get("/trust/{agent_id}", summary="Get current trust status")
async def get_trust(
    agent_id: str,
    _: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Get the current trust score, tier, and observation ceiling for an agent.
    """
    # Try in-memory first, then database
    info = _trust_state.get(agent_id)
    if not info:
        result = await session.execute(
            select(TrustStateDB).where(TrustStateDB.agent_id == agent_id)
        )
        db_state = result.scalar_one_or_none()
        if db_state:
            # Hydrate in-memory cache from DB
            info = {
                "agentId": db_state.agent_id,
                "name": db_state.name,
                "score": db_state.score,
                "tier": score_to_tier(db_state.score),
                "ceiling": TrustTier(db_state.ceiling),
                "capabilities": json.loads(db_state.capabilities or "[]"),
                "observationTier": db_state.observation_tier,
                "isRevoked": bool(db_state.is_revoked),
                "admittedAt": db_state.admitted_at.isoformat(),
            }
            _trust_state[agent_id] = info

    if not info:
        return {
            "agentId": agent_id,
            "message": "Agent not admitted. Use POST /trust/admit first.",
            "score": None,
            "tier": None,
        }

    tier_info = TIER_THRESHOLDS[info["tier"]]
    return {
        "agentId": agent_id,
        "score": info["score"],
        "tier": info["tier"],
        "tierName": tier_info["name"],
        "observationCeiling": info["ceiling"],
        "isRevoked": info["isRevoked"],
        "lastUpdated": datetime.utcnow().isoformat(),
    }


@router.post("/trust/{agent_id}/signal", summary="Record trust signal")
async def record_signal(
    agent_id: str,
    body: SignalRequest,
    _: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Record a trust signal for an agent (success, failure, violation, or neutral).

    Signals adjust the agent's trust score:
    - **success**: +weight (positive)
    - **neutral**: no change
    - **failure**: -weight (negative)
    - **violation**: -3x weight (severe negative)
    """
    info = _trust_state.get(agent_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"Agent not admitted: {agent_id}")

    if info["isRevoked"]:
        raise HTTPException(status_code=403, detail="Agent is revoked")

    score_before = info["score"]
    current_tier = int(info["tier"])
    direction = SIGNAL_WEIGHTS.get(body.type, 0.0)
    if body.type == "failure" and direction < 0:
        # Scale penalty by tier: lower tiers get smaller multipliers to aid ascension
        tier_mult = TIER_FAILURE_MULTIPLIERS.get(current_tier, 2.0)
        delta = -int(body.weight * 50 * tier_mult)
    else:
        delta = int(direction * body.weight * 50)

    # Apply score change, clamped to [0, 1000]
    new_score = max(0, min(1000, score_before + delta))

    # Apply observation ceiling
    ceiling = info["ceiling"]
    ceiling_max = TIER_THRESHOLDS[ceiling]["max"]
    new_score = min(new_score, ceiling_max)

    new_tier = score_to_tier(new_score)
    info["score"] = new_score
    info["tier"] = new_tier

    # Record signal history
    signal_record = {
        "type": body.type,
        "source": body.source,
        "weight": body.weight,
        "delta": delta,
        "context": body.context,
        "timestamp": datetime.utcnow().isoformat(),
    }
    _trust_signals.setdefault(agent_id, []).append(signal_record)

    # Persist signal to database
    db_signal = TrustSignalDB(
        agent_id=agent_id,
        signal_type=body.type,
        source=body.source,
        weight=body.weight,
        delta=delta,
        context_json=json.dumps(body.context) if body.context else None,
    )
    session.add(db_signal)

    # Update trust state in DB
    result = await session.execute(
        select(TrustStateDB).where(TrustStateDB.agent_id == agent_id)
    )
    db_state = result.scalar_one_or_none()
    if db_state:
        db_state.score = new_score
        db_state.tier = new_tier

    tier_info = TIER_THRESHOLDS[new_tier]
    return {
        "accepted": True,
        "scoreBefore": score_before,
        "scoreAfter": new_score,
        "change": new_score - score_before,
        "newTier": new_tier,
        "newTierName": tier_info["name"],
    }


@router.post("/trust/{agent_id}/revoke", summary="Revoke agent trust")
async def revoke_trust(
    agent_id: str,
    body: RevokeRequest,
    _: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """
    Revoke an agent's trust, setting its score to 0 and marking it as revoked.
    """
    info = _trust_state.get(agent_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"Agent not admitted: {agent_id}")

    info["score"] = 0
    info["tier"] = TrustTier.T0_SANDBOX
    info["isRevoked"] = True

    # Persist revocation to database
    result = await session.execute(
        select(TrustStateDB).where(TrustStateDB.agent_id == agent_id)
    )
    db_state = result.scalar_one_or_none()
    if db_state:
        db_state.score = 0
        db_state.tier = TrustTier.T0_SANDBOX
        db_state.is_revoked = True

    return {
        "revoked": True,
        "agentId": agent_id,
        "reason": body.reason,
    }


@router.get("/trust/{agent_id}/history", summary="Trust signal history")
async def get_trust_history(agent_id: str, limit: int = 50, _: str = Depends(verify_api_key)) -> dict:
    """
    Get the trust signal history for an agent.
    """
    signals = _trust_signals.get(agent_id, [])
    recent = signals[-limit:] if limit else signals

    return {
        "agentId": agent_id,
        "count": len(recent),
        "signals": list(reversed(recent)),
    }
