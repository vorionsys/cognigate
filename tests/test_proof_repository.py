"""
Tests for proof repository - immutable audit ledger persistence.

Tests CRUD operations, chain integrity verification, genesis hash,
query filters, stats, and chain linkage validation.
"""

import hashlib
import json
from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.database import Base
from app.db.proof_repository import ProofRepository, GENESIS_HASH
from app.models.proof import ProofRecord, ProofQuery


@pytest_asyncio.fixture
async def session():
    """Create in-memory SQLite session for each test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess
    await engine.dispose()


def make_record(chain_position: int, previous_hash: str, **overrides) -> ProofRecord:
    """Helper to create a proof record with computed hash."""
    record = ProofRecord(
        chain_position=chain_position,
        intent_id=overrides.get("intent_id", "int_test"),
        verdict_id=overrides.get("verdict_id", "vrd_test"),
        entity_id=overrides.get("entity_id", "agent_test"),
        action_type=overrides.get("action_type", "enforcement"),
        decision=overrides.get("decision", "allowed"),
        inputs_hash=overrides.get("inputs_hash", "a" * 64),
        outputs_hash=overrides.get("outputs_hash", "b" * 64),
        previous_hash=previous_hash,
        hash="",
    )
    # Compute hash like the proof router does
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
    serialized = json.dumps(record_data, sort_keys=True, default=str)
    record.hash = hashlib.sha256(serialized.encode()).hexdigest()
    return record


@pytest.mark.asyncio
class TestGenesisAndChainState:
    """Test genesis hash and chain state tracking."""

    async def test_empty_chain_returns_genesis_hash(self, session):
        repo = ProofRepository(session)
        last_hash = await repo.get_last_hash()
        assert last_hash == GENESIS_HASH
        assert last_hash == "0" * 64

    async def test_empty_chain_length_is_zero(self, session):
        repo = ProofRepository(session)
        length = await repo.get_chain_length()
        assert length == 0

    async def test_chain_state_updates_after_create(self, session):
        repo = ProofRepository(session)
        record = make_record(0, GENESIS_HASH)
        await repo.create(record)
        await session.commit()

        last_hash = await repo.get_last_hash()
        assert last_hash == record.hash
        length = await repo.get_chain_length()
        assert length == 1


@pytest.mark.asyncio
class TestCRUD:
    """Test proof record create, read, query operations."""

    async def test_create_and_get_by_id(self, session):
        repo = ProofRepository(session)
        record = make_record(0, GENESIS_HASH)
        created = await repo.create(record)
        await session.commit()

        found = await repo.get_by_id(created.proof_id)
        assert found is not None
        assert found.proof_id == created.proof_id
        assert found.decision == "allowed"

    async def test_get_by_id_not_found(self, session):
        repo = ProofRepository(session)
        found = await repo.get_by_id("nonexistent")
        assert found is None

    async def test_get_by_position(self, session):
        repo = ProofRepository(session)
        record = make_record(0, GENESIS_HASH)
        await repo.create(record)
        await session.commit()

        found = await repo.get_by_position(0)
        assert found is not None
        assert found.chain_position == 0

    async def test_get_by_position_not_found(self, session):
        repo = ProofRepository(session)
        found = await repo.get_by_position(999)
        assert found is None

    async def test_get_all_with_pagination(self, session):
        repo = ProofRepository(session)
        records = []
        prev_hash = GENESIS_HASH
        for i in range(5):
            rec = make_record(i, prev_hash)
            await repo.create(rec)
            records.append(rec)
            prev_hash = rec.hash
        await session.commit()

        all_records = await repo.get_all(limit=3)
        assert len(all_records) == 3

        all_records = await repo.get_all(limit=10, offset=3)
        assert len(all_records) == 2


@pytest.mark.asyncio
class TestQuery:
    """Test query with filters."""

    async def test_query_by_entity_id(self, session):
        repo = ProofRepository(session)
        r1 = make_record(0, GENESIS_HASH, entity_id="agent_a")
        await repo.create(r1)
        r2 = make_record(1, r1.hash, entity_id="agent_b")
        await repo.create(r2)
        await session.commit()

        query = ProofQuery(entity_id="agent_a")
        results = await repo.query(query)
        assert len(results) == 1
        assert results[0].entity_id == "agent_a"

    async def test_query_by_decision(self, session):
        repo = ProofRepository(session)
        r1 = make_record(0, GENESIS_HASH, decision="allowed")
        await repo.create(r1)
        r2 = make_record(1, r1.hash, decision="denied")
        await repo.create(r2)
        await session.commit()

        query = ProofQuery(decision="denied")
        results = await repo.query(query)
        assert len(results) == 1
        assert results[0].decision == "denied"

    async def test_query_by_intent_id(self, session):
        repo = ProofRepository(session)
        r1 = make_record(0, GENESIS_HASH, intent_id="int_abc")
        await repo.create(r1)
        r2 = make_record(1, r1.hash, intent_id="int_xyz")
        await repo.create(r2)
        await session.commit()

        query = ProofQuery(intent_id="int_abc")
        results = await repo.query(query)
        assert len(results) == 1

    async def test_query_with_pagination(self, session):
        repo = ProofRepository(session)
        prev_hash = GENESIS_HASH
        for i in range(10):
            rec = make_record(i, prev_hash)
            await repo.create(rec)
            prev_hash = rec.hash
        await session.commit()

        query = ProofQuery(limit=3, offset=0)
        page1 = await repo.query(query)
        assert len(page1) == 3

        query = ProofQuery(limit=3, offset=3)
        page2 = await repo.query(query)
        assert len(page2) == 3
        assert page1[0].proof_id != page2[0].proof_id


@pytest.mark.asyncio
class TestChainIntegrity:
    """Test chain integrity verification."""

    async def test_empty_chain_is_valid(self, session):
        repo = ProofRepository(session)
        valid, issues = await repo.verify_chain_integrity()
        assert valid
        assert issues == []

    async def test_single_record_chain_valid(self, session):
        repo = ProofRepository(session)
        record = make_record(0, GENESIS_HASH)
        await repo.create(record)
        await session.commit()

        valid, issues = await repo.verify_chain_integrity()
        assert valid
        assert issues == []

    async def test_multi_record_chain_valid(self, session):
        repo = ProofRepository(session)
        r0 = make_record(0, GENESIS_HASH)
        await repo.create(r0)
        r1 = make_record(1, r0.hash)
        await repo.create(r1)
        r2 = make_record(2, r1.hash)
        await repo.create(r2)
        await session.commit()

        valid, issues = await repo.verify_chain_integrity()
        assert valid
        assert issues == []

    async def test_broken_chain_detected(self, session):
        repo = ProofRepository(session)
        r0 = make_record(0, GENESIS_HASH)
        await repo.create(r0)
        # Create r1 with wrong previous hash
        r1 = make_record(1, "wrong_hash_" + "0" * 53)
        await repo.create(r1)
        await session.commit()

        valid, issues = await repo.verify_chain_integrity()
        assert not valid
        assert len(issues) > 0

    async def test_wrong_genesis_detected(self, session):
        repo = ProofRepository(session)
        # First record doesn't link to genesis
        r0 = make_record(0, "not_genesis_" + "0" * 52)
        await repo.create(r0)
        await session.commit()

        valid, issues = await repo.verify_chain_integrity()
        assert not valid
        assert any("genesis" in issue for issue in issues)


@pytest.mark.asyncio
class TestStats:
    """Test chain statistics."""

    async def test_empty_chain_stats(self, session):
        repo = ProofRepository(session)
        stats = await repo.get_stats()
        assert stats["total_records"] == 0
        assert stats["chain_length"] == 0
        assert stats["last_record_at"] is None

    async def test_stats_with_records(self, session):
        repo = ProofRepository(session)
        r0 = make_record(0, GENESIS_HASH, decision="allowed")
        await repo.create(r0)
        r1 = make_record(1, r0.hash, decision="denied")
        await repo.create(r1)
        r2 = make_record(2, r1.hash, decision="allowed")
        await repo.create(r2)
        await session.commit()

        stats = await repo.get_stats()
        assert stats["total_records"] == 3
        assert stats["last_record_at"] is not None
        assert stats["records_by_decision"]["allowed"] == 2
        assert stats["records_by_decision"]["denied"] == 1
