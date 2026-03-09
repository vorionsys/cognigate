# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Repository for proof record persistence.

Handles all database operations for the proof chain.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.proof import ProofRecord, ProofQuery
from .models import ProofRecordDB, ChainStateDB

logger = logging.getLogger(__name__)

# Genesis hash for empty chain
GENESIS_HASH = "0" * 64


class ProofRepository:
    """
    Repository for proof record CRUD operations.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _get_dialect_name(self) -> str:
        """Get the database dialect name (e.g., 'postgresql', 'sqlite')."""
        bind = self.session.get_bind()
        return bind.dialect.name

    async def get_chain_state_for_append(self) -> tuple[str, int]:
        """
        Atomically read chain state with row-level lock for append operations.

        Uses SELECT FOR UPDATE on PostgreSQL to prevent concurrent chain appends.
        Falls back to a plain SELECT on SQLite (which is single-writer anyway).

        Returns:
            Tuple of (last_hash, chain_length).
        """
        dialect = await self._get_dialect_name()

        if dialect == "sqlite":
            # SQLite uses database-level locking (single writer), so
            # SELECT FOR UPDATE is unnecessary and unsupported.
            stmt = select(ChainStateDB).where(ChainStateDB.id == 1)
        else:
            # PostgreSQL: acquire row-level lock to serialize chain appends.
            stmt = (
                select(ChainStateDB)
                .where(ChainStateDB.id == 1)
                .with_for_update()
            )

        result = await self.session.execute(stmt)
        state = result.scalar_one_or_none()

        if state:
            return state.last_hash, state.chain_length
        return GENESIS_HASH, 0

    async def get_last_hash(self) -> str:
        """Get the hash of the last record in the chain."""
        result = await self.session.execute(
            select(ChainStateDB).where(ChainStateDB.id == 1)
        )
        state = result.scalar_one_or_none()

        if state:
            return state.last_hash
        return GENESIS_HASH

    async def get_chain_length(self) -> int:
        """Get the current chain length."""
        result = await self.session.execute(
            select(ChainStateDB).where(ChainStateDB.id == 1)
        )
        state = result.scalar_one_or_none()

        if state:
            return state.chain_length
        return 0

    async def _update_chain_state(self, last_hash: str, chain_length: int) -> None:
        """
        Update the chain state after adding a record.

        When called within a transaction that already holds the FOR UPDATE lock
        (via get_chain_state_for_append), the row is already locked and this
        update is safe from concurrent modification.

        Increments the version column for optimistic concurrency detection
        as defense-in-depth.
        """
        result = await self.session.execute(
            select(ChainStateDB).where(ChainStateDB.id == 1)
        )
        state = result.scalar_one_or_none()

        if state:
            state.last_hash = last_hash
            state.chain_length = chain_length
            state.version = state.version + 1
            state.updated_at = datetime.utcnow()
        else:
            state = ChainStateDB(
                id=1,
                last_hash=last_hash,
                chain_length=chain_length,
                version=1,
            )
            self.session.add(state)

    async def create(self, record: ProofRecord) -> ProofRecord:
        """
        Create a new proof record in the database.

        Args:
            record: The proof record to create

        Returns:
            The created proof record
        """
        db_record = ProofRecordDB(
            proof_id=record.proof_id,
            chain_position=record.chain_position,
            intent_id=record.intent_id,
            verdict_id=record.verdict_id,
            entity_id=record.entity_id,
            action_type=record.action_type,
            decision=record.decision,
            inputs_hash=record.inputs_hash,
            outputs_hash=record.outputs_hash,
            previous_hash=record.previous_hash,
            hash=record.hash,
            signature=record.signature,
            created_at=record.created_at,
            metadata_json=json.dumps(record.metadata) if record.metadata else None,
        )

        self.session.add(db_record)

        # Update chain state
        await self._update_chain_state(record.hash, record.chain_position + 1)

        await self.session.flush()

        logger.info(
            "proof_record_created",
            extra={
                "proof_id": record.proof_id,
                "chain_position": record.chain_position,
            }
        )

        return record

    async def get_by_id(self, proof_id: str) -> Optional[ProofRecord]:
        """
        Get a proof record by its ID.

        Args:
            proof_id: The proof ID to look up

        Returns:
            The proof record or None if not found
        """
        result = await self.session.execute(
            select(ProofRecordDB).where(ProofRecordDB.proof_id == proof_id)
        )
        db_record = result.scalar_one_or_none()

        if db_record:
            return self._to_model(db_record)
        return None

    async def get_by_position(self, position: int) -> Optional[ProofRecord]:
        """
        Get a proof record by its chain position.

        Args:
            position: The chain position

        Returns:
            The proof record or None if not found
        """
        result = await self.session.execute(
            select(ProofRecordDB).where(ProofRecordDB.chain_position == position)
        )
        db_record = result.scalar_one_or_none()

        if db_record:
            return self._to_model(db_record)
        return None

    async def query(self, query: ProofQuery) -> list[ProofRecord]:
        """
        Query proof records with filters.

        Args:
            query: The query parameters

        Returns:
            List of matching proof records
        """
        stmt = select(ProofRecordDB)

        if query.entity_id:
            stmt = stmt.where(ProofRecordDB.entity_id == query.entity_id)

        if query.intent_id:
            stmt = stmt.where(ProofRecordDB.intent_id == query.intent_id)

        if query.verdict_id:
            stmt = stmt.where(ProofRecordDB.verdict_id == query.verdict_id)

        if query.decision:
            stmt = stmt.where(ProofRecordDB.decision == query.decision)

        if query.start_date:
            stmt = stmt.where(ProofRecordDB.created_at >= query.start_date)

        if query.end_date:
            stmt = stmt.where(ProofRecordDB.created_at <= query.end_date)

        # Order by chain position (oldest first)
        stmt = stmt.order_by(ProofRecordDB.chain_position)

        # Apply pagination
        stmt = stmt.offset(query.offset).limit(query.limit)

        result = await self.session.execute(stmt)
        db_records = result.scalars().all()

        return [self._to_model(r) for r in db_records]

    async def get_all(self, limit: int = 1000, offset: int = 0) -> list[ProofRecord]:
        """
        Get all proof records with pagination.

        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of proof records
        """
        result = await self.session.execute(
            select(ProofRecordDB)
            .order_by(ProofRecordDB.chain_position)
            .offset(offset)
            .limit(limit)
        )
        db_records = result.scalars().all()

        return [self._to_model(r) for r in db_records]

    async def get_stats(self) -> dict:
        """
        Get statistics about the proof chain.

        Returns:
            Dictionary with chain statistics
        """
        # Total count
        count_result = await self.session.execute(
            select(func.count(ProofRecordDB.id))
        )
        total_records = count_result.scalar() or 0

        # Last record
        last_result = await self.session.execute(
            select(ProofRecordDB)
            .order_by(ProofRecordDB.chain_position.desc())
            .limit(1)
        )
        last_record = last_result.scalar_one_or_none()

        # Decisions count
        decisions_result = await self.session.execute(
            select(
                ProofRecordDB.decision,
                func.count(ProofRecordDB.id)
            ).group_by(ProofRecordDB.decision)
        )
        decisions = {row[0]: row[1] for row in decisions_result.all()}

        return {
            "total_records": total_records,
            "chain_length": total_records,
            "last_record_at": last_record.created_at if last_record else None,
            "records_by_decision": decisions,
        }

    async def verify_chain_integrity(self) -> tuple[bool, list[str]]:
        """
        Verify the integrity of the entire proof chain.

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # Get all records in order
        result = await self.session.execute(
            select(ProofRecordDB).order_by(ProofRecordDB.chain_position)
        )
        records = result.scalars().all()

        if not records:
            return True, []

        # Check first record links to genesis
        if records[0].previous_hash != GENESIS_HASH:
            issues.append("First record does not link to genesis hash")

        # Check each record links to previous
        for i in range(1, len(records)):
            current = records[i]
            previous = records[i - 1]

            if current.previous_hash != previous.hash:
                issues.append(
                    f"Chain break at position {current.chain_position}: "
                    f"expected {previous.hash}, got {current.previous_hash}"
                )

            if current.chain_position != previous.chain_position + 1:
                issues.append(
                    f"Position gap at {current.chain_position}: "
                    f"expected {previous.chain_position + 1}"
                )

        return len(issues) == 0, issues

    def _to_model(self, db_record: ProofRecordDB) -> ProofRecord:
        """Convert a database record to a Pydantic model."""
        return ProofRecord(
            proof_id=db_record.proof_id,
            chain_position=db_record.chain_position,
            intent_id=db_record.intent_id,
            verdict_id=db_record.verdict_id,
            entity_id=db_record.entity_id,
            action_type=db_record.action_type,
            decision=db_record.decision,
            inputs_hash=db_record.inputs_hash,
            outputs_hash=db_record.outputs_hash,
            previous_hash=db_record.previous_hash,
            hash=db_record.hash,
            signature=db_record.signature,
            created_at=db_record.created_at,
            metadata=json.loads(db_record.metadata_json) if db_record.metadata_json else {},
        )
