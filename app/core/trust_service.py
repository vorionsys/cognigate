"""
Trust service — resolves entity trust scores from the database.

Queries the trust_state table for real trust data instead of
returning hardcoded mocks.  Includes a simple in-memory cache
with a configurable TTL to avoid hitting the DB on every intent.
"""

import time

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.db.models import TrustStateDB
from app.models.common import TrustLevel

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Simple in-memory cache: entity_id -> (score, level, cached_at_epoch)
# ---------------------------------------------------------------------------
_cache: dict[str, tuple[int, int, float]] = {}
_CACHE_TTL = 30.0  # seconds


def invalidate_cache(entity_id: str | None = None) -> None:
    """
    Invalidate the trust cache for one entity, or flush it entirely.

    Useful after trust signals update a score so the next lookup
    picks up the new value immediately.
    """
    if entity_id is None:
        _cache.clear()
    else:
        _cache.pop(entity_id, None)


async def get_trust_score(entity_id: str) -> tuple[int, TrustLevel]:
    """
    Resolve trust score and tier for *entity_id* from the database.

    Returns
    -------
    tuple[int, TrustLevel]
        (score, tier) — score is 0-1000, tier is 0-7.
        Falls back to (200, 1) for unknown entities or on DB errors.
    """
    now = time.time()

    # --- Check cache ---
    if entity_id in _cache:
        score, level, cached_at = _cache[entity_id]
        if now - cached_at < _CACHE_TTL:
            return score, level  # type: ignore[return-value]

    # --- Query the database ---
    try:
        async for session in get_session():
            result = await session.execute(
                select(TrustStateDB).where(TrustStateDB.agent_id == entity_id)
            )
            trust_state = result.scalar_one_or_none()

            if trust_state:
                score = trust_state.score
                # Clamp tier into the valid TrustLevel range 0-7
                level = max(0, min(trust_state.tier, 7))
                _cache[entity_id] = (score, level, time.time())
                logger.debug(
                    "trust_resolved",
                    entity_id=entity_id,
                    score=score,
                    tier=level,
                )
                return score, level  # type: ignore[return-value]
    except Exception:
        logger.exception("trust_lookup_failed", entity_id=entity_id)

    # --- Default for unknown / failed lookups ---
    default_score, default_level = 200, 1
    _cache[entity_id] = (default_score, default_level, time.time())
    return default_score, default_level  # type: ignore[return-value]
