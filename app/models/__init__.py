"""
Pydantic models for the Cognigate Engine.
"""

from .intent import IntentRequest, IntentResponse, StructuredPlan
from .enforce import EnforceRequest, EnforceResponse, PolicyViolation
from .proof import ProofRecord, ProofQuery, ProofVerification
from .critic import CriticVerdict, CriticRequest, CriticConfig
from .common import TrustLevel, TrustScore, EntityId
from .compliance import (
    ComplianceHealthResponse,
    ControlHealthStatus,
    FrameworkHealth,
    ControlAlert,
    ComplianceSnapshot,
    ComplianceDashboardResponse,
)
from .evidence import (
    ControlEvidence,
    ControlMapping,
    EvidenceChainEvent,
    EvidenceQuery,
)
from .evidence import (
    ControlHealthStatus as EvidenceControlHealth,
    ComplianceSnapshot as EvidenceComplianceSnapshot,
)

__all__ = [
    "IntentRequest",
    "IntentResponse",
    "StructuredPlan",
    "EnforceRequest",
    "EnforceResponse",
    "PolicyViolation",
    "ProofRecord",
    "ProofQuery",
    "ProofVerification",
    "CriticVerdict",
    "CriticRequest",
    "CriticConfig",
    "TrustLevel",
    "TrustScore",
    "EntityId",
    # Compliance API response models
    "ComplianceHealthResponse",
    "ControlHealthStatus",
    "FrameworkHealth",
    "ControlAlert",
    "ComplianceSnapshot",
    "ComplianceDashboardResponse",
    # Evidence layer models
    "ControlEvidence",
    "ControlMapping",
    "EvidenceChainEvent",
    "EvidenceQuery",
    "EvidenceControlHealth",
    "EvidenceComplianceSnapshot",
]
