"""
Agent Management Router

Port of apps/cognigate-api/src/routes/agents.ts to Python/FastAPI.
Provides CRUD operations for agent registration within the Gate Trust model.
"""

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.constants_bridge import (
    TIER_THRESHOLDS,
    TrustTier,
    score_to_tier,
)
from app.models.common import generate_id

router = APIRouter()


# =============================================================================
# IN-MEMORY AGENT STORE
# =============================================================================

_agents: dict[str, dict[str, Any]] = {}


# =============================================================================
# REQUEST / RESPONSE MODELS
# =============================================================================

class RegisterAgentRequest(BaseModel):
    agentId: str | None = None
    name: str
    capabilities: list[str] = []
    observationTier: str = "GRAY_BOX"


class UpdateAgentRequest(BaseModel):
    name: str | None = None
    capabilities: list[str] | None = None


# =============================================================================
# ROUTES
# =============================================================================

@router.post("/agents", status_code=201, summary="Register a new agent")
async def register_agent(body: RegisterAgentRequest) -> dict:
    """
    Register a new agent through Gate Trust admission.

    Creates the agent with an initial trust score based on its observation tier:
    - **BLACK_BOX**: Score 100 (T0 Sandbox)
    - **GRAY_BOX**: Score 200 (T1 Observed)
    - **WHITE_BOX**: Score 350 (T2 Provisional)
    """
    agent_id = body.agentId or generate_id("agent_")

    if agent_id in _agents and not _agents[agent_id].get("isRevoked"):
        raise HTTPException(status_code=409, detail="Agent already exists")

    # Determine initial score by observation tier
    initial_scores = {
        "BLACK_BOX": 100,
        "GRAY_BOX": 200,
        "WHITE_BOX": 350,
    }
    initial_score = initial_scores.get(body.observationTier, 200)
    initial_tier = score_to_tier(initial_score)
    tier_info = TIER_THRESHOLDS[initial_tier]

    # Observation ceiling limits max tier by observation transparency
    ceilings = {
        "BLACK_BOX": TrustTier.T2_PROVISIONAL,
        "GRAY_BOX": TrustTier.T4_STANDARD,
        "WHITE_BOX": TrustTier.T7_AUTONOMOUS,
    }
    ceiling = ceilings.get(body.observationTier, TrustTier.T4_STANDARD)

    now = datetime.utcnow()
    expires_at = now + timedelta(days=1)

    agent = {
        "agentId": agent_id,
        "name": body.name,
        "capabilities": body.capabilities,
        "observationTier": body.observationTier,
        "score": initial_score,
        "tier": initial_tier,
        "observationCeiling": ceiling,
        "admittedAt": now.isoformat(),
        "expiresAt": expires_at.isoformat(),
        "lastActivityAt": now.isoformat(),
        "isRevoked": False,
    }
    _agents[agent_id] = agent

    return {
        "agentId": agent_id,
        "name": body.name,
        "capabilities": body.capabilities,
        "observationTier": body.observationTier,
        "trustScore": initial_score,
        "trustTier": initial_tier,
        "trustTierName": tier_info["name"],
        "observationCeiling": ceiling,
        "expiresAt": expires_at.isoformat(),
        "registeredAt": now.isoformat(),
    }


@router.get("/agents", summary="List all agents")
async def list_agents(limit: int = 100, tier: int | None = None) -> list[dict]:
    """
    List all active (non-revoked) agents.

    Optional filters:
    - **limit**: Max number of results (default 100)
    - **tier**: Filter by trust tier (0-7)
    """
    agents = [a for a in _agents.values() if not a.get("isRevoked")]

    if tier is not None:
        agents = [a for a in agents if a["tier"] == tier]

    results = []
    for agent in agents[:limit]:
        tier_info = TIER_THRESHOLDS[agent["tier"]]
        results.append({
            "agentId": agent["agentId"],
            "name": agent["name"],
            "trustScore": agent["score"],
            "trustTier": agent["tier"],
            "trustTierName": tier_info["name"],
            "isRevoked": agent["isRevoked"],
        })

    return results


@router.get("/agents/{agent_id}", summary="Get agent details")
async def get_agent(agent_id: str) -> dict:
    """
    Get detailed information for a single agent including trust info.
    """
    agent = _agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    tier_info = TIER_THRESHOLDS[agent["tier"]]
    return {
        "agentId": agent["agentId"],
        "name": agent["name"],
        "capabilities": agent["capabilities"],
        "observationTier": agent["observationTier"],
        "trustScore": agent["score"],
        "trustTier": agent["tier"],
        "trustTierName": tier_info["name"],
        "observationCeiling": agent["observationCeiling"],
        "isRevoked": agent["isRevoked"],
        "admittedAt": agent["admittedAt"],
        "lastActivityAt": agent["lastActivityAt"],
    }


@router.patch("/agents/{agent_id}", summary="Update agent")
async def update_agent(agent_id: str, body: UpdateAgentRequest) -> dict:
    """
    Update agent name and/or capabilities.
    """
    agent = _agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    if body.name is not None:
        agent["name"] = body.name
    if body.capabilities is not None:
        agent["capabilities"] = body.capabilities

    agent["lastActivityAt"] = datetime.utcnow().isoformat()

    return {
        "agentId": agent_id,
        "name": agent["name"],
        "capabilities": agent["capabilities"],
        "updatedAt": agent["lastActivityAt"],
    }


@router.delete("/agents/{agent_id}", status_code=204, summary="Revoke agent")
async def delete_agent(agent_id: str) -> None:
    """
    Revoke an agent, removing its trust and access.
    """
    agent = _agents.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    agent["isRevoked"] = True
    agent["lastActivityAt"] = datetime.utcnow().isoformat()
