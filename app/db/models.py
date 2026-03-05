"""
SQLAlchemy models for Cognigate database tables.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class ProofRecordDB(Base):
    """
    SQLAlchemy model for proof records.

    Maps to the proof_records table.
    """
    __tablename__ = "proof_records"
    __table_args__ = (
        UniqueConstraint('chain_position', name='uq_proof_chain_position'),
    )

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proof_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # Chain position
    chain_position: Mapped[int] = mapped_column(Integer, unique=True, index=True)

    # References
    intent_id: Mapped[str] = mapped_column(String(64), index=True)
    verdict_id: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str] = mapped_column(String(128), index=True)

    # The record
    action_type: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(32), index=True)

    # Hashes for integrity
    inputs_hash: Mapped[str] = mapped_column(String(64))
    outputs_hash: Mapped[str] = mapped_column(String(64))

    # Chain integrity
    previous_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), index=True)
    signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ChainStateDB(Base):
    """
    Stores the current state of the proof chain.

    Single row table to track the last hash for chain linking.
    """
    __tablename__ = "chain_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    last_hash: Mapped[str] = mapped_column(String(64))
    chain_length: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )


class TrustStateDB(Base):
    """Persisted trust state for agents."""
    __tablename__ = "trust_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(256))
    score: Mapped[int] = mapped_column(Integer, default=200)
    tier: Mapped[int] = mapped_column(Integer, default=1)
    ceiling: Mapped[int] = mapped_column(Integer, default=4)
    capabilities: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    observation_tier: Mapped[str] = mapped_column(String(32), default="GRAY_BOX")
    is_revoked: Mapped[bool] = mapped_column(Integer, default=False)  # SQLite compat
    admitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TrustSignalDB(Base):
    """Persisted trust signals for audit trail."""
    __tablename__ = "trust_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(128), index=True)
    signal_type: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(256))
    weight: Mapped[float] = mapped_column(Float, default=0.5)
    delta: Mapped[int] = mapped_column(Integer)
    context_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class IntentRecordDB(Base):
    """Persisted intent records for retrieval via GET /intent/{intent_id}."""
    __tablename__ = "intent_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    intent_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    entity_id: Mapped[str] = mapped_column(String(128), index=True)
    goal: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="normalized")
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    plan_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trust_score: Mapped[int] = mapped_column(Integer, default=200)
    trust_level: Mapped[int] = mapped_column(Integer, default=1)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
