"""
SQLAlchemy models for Cognigate database tables.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class ProofRecordDB(Base):
    """
    SQLAlchemy model for proof records.

    Maps to the proof_records table.
    """
    __tablename__ = "proof_records"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proof_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # Chain position
    chain_position: Mapped[int] = mapped_column(Integer, index=True)

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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
