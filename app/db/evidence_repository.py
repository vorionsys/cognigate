"""
Repository for compliance evidence persistence.

Handles all database operations for the evidence layer:
- Recording evidence when proof events are created
- Querying evidence by control, framework, and time range
- Computing control health from evidence records
- Generating point-in-time compliance snapshots
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evidence import (
    ControlEvidence,
    ControlHealthStatus,
    ComplianceSnapshot,
    EvidenceQuery,
)
from .evidence_models import (
    ControlEvidenceDB,
    ControlHealthDB,
    ComplianceSnapshotDB,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retention policies per framework (years)
# ---------------------------------------------------------------------------
RETENTION_YEARS: dict[str, int] = {
    "NIST-800-53": 7,
    "EU-AI-ACT": 10,
    "ISO-42001": 7,
    "SOC-2": 5,
    "NIST-AI-RMF": 7,
    "CMMC": 7,
    "GDPR": 6,
}

# ---------------------------------------------------------------------------
# Default control sets per framework (controls Cognigate addresses)
# ---------------------------------------------------------------------------
FRAMEWORK_CONTROLS: dict[str, list[str]] = {
    "NIST-800-53": [
        "AC-2", "AC-3", "AC-6", "AC-17",
        "AU-2", "AU-3", "AU-6", "AU-9", "AU-12",
        "CA-7",
        "CM-3", "CM-8",
        "IA-2", "IA-5",
        "IR-4", "IR-5", "IR-6",
        "RA-3", "RA-5",
        "SC-7", "SC-13", "SC-28",
        "SI-4", "SI-7",
    ],
    "EU-AI-ACT": [
        "Article-9", "Article-10", "Article-11", "Article-12",
        "Article-13", "Article-14", "Article-15",
        "Article-17", "Article-72",
    ],
    "ISO-42001": [
        "A.5.2", "A.5.3", "A.5.4",
        "A.6.1.2", "A.6.1.4",
        "A.6.2.2", "A.6.2.4", "A.6.2.6",
        "A.7.2", "A.7.3",
        "A.8.2", "A.8.4",
        "A.9.2", "A.9.3", "A.9.4",
        "A.10.2", "A.10.3",
    ],
    "SOC-2": [
        "CC1.1", "CC1.2",
        "CC2.1",
        "CC3.1", "CC3.2", "CC3.3",
        "CC4.1", "CC4.2",
        "CC5.1", "CC5.2", "CC5.3",
        "CC6.1", "CC6.2", "CC6.3", "CC6.6", "CC6.7", "CC6.8",
        "CC7.1", "CC7.2", "CC7.3", "CC7.4",
        "CC8.1",
        "CC9.1",
    ],
    "NIST-AI-RMF": [
        "GOVERN-1.1", "GOVERN-1.2", "GOVERN-1.5",
        "GOVERN-4.1", "GOVERN-4.2",
        "MAP-1.1", "MAP-1.5", "MAP-1.6",
        "MAP-2.1", "MAP-2.2", "MAP-2.3",
        "MAP-3.5",
        "MEASURE-1.1", "MEASURE-2.2", "MEASURE-2.5",
        "MEASURE-2.6", "MEASURE-2.11",
        "MANAGE-1.1", "MANAGE-2.2", "MANAGE-2.4",
        "MANAGE-3.1", "MANAGE-4.1",
    ],
    "CMMC": [
        "AC.L1-3.1.1", "AC.L1-3.1.2",
        "AC.L2-3.1.5", "AC.L2-3.1.7",
        "AU.L2-3.3.1", "AU.L2-3.3.2",
        "IA.L1-3.5.1", "IA.L1-3.5.2",
        "IR.L2-3.6.1", "IR.L2-3.6.2",
        "SC.L1-3.13.1", "SC.L2-3.13.11",
        "SI.L1-3.14.1", "SI.L2-3.14.6", "SI.L2-3.14.7",
    ],
    "GDPR": [
        "Article-5", "Article-6",
        "Article-12", "Article-13", "Article-14",
        "Article-22", "Article-25",
        "Article-30", "Article-32",
        "Article-33", "Article-35",
    ],
}


def _retention_expiry(framework: str) -> datetime:
    """Calculate retention expiry for a given framework."""
    years = RETENTION_YEARS.get(framework, 7)
    return datetime.utcnow() + timedelta(days=365 * years)


class EvidenceRepository:
    """
    Repository for compliance evidence CRUD operations.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def record_evidence(self, evidence: ControlEvidence) -> ControlEvidence:
        """
        Persist a ControlEvidence record.

        Args:
            evidence: The evidence record to store.

        Returns:
            The stored evidence record.
        """
        db_record = ControlEvidenceDB(
            evidence_id=evidence.evidence_id,
            proof_id=evidence.proof_id,
            control_id=evidence.control_id,
            framework=evidence.framework,
            evidence_type=evidence.evidence_type,
            evidence_category=evidence.evidence_category,
            description=evidence.description,
            compliance_status=evidence.compliance_status,
            collected_at=evidence.collected_at,
            retention_expires=evidence.retention_expires,
            metadata_json=json.dumps(evidence.metadata) if evidence.metadata else None,
        )
        self.session.add(db_record)
        await self.session.flush()

        logger.info(
            "evidence_recorded",
            extra={
                "evidence_id": evidence.evidence_id,
                "proof_id": evidence.proof_id,
                "control_id": evidence.control_id,
                "framework": evidence.framework,
            },
        )
        return evidence

    async def record_evidence_batch(
        self, evidence_list: list[ControlEvidence]
    ) -> list[ControlEvidence]:
        """
        Persist multiple ControlEvidence records in a single flush.

        Args:
            evidence_list: Evidence records to store.

        Returns:
            The stored evidence records.
        """
        db_records = [
            ControlEvidenceDB(
                evidence_id=e.evidence_id,
                proof_id=e.proof_id,
                control_id=e.control_id,
                framework=e.framework,
                evidence_type=e.evidence_type,
                evidence_category=e.evidence_category,
                description=e.description,
                compliance_status=e.compliance_status,
                collected_at=e.collected_at,
                retention_expires=e.retention_expires,
                metadata_json=json.dumps(e.metadata) if e.metadata else None,
            )
            for e in evidence_list
        ]
        self.session.add_all(db_records)
        await self.session.flush()

        logger.info(
            "evidence_batch_recorded",
            extra={"count": len(evidence_list)},
        )
        return evidence_list

    async def save_control_health(self, health: ControlHealthStatus) -> None:
        """
        Persist a control health snapshot row.

        Args:
            health: The control health status to store.
        """
        db_record = ControlHealthDB(
            control_id=health.control_id,
            framework=health.framework,
            status=health.status,
            last_evidence_at=health.last_evidence_at,
            evidence_count=health.evidence_count,
            issues_json=json.dumps(health.issues) if health.issues else None,
            remediation=health.remediation,
        )
        self.session.add(db_record)
        await self.session.flush()

    async def save_compliance_snapshot(self, snapshot: ComplianceSnapshot) -> ComplianceSnapshot:
        """
        Persist a framework-level compliance snapshot.

        Args:
            snapshot: The compliance snapshot to store.

        Returns:
            The stored snapshot.
        """
        controls_data = [ctrl.model_dump(mode="json") for ctrl in snapshot.controls]
        db_record = ComplianceSnapshotDB(
            snapshot_id=snapshot.snapshot_id,
            framework=snapshot.framework,
            total_controls=snapshot.total_controls,
            compliant=snapshot.compliant,
            non_compliant=snapshot.non_compliant,
            degraded=snapshot.degraded,
            unknown=snapshot.unknown,
            controls_json=json.dumps(controls_data),
            timestamp=snapshot.timestamp,
        )
        self.session.add(db_record)
        await self.session.flush()

        logger.info(
            "compliance_snapshot_saved",
            extra={
                "snapshot_id": snapshot.snapshot_id,
                "framework": snapshot.framework,
                "compliant": snapshot.compliant,
                "total": snapshot.total_controls,
            },
        )
        return snapshot

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get_control_evidence(
        self,
        control_id: str,
        framework: str,
        *,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[ControlEvidence]:
        """
        Get all evidence records for a specific control.

        Args:
            control_id: Control identifier (e.g. "AC-3").
            framework: Framework identifier (e.g. "NIST-800-53").
            limit: Maximum records to return.
            offset: Records to skip.

        Returns:
            List of ControlEvidence records ordered by collection time.
        """
        stmt = (
            select(ControlEvidenceDB)
            .where(
                and_(
                    ControlEvidenceDB.control_id == control_id,
                    ControlEvidenceDB.framework == framework,
                )
            )
            .order_by(ControlEvidenceDB.collected_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_evidence_model(r) for r in rows]

    async def get_evidence_by_proof(self, proof_id: str) -> list[ControlEvidence]:
        """
        Get all evidence records generated from a specific proof record.

        Args:
            proof_id: The originating proof record ID.

        Returns:
            List of ControlEvidence records.
        """
        stmt = (
            select(ControlEvidenceDB)
            .where(ControlEvidenceDB.proof_id == proof_id)
            .order_by(ControlEvidenceDB.collected_at.desc())
        )
        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_evidence_model(r) for r in rows]

    async def query_evidence(self, query: EvidenceQuery) -> list[ControlEvidence]:
        """
        Query evidence records with flexible filters.

        Args:
            query: Query parameters.

        Returns:
            Matching ControlEvidence records.
        """
        stmt = select(ControlEvidenceDB)

        if query.proof_id:
            stmt = stmt.where(ControlEvidenceDB.proof_id == query.proof_id)
        if query.control_id:
            stmt = stmt.where(ControlEvidenceDB.control_id == query.control_id)
        if query.framework:
            stmt = stmt.where(ControlEvidenceDB.framework == query.framework)
        if query.evidence_type:
            stmt = stmt.where(ControlEvidenceDB.evidence_type == query.evidence_type)
        if query.evidence_category:
            stmt = stmt.where(ControlEvidenceDB.evidence_category == query.evidence_category)
        if query.compliance_status:
            stmt = stmt.where(ControlEvidenceDB.compliance_status == query.compliance_status)
        if query.start_date:
            stmt = stmt.where(ControlEvidenceDB.collected_at >= query.start_date)
        if query.end_date:
            stmt = stmt.where(ControlEvidenceDB.collected_at <= query.end_date)

        stmt = (
            stmt.order_by(ControlEvidenceDB.collected_at.desc())
            .offset(query.offset)
            .limit(query.limit)
        )

        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_evidence_model(r) for r in rows]

    # ------------------------------------------------------------------
    # Computed operations
    # ------------------------------------------------------------------

    async def get_control_health(
        self,
        control_id: str,
        framework: str,
        *,
        lookback_hours: int = 24,
    ) -> ControlHealthStatus:
        """
        Compute the current health status of a specific control.

        Health is derived from the evidence records collected within
        the lookback window. A control is:
        - **compliant** if evidence exists and none is "partially_satisfies"
          with unresolved issues.
        - **degraded** if evidence exists but the most recent record is
          "partially_satisfies" or "supports".
        - **non_compliant** if no evidence exists within the lookback window.
        - **unknown** if the control has never been evaluated.

        Args:
            control_id: Control identifier.
            framework: Framework identifier.
            lookback_hours: How far back to consider evidence.

        Returns:
            ControlHealthStatus for the control.
        """
        cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)

        # Total evidence count
        count_result = await self.session.execute(
            select(func.count(ControlEvidenceDB.id)).where(
                and_(
                    ControlEvidenceDB.control_id == control_id,
                    ControlEvidenceDB.framework == framework,
                )
            )
        )
        total_count = count_result.scalar() or 0

        # Recent evidence count
        recent_result = await self.session.execute(
            select(func.count(ControlEvidenceDB.id)).where(
                and_(
                    ControlEvidenceDB.control_id == control_id,
                    ControlEvidenceDB.framework == framework,
                    ControlEvidenceDB.collected_at >= cutoff,
                )
            )
        )
        recent_count = recent_result.scalar() or 0

        # Latest evidence record
        latest_result = await self.session.execute(
            select(ControlEvidenceDB)
            .where(
                and_(
                    ControlEvidenceDB.control_id == control_id,
                    ControlEvidenceDB.framework == framework,
                )
            )
            .order_by(ControlEvidenceDB.collected_at.desc())
            .limit(1)
        )
        latest = latest_result.scalar_one_or_none()

        # Determine status
        issues: list[str] = []
        remediation: Optional[str] = None

        if total_count == 0:
            status = "unknown"
            issues.append("No evidence has ever been recorded for this control")
            remediation = "Ensure proof chain events are being generated for actions related to this control"
        elif recent_count == 0:
            status = "non_compliant"
            issues.append(
                f"No evidence collected in the last {lookback_hours} hours"
            )
            remediation = "Investigate whether the system is generating proof events for this control"
        elif latest and latest.compliance_status == "satisfies":
            status = "compliant"
        elif latest and latest.compliance_status == "partially_satisfies":
            status = "degraded"
            issues.append("Latest evidence only partially satisfies the control")
            remediation = "Review partial satisfaction and determine if additional controls are needed"
        else:
            status = "degraded"
            issues.append("Latest evidence provides only supporting evidence")
            remediation = "Additional primary evidence may be required"

        return ControlHealthStatus(
            control_id=control_id,
            framework=framework,
            status=status,
            last_evidence_at=latest.collected_at if latest else None,
            evidence_count=total_count,
            issues=issues,
            remediation=remediation,
        )

    async def get_compliance_snapshot(
        self,
        framework: str,
        *,
        lookback_hours: int = 24,
        persist: bool = True,
    ) -> ComplianceSnapshot:
        """
        Generate a point-in-time compliance snapshot for a framework.

        Iterates over all controls Cognigate addresses for the given
        framework, computes health for each, and aggregates into a
        snapshot.

        Args:
            framework: Framework identifier.
            lookback_hours: Lookback window for health computation.
            persist: Whether to persist the snapshot to the database.

        Returns:
            ComplianceSnapshot with per-control breakdown.
        """
        controls = FRAMEWORK_CONTROLS.get(framework, [])
        if not controls:
            logger.warning(
                "unknown_framework_for_snapshot",
                extra={"framework": framework},
            )

        health_statuses: list[ControlHealthStatus] = []
        counts = {"compliant": 0, "non_compliant": 0, "degraded": 0, "unknown": 0}

        for control_id in controls:
            health = await self.get_control_health(
                control_id, framework, lookback_hours=lookback_hours
            )
            health_statuses.append(health)
            counts[health.status] += 1

        snapshot = ComplianceSnapshot(
            framework=framework,
            total_controls=len(controls),
            compliant=counts["compliant"],
            non_compliant=counts["non_compliant"],
            degraded=counts["degraded"],
            unknown=counts["unknown"],
            controls=health_statuses,
        )

        if persist:
            await self.save_compliance_snapshot(snapshot)

        logger.info(
            "compliance_snapshot_generated",
            extra={
                "framework": framework,
                "total": snapshot.total_controls,
                "compliant": snapshot.compliant,
                "non_compliant": snapshot.non_compliant,
                "degraded": snapshot.degraded,
                "unknown": snapshot.unknown,
            },
        )
        return snapshot

    async def get_evidence_chain(
        self,
        start_time: datetime,
        end_time: datetime,
        framework: Optional[str] = None,
        *,
        limit: int = 10000,
    ) -> list[ControlEvidence]:
        """
        Retrieve the evidence chain for an audit period.

        Returns all evidence records within the time range, optionally
        filtered by framework, ordered chronologically for audit
        consumption.

        Args:
            start_time: Audit period start (inclusive).
            end_time: Audit period end (inclusive).
            framework: Optional framework filter.
            limit: Maximum records to return.

        Returns:
            Chronologically ordered list of ControlEvidence records.
        """
        stmt = select(ControlEvidenceDB).where(
            and_(
                ControlEvidenceDB.collected_at >= start_time,
                ControlEvidenceDB.collected_at <= end_time,
            )
        )
        if framework:
            stmt = stmt.where(ControlEvidenceDB.framework == framework)

        stmt = stmt.order_by(ControlEvidenceDB.collected_at.asc()).limit(limit)

        result = await self.session.execute(stmt)
        rows = result.scalars().all()
        return [self._to_evidence_model(r) for r in rows]

    async def get_evidence_stats(
        self, framework: Optional[str] = None
    ) -> dict:
        """
        Get aggregate statistics about the evidence store.

        Args:
            framework: Optional framework filter.

        Returns:
            Dictionary with evidence statistics.
        """
        base_filter = []
        if framework:
            base_filter.append(ControlEvidenceDB.framework == framework)

        # Total count
        count_stmt = select(func.count(ControlEvidenceDB.id))
        if base_filter:
            count_stmt = count_stmt.where(*base_filter)
        total = (await self.session.execute(count_stmt)).scalar() or 0

        # Counts by framework
        fw_stmt = select(
            ControlEvidenceDB.framework,
            func.count(ControlEvidenceDB.id),
        ).group_by(ControlEvidenceDB.framework)
        if base_filter:
            fw_stmt = fw_stmt.where(*base_filter)
        fw_result = await self.session.execute(fw_stmt)
        by_framework = {row[0]: row[1] for row in fw_result.all()}

        # Counts by evidence type
        et_stmt = select(
            ControlEvidenceDB.evidence_type,
            func.count(ControlEvidenceDB.id),
        ).group_by(ControlEvidenceDB.evidence_type)
        if base_filter:
            et_stmt = et_stmt.where(*base_filter)
        et_result = await self.session.execute(et_stmt)
        by_type = {row[0]: row[1] for row in et_result.all()}

        # Latest record
        latest_stmt = (
            select(ControlEvidenceDB)
            .order_by(ControlEvidenceDB.collected_at.desc())
            .limit(1)
        )
        if base_filter:
            latest_stmt = latest_stmt.where(*base_filter)
        latest = (await self.session.execute(latest_stmt)).scalar_one_or_none()

        return {
            "total_evidence_records": total,
            "by_framework": by_framework,
            "by_evidence_type": by_type,
            "latest_collected_at": latest.collected_at.isoformat() if latest else None,
        }

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def _to_evidence_model(self, db_record: ControlEvidenceDB) -> ControlEvidence:
        """Convert a database row to a Pydantic model."""
        return ControlEvidence(
            evidence_id=db_record.evidence_id,
            proof_id=db_record.proof_id,
            control_id=db_record.control_id,
            framework=db_record.framework,
            evidence_type=db_record.evidence_type,
            evidence_category=db_record.evidence_category,
            description=db_record.description,
            compliance_status=db_record.compliance_status,
            collected_at=db_record.collected_at,
            retention_expires=db_record.retention_expires,
            metadata=json.loads(db_record.metadata_json) if db_record.metadata_json else {},
        )
