# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
PROOF layer models - Immutable audit records.
"""

from typing import Optional, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime

from .common import generate_id, utc_now


class ProofRecord(BaseModel):
    """
    An immutable record of an enforcement decision.
    PROOF = Persistent Record of Operational Facts
    """

    proof_id: str = Field(default_factory=lambda: generate_id("prf_"))
    chain_position: int = Field(..., description="Position in the proof chain")

    # References
    intent_id: str = Field(..., description="Associated intent ID")
    verdict_id: str = Field(..., description="Associated verdict ID")
    entity_id: str = Field(..., description="Entity that requested the action")

    # The record
    action_type: str = Field(..., description="Type of action recorded")
    decision: Literal["allowed", "denied", "escalated", "modified"] = Field(...)

    # Inputs and outputs
    inputs_hash: str = Field(..., description="SHA-256 hash of inputs")
    outputs_hash: str = Field(..., description="SHA-256 hash of outputs")

    # Chain integrity
    previous_hash: str = Field(..., description="Hash of previous proof record")
    hash: str = Field(..., description="Hash of this record")
    signature: Optional[str] = Field(None, description="Digital signature")

    # Metadata
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProofQuery(BaseModel):
    """
    Query parameters for searching proof records.
    """

    entity_id: Optional[str] = None
    intent_id: Optional[str] = None
    verdict_id: Optional[str] = None
    decision: Optional[Literal["allowed", "denied", "escalated", "modified"]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = Field(100, ge=1, le=1000)
    offset: int = Field(0, ge=0)


class ProofVerification(BaseModel):
    """
    Result of verifying a proof record's integrity.
    """

    proof_id: str
    valid: bool = Field(..., description="Whether the proof record is valid")
    chain_valid: bool = Field(..., description="Whether the chain linkage is valid")
    signature_valid: Optional[bool] = Field(None, description="Whether the signature is valid")
    issues: list[str] = Field(default_factory=list, description="Any issues found")
    verified_at: datetime = Field(default_factory=utc_now)


class ProofStats(BaseModel):
    """
    Statistics about the proof ledger.
    """

    total_records: int
    chain_length: int
    last_record_at: Optional[datetime]
    records_by_decision: dict[str, int]
    chain_integrity: bool
