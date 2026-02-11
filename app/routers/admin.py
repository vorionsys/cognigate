"""
ADMIN endpoints - System monitoring and control.

These endpoints provide visibility into the security layers and
allow manual intervention when needed.

All admin endpoints require the X-Admin-Key header for authentication.
"""

import structlog
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.core.velocity import velocity_tracker, get_velocity_stats
from app.core.circuit_breaker import circuit_breaker, CircuitState
from app.core.auth import verify_admin_key

logger = structlog.get_logger()
router = APIRouter()


# ============================================================================
# CIRCUIT BREAKER ENDPOINTS
# ============================================================================

@router.get("/admin/circuit")
async def get_circuit_status(
    _: str = Depends(verify_admin_key),
) -> dict:
    """
    Get circuit breaker status.

    Returns current state, metrics, and trip history.
    """
    return circuit_breaker.get_status()


@router.get("/admin/circuit/history")
async def get_circuit_history(
    limit: int = 10,
    _: str = Depends(verify_admin_key),
) -> dict:
    """Get circuit breaker trip history."""
    return {
        "trips": circuit_breaker.get_trip_history(limit),
    }


class ManualHaltRequest(BaseModel):
    reason: str = "Manual halt via admin API"


@router.post("/admin/circuit/halt")
async def manual_circuit_halt(
    request: ManualHaltRequest,
    _: str = Depends(verify_admin_key),
) -> dict:
    """
    Manually trip the circuit breaker.

    This will block ALL requests until reset.
    Use with caution.
    """
    circuit_breaker.manual_trip(request.reason)
    logger.warning("admin_circuit_halt", reason=request.reason)
    return {
        "status": "halted",
        "reason": request.reason,
        "message": "Circuit breaker tripped. All requests will be blocked.",
    }


@router.post("/admin/circuit/reset")
async def manual_circuit_reset(
    _: str = Depends(verify_admin_key),
) -> dict:
    """
    Manually reset the circuit breaker.

    This will restore normal operation.
    """
    circuit_breaker.manual_reset()
    logger.info("admin_circuit_reset")
    return {
        "status": "reset",
        "message": "Circuit breaker reset. Normal operation restored.",
    }


# ============================================================================
# ENTITY CONTROL ENDPOINTS
# ============================================================================

class EntityHaltRequest(BaseModel):
    entity_id: str
    reason: str = "Manual halt via admin API"


@router.post("/admin/entity/halt")
async def halt_entity(
    request: EntityHaltRequest,
    _: str = Depends(verify_admin_key),
) -> dict:
    """
    Halt a specific entity.

    This entity will be blocked until manually unhalted.
    """
    circuit_breaker.halt_entity(request.entity_id, request.reason)
    logger.warning(
        "admin_entity_halt",
        entity_id=request.entity_id,
        reason=request.reason,
    )
    return {
        "status": "halted",
        "entity_id": request.entity_id,
        "reason": request.reason,
    }


class EntityUnhaltRequest(BaseModel):
    entity_id: str


@router.post("/admin/entity/unhalt")
async def unhalt_entity(
    request: EntityUnhaltRequest,
    _: str = Depends(verify_admin_key),
) -> dict:
    """
    Unhalt a specific entity.

    This will restore the entity's ability to make requests.
    """
    circuit_breaker.unhalt_entity(request.entity_id)
    logger.info("admin_entity_unhalt", entity_id=request.entity_id)
    return {
        "status": "unhalted",
        "entity_id": request.entity_id,
    }


class CascadeHaltRequest(BaseModel):
    parent_id: str
    reason: str = "Cascade halt via admin API"


@router.post("/admin/entity/cascade-halt")
async def cascade_halt_entity(
    request: CascadeHaltRequest,
    _: str = Depends(verify_admin_key),
) -> dict:
    """
    Halt a parent entity and all its registered children.

    Use this when a parent agent is misbehaving and you need
    to stop the entire agent tree.
    """
    circuit_breaker.cascade_halt(request.parent_id, request.reason)
    logger.warning(
        "admin_cascade_halt",
        parent_id=request.parent_id,
        reason=request.reason,
    )
    return {
        "status": "cascade_halted",
        "parent_id": request.parent_id,
        "reason": request.reason,
    }


# ============================================================================
# VELOCITY ENDPOINTS
# ============================================================================

@router.get("/admin/velocity")
async def get_all_velocity_stats(
    _: str = Depends(verify_admin_key),
) -> dict:
    """
    Get velocity statistics for all entities.
    """
    return {
        "entities": await velocity_tracker.get_all_stats(),
    }


@router.get("/admin/velocity/{entity_id}")
async def get_entity_velocity(
    entity_id: str,
    _: str = Depends(verify_admin_key),
) -> dict:
    """
    Get velocity statistics for a specific entity.
    """
    stats = await get_velocity_stats(entity_id)
    if stats["total_actions"] == 0:
        raise HTTPException(status_code=404, detail=f"No velocity data for entity {entity_id}")
    return stats


class ThrottleRequest(BaseModel):
    entity_id: str
    duration_seconds: float = 300  # 5 minutes default


@router.post("/admin/velocity/throttle")
async def throttle_entity(
    request: ThrottleRequest,
    _: str = Depends(verify_admin_key),
) -> dict:
    """
    Manually throttle an entity.

    This will block the entity for the specified duration,
    regardless of their actual velocity.
    """
    await velocity_tracker.throttle_entity(request.entity_id, request.duration_seconds)
    logger.warning(
        "admin_throttle",
        entity_id=request.entity_id,
        duration_seconds=request.duration_seconds,
    )
    return {
        "status": "throttled",
        "entity_id": request.entity_id,
        "duration_seconds": request.duration_seconds,
    }


@router.post("/admin/velocity/unthrottle")
async def unthrottle_entity(
    request: EntityUnhaltRequest,
    _: str = Depends(verify_admin_key),
) -> dict:
    """
    Remove throttle from an entity.
    """
    await velocity_tracker.unthrottle_entity(request.entity_id)
    logger.info("admin_unthrottle", entity_id=request.entity_id)
    return {
        "status": "unthrottled",
        "entity_id": request.entity_id,
    }


# ============================================================================
# SYSTEM STATUS ENDPOINT
# ============================================================================

@router.get("/admin/status")
async def get_system_status(
    _: str = Depends(verify_admin_key),
) -> dict:
    """
    Get comprehensive system status.

    Returns circuit breaker, velocity, and overall health status.
    """
    circuit_status = circuit_breaker.get_status()

    # Determine overall health
    if circuit_status["state"] == CircuitState.OPEN.value:
        health = "critical"
        health_message = "System is halted"
    elif circuit_status["state"] == CircuitState.HALF_OPEN.value:
        health = "degraded"
        health_message = "System is recovering"
    elif len(circuit_status["halted_entities"]) > 0:
        health = "warning"
        health_message = f"{len(circuit_status['halted_entities'])} entities halted"
    else:
        health = "healthy"
        health_message = "All systems operational"

    return {
        "health": health,
        "health_message": health_message,
        "circuit_breaker": circuit_status,
        "velocity": {
            "tracked_entities": len(velocity_tracker._states),
        },
        "security_layers": {
            "L0_burst": "active",
            "L1_sustained": "active",
            "L2_quota": "active",
            "L3_tripwires": "active",
            "L4_critic": "active (if API key set)",
            "L5_circuit_breaker": "active",
        },
    }
