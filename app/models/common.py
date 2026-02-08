"""
Common types and models used across the Cognigate Engine.
"""

from typing import Literal, Annotated
from pydantic import BaseModel, Field
import uuid
from datetime import datetime


# Type aliases
TrustLevel = Literal[0, 1, 2, 3, 4, 5, 6, 7]
TrustScore = Annotated[int, Field(ge=0, le=1000)]
EntityId = str

# Trust level metadata — canonical 8-tier model (T0-T7)
TRUST_LEVELS = {
    0: {"name": "Sandbox", "min_score": 0, "max_score": 199},
    1: {"name": "Observed", "min_score": 200, "max_score": 349},
    2: {"name": "Provisional", "min_score": 350, "max_score": 499},
    3: {"name": "Monitored", "min_score": 500, "max_score": 649},
    4: {"name": "Standard", "min_score": 650, "max_score": 799},
    5: {"name": "Trusted", "min_score": 800, "max_score": 875},
    6: {"name": "Certified", "min_score": 876, "max_score": 950},
    7: {"name": "Autonomous", "min_score": 951, "max_score": 1000},
}


def generate_id(prefix: str = "") -> str:
    """Generate a unique ID with optional prefix."""
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def utc_now() -> datetime:
    """Get current UTC timestamp."""
    return datetime.utcnow()


class BaseResponse(BaseModel):
    """Base response model with common fields."""

    request_id: str = Field(default_factory=lambda: generate_id("req_"))
    timestamp: datetime = Field(default_factory=utc_now)
    version: str = "1.0"
