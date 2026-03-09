# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Evidence Schema Models — PROOF Ledger Compliance Evidence Layer.

Maps immutable proof chain records to compliance framework controls,
enabling automated audit evidence generation and real-time compliance
health monitoring.

Supported frameworks:
- NIST 800-53 Rev 5
- EU AI Act
- ISO/IEC 42001
- SOC 2 Type II
- NIST AI RMF 1.0
- CMMC 2.0
- GDPR
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime

from .common import generate_id, utc_now


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

EvidenceType = Literal[
    "log",
    "metric",
    "attestation",
    "configuration",
    "test_result",
]

EvidenceCategory = Literal[
    "access_control",
    "audit",
    "risk_assessment",
    "incident_response",
    "system_integrity",
    "transparency",
    "accountability",
    "data_governance",
    "identity_management",
    "configuration_management",
]

ComplianceStatus = Literal[
    "satisfies",
    "partially_satisfies",
    "supports",
]

ControlStatus = Literal[
    "compliant",
    "non_compliant",
    "degraded",
    "unknown",
]

SatisfactionLevel = Literal[
    "full",
    "partial",
    "supporting",
]

Framework = Literal[
    "NIST-800-53",
    "EU-AI-ACT",
    "ISO-42001",
    "SOC-2",
    "NIST-AI-RMF",
    "CMMC",
    "GDPR",
]


# ---------------------------------------------------------------------------
# Core evidence models
# ---------------------------------------------------------------------------

class ControlMapping(BaseModel):
    """
    Maps a single proof event to a specific compliance control.

    Used within EvidenceChainEvent to declare which controls a given
    proof record satisfies and at what level.
    """

    control_id: str = Field(
        ...,
        description="Control identifier, e.g. 'AC-3', 'Article-9', 'CC6.1'",
    )
    framework: Framework = Field(
        ...,
        description="Compliance framework this control belongs to",
    )
    evidence_type: EvidenceType = Field(
        ...,
        description="Type of evidence this mapping represents",
    )
    satisfaction_level: SatisfactionLevel = Field(
        ...,
        description="How fully this event satisfies the control",
    )


class ControlEvidence(BaseModel):
    """
    Links a proof record to the compliance control it satisfies.

    Each ControlEvidence record is an immutable attestation that a
    specific proof chain event provides evidence for a specific
    compliance control. These records are the primary audit artifact.
    """

    evidence_id: str = Field(
        default_factory=lambda: generate_id("evi_"),
        description="Unique evidence identifier",
    )
    proof_id: str = Field(
        ...,
        description="Links to the originating ProofRecord",
    )
    control_id: str = Field(
        ...,
        description="Control identifier, e.g. 'AC-3', 'Article-9'",
    )
    framework: Framework = Field(
        ...,
        description="Compliance framework",
    )
    evidence_type: EvidenceType = Field(
        ...,
        description="Classification of the evidence",
    )
    evidence_category: EvidenceCategory = Field(
        ...,
        description="Broad category for grouping and filtering",
    )
    description: str = Field(
        ...,
        description="Human-readable description of what this evidence proves",
    )
    compliance_status: ComplianceStatus = Field(
        ...,
        description="How fully this evidence satisfies the control",
    )
    collected_at: datetime = Field(
        default_factory=utc_now,
        description="UTC timestamp when evidence was collected",
    )
    retention_expires: datetime = Field(
        ...,
        description="Retention expiry based on framework requirements",
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Additional context (entity_id, intent_id, etc.)",
    )


class ControlHealthStatus(BaseModel):
    """
    Runtime health status of a specific compliance control.

    Computed from the aggregate of ControlEvidence records for the
    control within a lookback window.
    """

    control_id: str = Field(
        ...,
        description="Control identifier",
    )
    framework: Framework = Field(
        ...,
        description="Compliance framework",
    )
    status: ControlStatus = Field(
        ...,
        description="Current compliance status of the control",
    )
    last_evidence_at: Optional[datetime] = Field(
        None,
        description="When the most recent evidence was collected",
    )
    evidence_count: int = Field(
        0,
        description="Total evidence records for this control",
    )
    issues: list[str] = Field(
        default_factory=list,
        description="Active issues affecting compliance status",
    )
    remediation: Optional[str] = Field(
        None,
        description="Recommended remediation action if non-compliant",
    )


class ComplianceSnapshot(BaseModel):
    """
    Point-in-time compliance status across all controls for a framework.

    Generated on demand or periodically and stored for historical
    compliance trending.
    """

    snapshot_id: str = Field(
        default_factory=lambda: generate_id("snap_"),
        description="Unique snapshot identifier",
    )
    timestamp: datetime = Field(
        default_factory=utc_now,
        description="When this snapshot was generated",
    )
    framework: Framework = Field(
        ...,
        description="Compliance framework this snapshot covers",
    )
    total_controls: int = Field(
        ...,
        description="Total controls assessed",
    )
    compliant: int = Field(
        ...,
        description="Number of compliant controls",
    )
    non_compliant: int = Field(
        ...,
        description="Number of non-compliant controls",
    )
    degraded: int = Field(
        ...,
        description="Number of degraded controls",
    )
    unknown: int = Field(
        ...,
        description="Number of controls with unknown status",
    )
    controls: list[ControlHealthStatus] = Field(
        default_factory=list,
        description="Per-control health breakdown",
    )

    @property
    def compliance_ratio(self) -> float:
        """Fraction of controls that are fully compliant."""
        if self.total_controls == 0:
            return 0.0
        return self.compliant / self.total_controls


class EvidenceChainEvent(BaseModel):
    """
    Extended proof record enriched with evidence metadata.

    Combines the immutable proof chain fields with cryptographic
    context and compliance control mappings. This is the primary
    record consumed by external audit systems.
    """

    # --- Fields mirrored from ProofRecord ---
    proof_id: str = Field(..., description="Proof record identifier")
    chain_position: int = Field(..., description="Position in the proof chain")
    intent_id: str = Field(..., description="Associated intent ID")
    verdict_id: str = Field(..., description="Associated verdict ID")
    entity_id: str = Field(..., description="Entity that requested the action")
    action_type: str = Field(..., description="Proof event type")
    decision: str = Field(..., description="Enforcement decision")
    inputs_hash: str = Field(..., description="SHA-256 hash of inputs")
    outputs_hash: str = Field(..., description="SHA-256 hash of outputs")

    # --- Evidence-specific fields ---
    execution_hash: str = Field(
        ...,
        description="SHA-256 hash of the full execution payload",
    )
    policy_hash: str = Field(
        ...,
        description="SHA-256 hash of the active policy set at execution time",
    )
    actor_identity: str = Field(
        ...,
        description="Verified entity identity (Ed25519 public key or entity_id)",
    )
    timestamp_utc: datetime = Field(
        default_factory=utc_now,
        description="Canonical UTC timestamp for the event",
    )
    previous_hash: str = Field(
        ...,
        description="Hash of the preceding proof record in the chain",
    )
    hash: str = Field(
        ...,
        description="Hash of this record",
    )
    signature: Optional[str] = Field(
        None,
        description="Ed25519 digital signature",
    )
    control_mappings: list[ControlMapping] = Field(
        default_factory=list,
        description="Compliance controls this event satisfies",
    )


class EvidenceQuery(BaseModel):
    """
    Query parameters for searching evidence records.
    """

    proof_id: Optional[str] = None
    control_id: Optional[str] = None
    framework: Optional[Framework] = None
    evidence_type: Optional[EvidenceType] = None
    evidence_category: Optional[EvidenceCategory] = None
    compliance_status: Optional[ComplianceStatus] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)
