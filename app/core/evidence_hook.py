# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Evidence Hook — Automatic Evidence Generation on Proof Record Creation.

This module provides the EvidenceHook class, which is invoked after every
proof record is created in the proof chain. It uses the EvidenceMapper to
determine which compliance controls the proof event satisfies, then
persists the resulting ControlEvidence records via the EvidenceRepository.

Integration point:
    After ProofRepository.create() succeeds, call:
        await evidence_hook.on_proof_created(proof_record, session)

This ensures that every proof chain event automatically generates the
corresponding compliance evidence — no manual mapping, no batch jobs,
no evidence gaps.
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.proof import ProofRecord
from app.models.evidence import ControlEvidence
from app.core.evidence_mapper import EvidenceMapper
from app.db.evidence_repository import EvidenceRepository

logger = logging.getLogger(__name__)


class EvidenceHook:
    """
    Automatically generates compliance evidence when proof records are created.

    This hook bridges the Proof Plane and the Evidence Layer. It is
    designed to be called synchronously within the same database
    transaction as the proof record creation, so evidence records are
    atomically committed alongside their originating proof records.

    Usage::

        hook = EvidenceHook()

        # Inside proof record creation flow:
        proof_record = await proof_repo.create(record)
        await hook.on_proof_created(proof_record, session)

    Thread safety:
        The hook is stateless (mapper is stateless). Multiple concurrent
        calls are safe.
    """

    def __init__(
        self,
        mapper: Optional[EvidenceMapper] = None,
        frameworks: Optional[list[str]] = None,
    ) -> None:
        """
        Initialize the evidence hook.

        Args:
            mapper: EvidenceMapper instance. If None, creates a default one.
            frameworks: Optional list of frameworks to generate evidence for.
                If None, generates evidence for ALL frameworks.
        """
        self.mapper = mapper or EvidenceMapper()
        self.frameworks = frameworks

    async def on_proof_created(
        self,
        proof_record: ProofRecord,
        session: AsyncSession,
    ) -> list[ControlEvidence]:
        """
        Called after every proof record creation.

        Maps the proof record to compliance evidence and persists the
        evidence records within the same database session (and thus
        the same transaction).

        Args:
            proof_record: The newly created proof record.
            session: The active database session (same transaction
                as the proof record creation).

        Returns:
            List of ControlEvidence records that were created.

        Raises:
            No exceptions are raised to the caller. Errors are logged
            and an empty list is returned to avoid blocking proof chain
            operations.
        """
        try:
            # Generate evidence records from the proof event
            evidence_records = self.mapper.map_event_to_evidence(
                proof_record,
                frameworks=self.frameworks,
            )

            if not evidence_records:
                logger.debug(
                    "no_evidence_generated",
                    extra={
                        "proof_id": proof_record.proof_id,
                        "action_type": proof_record.action_type,
                    },
                )
                return []

            # Persist evidence records in batch
            repository = EvidenceRepository(session)
            stored = await repository.record_evidence_batch(evidence_records)

            logger.info(
                "evidence_hook_completed",
                extra={
                    "proof_id": proof_record.proof_id,
                    "action_type": proof_record.action_type,
                    "evidence_count": len(stored),
                    "frameworks": list({e.framework for e in stored}),
                },
            )
            return stored

        except Exception:
            # Evidence generation MUST NOT block proof chain operations.
            # Log the error (with full traceback) and return empty to
            # allow the proof record commit to proceed.
            logger.exception(
                "evidence_generation_failed",
                extra={
                    "proof_id": proof_record.proof_id,
                    "action_type": proof_record.action_type,
                },
            )
            return []


# ---------------------------------------------------------------------------
# Module-level singleton for convenience
# ---------------------------------------------------------------------------

evidence_hook = EvidenceHook()


async def on_proof_created(
    proof_record: ProofRecord,
    session: AsyncSession,
) -> list[ControlEvidence]:
    """
    Module-level convenience function for the evidence hook.

    Calls the global EvidenceHook instance.

    Args:
        proof_record: The newly created proof record.
        session: The active database session.

    Returns:
        List of ControlEvidence records created.
    """
    return await evidence_hook.on_proof_created(proof_record, session)
