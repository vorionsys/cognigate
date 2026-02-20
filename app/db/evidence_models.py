"""
SQLAlchemy models for compliance evidence tables.

Three tables:
- control_evidence: Links proof records to compliance framework controls.
- control_health: Periodic per-control health snapshots.
- compliance_snapshots: Framework-level compliance snapshots.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class ControlEvidenceDB(Base):
    """
    Links a proof record to the compliance control it satisfies.

    Each row is an immutable attestation that a specific proof chain
    event provides evidence for a specific compliance control.
    """
    __tablename__ = "control_evidence"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # Link to proof chain
    proof_id: Mapped[str] = mapped_column(String(64), index=True)

    # Control identification
    control_id: Mapped[str] = mapped_column(String(32), index=True)
    framework: Mapped[str] = mapped_column(String(32), index=True)

    # Evidence classification
    evidence_type: Mapped[str] = mapped_column(String(32))
    evidence_category: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text)
    compliance_status: Mapped[str] = mapped_column(String(32))

    # Timestamps
    collected_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True,
    )
    retention_expires: Mapped[datetime] = mapped_column(
        DateTime,
        index=True,
    )

    # Additional context (JSON)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ControlHealthDB(Base):
    """
    Periodic health snapshot for a single compliance control.

    Stored at regular intervals to enable compliance trending and
    historical lookback for auditors.
    """
    __tablename__ = "control_health"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Control identification
    control_id: Mapped[str] = mapped_column(String(32), index=True)
    framework: Mapped[str] = mapped_column(String(32), index=True)

    # Status
    status: Mapped[str] = mapped_column(String(32))
    last_evidence_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)

    # Issues and remediation (JSON list / text)
    issues_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    remediation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Snapshot timestamp
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True,
    )


class ComplianceSnapshotDB(Base):
    """
    Framework-level compliance snapshot.

    Point-in-time aggregate of all control health statuses for a
    given framework. Stored for historical compliance reporting.
    """
    __tablename__ = "compliance_snapshots"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # Framework
    framework: Mapped[str] = mapped_column(String(32), index=True)

    # Aggregate counts
    total_controls: Mapped[int] = mapped_column(Integer)
    compliant: Mapped[int] = mapped_column(Integer)
    non_compliant: Mapped[int] = mapped_column(Integer)
    degraded: Mapped[int] = mapped_column(Integer)
    unknown: Mapped[int] = mapped_column(Integer)

    # Detailed per-control breakdown (JSON)
    controls_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True,
    )
