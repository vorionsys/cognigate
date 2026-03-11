# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
PROOF endpoints - Immutable audit ledger.

PROOF = Persistent Record of Operational Facts

The PROOF layer creates and maintains cryptographically sealed records
of all governance decisions for audit and compliance.
"""

import hashlib
import json
import structlog
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_api_key
from app.models.proof import ProofRecord, ProofQuery, ProofVerification, ProofStats, ProofRequest
from app.models.common import generate_id
from app.db import get_session, ProofRepository
from app.core.signatures import sign_proof_record, verify_proof_signature
from app.core.evidence_hook import on_proof_created

logger = structlog.get_logger()
router = APIRouter()

# Map enforcement actions to proof decisions (verb -> past participle)
ACTION_TO_DECISION = {
    "allow": "allowed",
    "deny": "denied",
    "escalate": "escalated",
    "modify": "modified",
}


def calculate_hash(data: dict) -> str:
    """Calculate SHA-256 hash of data."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


async def create_proof_record(
    session: AsyncSession,
    intent_id: str,
    verdict_id: str,
    entity_id: str,
    action_type: str,
    decision: str,
    inputs: dict,
    outputs: dict,
) -> ProofRecord:
    """
    Create a new proof record and add it to the chain.
    """
    repo = ProofRepository(session)

    # Atomically read chain state under row-level lock (PostgreSQL) to prevent
    # concurrent appends from reading the same chain position.
    last_hash, chain_length = await repo.get_chain_state_for_append()

    inputs_hash = calculate_hash(inputs)
    outputs_hash = calculate_hash(outputs)

    record = ProofRecord(
        chain_position=chain_length,
        intent_id=intent_id,
        verdict_id=verdict_id,
        entity_id=entity_id,
        action_type=action_type,
        decision=decision,
        inputs_hash=inputs_hash,
        outputs_hash=outputs_hash,
        previous_hash=last_hash,
        hash="",  # Calculated below
    )

    # Calculate record hash
    record_data = {
        "proof_id": record.proof_id,
        "chain_position": record.chain_position,
        "intent_id": record.intent_id,
        "verdict_id": record.verdict_id,
        "entity_id": record.entity_id,
        "action_type": record.action_type,
        "decision": record.decision,
        "inputs_hash": record.inputs_hash,
        "outputs_hash": record.outputs_hash,
        "previous_hash": record.previous_hash,
        "created_at": record.created_at.isoformat(),
    }
    record.hash = calculate_hash(record_data)

    # Sign the record (includes hash in signature)
    record.signature = sign_proof_record(record_data)

    # Persist to database
    await repo.create(record)

    logger.info(
        "proof_created",
        proof_id=record.proof_id,
        chain_position=record.chain_position,
        decision=decision,
    )

    # Generate compliance evidence from the proof record.
    # Wrapped in try/except so evidence generation failures never block
    # proof chain operations — proof creation is primary, evidence is
    # supplementary.
    try:
        await on_proof_created(record, session)
    except Exception:
        logger.exception(
            "evidence_hook_call_failed",
            proof_id=record.proof_id,
            chain_position=record.chain_position,
            action_type=record.action_type,
            decision=record.decision,
        )

    return record


@router.post("/proof", response_model=ProofRecord)
async def create_proof(
    request: ProofRequest,
    _: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_session),
) -> ProofRecord:
    """
    Create an immutable proof record for a governance decision.

    This endpoint:
    1. Accepts a minimal proof request (entity, action, outcome)
    2. Creates a cryptographically linked proof record
    3. Adds it to the proof chain
    4. Returns the proof record

    The proof chain is append-only and tamper-evident.
    """
    record = await create_proof_record(
        session=session,
        intent_id=request.intent_id or generate_id("int_"),
        verdict_id=request.verdict_id or generate_id("vrd_"),
        entity_id=request.entity_id,
        action_type=request.action,
        decision=request.outcome,
        inputs=request.details or {},
        outputs={"outcome": request.outcome},
    )

    return record


@router.get("/proof/stats", response_model=ProofStats)
async def get_proof_stats(
    _: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_session),
) -> ProofStats:
    """
    Get statistics about the proof ledger.
    """
    repo = ProofRepository(session)

    # Get stats from database
    stats = await repo.get_stats()

    # Verify chain integrity
    chain_valid, _ = await repo.verify_chain_integrity()

    return ProofStats(
        total_records=stats["total_records"],
        chain_length=stats["chain_length"],
        last_record_at=stats["last_record_at"],
        records_by_decision=stats["records_by_decision"],
        chain_integrity=chain_valid,
    )


@router.get("/proof/{proof_id}", response_model=ProofRecord)
async def get_proof(
    proof_id: str,
    _: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_session),
) -> ProofRecord:
    """
    Retrieve a proof record by ID.
    """
    repo = ProofRepository(session)
    record = await repo.get_by_id(proof_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Proof {proof_id} not found")

    return record


@router.post("/proof/query", response_model=list[ProofRecord])
async def query_proofs(
    query: ProofQuery,
    _: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_session),
) -> list[ProofRecord]:
    """
    Query proof records with filters.
    """
    repo = ProofRepository(session)
    return await repo.query(query)


@router.get("/proof/{proof_id}/verify", response_model=ProofVerification)
async def verify_proof(
    proof_id: str,
    _: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_session),
) -> ProofVerification:
    """
    Verify the integrity of a proof record and its chain linkage.
    """
    repo = ProofRepository(session)
    record = await repo.get_by_id(proof_id)

    if not record:
        raise HTTPException(status_code=404, detail=f"Proof {proof_id} not found")

    issues = []

    # Verify hash
    record_data = {
        "proof_id": record.proof_id,
        "chain_position": record.chain_position,
        "intent_id": record.intent_id,
        "verdict_id": record.verdict_id,
        "entity_id": record.entity_id,
        "action_type": record.action_type,
        "decision": record.decision,
        "inputs_hash": record.inputs_hash,
        "outputs_hash": record.outputs_hash,
        "previous_hash": record.previous_hash,
        "created_at": record.created_at.isoformat(),
    }
    expected_hash = calculate_hash(record_data)

    hash_valid = record.hash == expected_hash
    if not hash_valid:
        issues.append("Hash mismatch - record may be tampered")

    # Verify chain linkage
    chain_valid = True
    if record.chain_position > 0:
        previous = await repo.get_by_position(record.chain_position - 1)
        if previous and record.previous_hash != previous.hash:
            chain_valid = False
            issues.append("Chain linkage broken")

    # Verify signature if present
    signature_valid = None
    if record.signature:
        signature_valid = verify_proof_signature(record_data, record.signature)
        if not signature_valid:
            issues.append("Signature verification failed")

    return ProofVerification(
        proof_id=proof_id,
        valid=hash_valid and chain_valid and (signature_valid is not False),
        chain_valid=chain_valid,
        signature_valid=signature_valid,
        issues=issues,
    )
