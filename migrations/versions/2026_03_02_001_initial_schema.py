"""Initial schema — all existing Cognigate tables.

Revision ID: 001
Revises: None
Create Date: 2026-03-02

This migration captures the baseline schema that was previously
created via Base.metadata.create_all(). All tables defined in:
- app/db/models.py (proof_records, chain_state, trust_state, trust_signals, intent_records)
- app/db/evidence_models.py (control_evidence, control_health, compliance_snapshots)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- proof_records --
    op.create_table(
        "proof_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("proof_id", sa.String(64), nullable=False),
        sa.Column("chain_position", sa.Integer(), nullable=False),
        sa.Column("intent_id", sa.String(64), nullable=False),
        sa.Column("verdict_id", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(128), nullable=False),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("inputs_hash", sa.String(64), nullable=False),
        sa.Column("outputs_hash", sa.String(64), nullable=False),
        sa.Column("previous_hash", sa.String(64), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("proof_id"),
        sa.UniqueConstraint("chain_position", name="uq_proof_chain_position"),
    )
    op.create_index("ix_proof_records_proof_id", "proof_records", ["proof_id"])
    op.create_index("ix_proof_records_chain_position", "proof_records", ["chain_position"])
    op.create_index("ix_proof_records_intent_id", "proof_records", ["intent_id"])
    op.create_index("ix_proof_records_verdict_id", "proof_records", ["verdict_id"])
    op.create_index("ix_proof_records_entity_id", "proof_records", ["entity_id"])
    op.create_index("ix_proof_records_decision", "proof_records", ["decision"])
    op.create_index("ix_proof_records_hash", "proof_records", ["hash"])
    op.create_index("ix_proof_records_created_at", "proof_records", ["created_at"])

    # -- chain_state --
    op.create_table(
        "chain_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("last_hash", sa.String(64), nullable=False),
        sa.Column("chain_length", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # -- trust_state --
    op.create_table(
        "trust_state",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_id", sa.String(128), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("ceiling", sa.Integer(), nullable=False),
        sa.Column("capabilities", sa.Text(), nullable=True),
        sa.Column("observation_tier", sa.String(32), nullable=False),
        sa.Column("is_revoked", sa.Integer(), nullable=False),
        sa.Column("admitted_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id"),
    )
    op.create_index("ix_trust_state_agent_id", "trust_state", ["agent_id"])

    # -- trust_signals --
    op.create_table(
        "trust_signals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("agent_id", sa.String(128), nullable=False),
        sa.Column("signal_type", sa.String(32), nullable=False),
        sa.Column("source", sa.String(256), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("context_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trust_signals_agent_id", "trust_signals", ["agent_id"])
    op.create_index("ix_trust_signals_created_at", "trust_signals", ["created_at"])

    # -- intent_records --
    op.create_table(
        "intent_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("intent_id", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(128), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("risk_score", sa.Float(), nullable=False),
        sa.Column("plan_json", sa.Text(), nullable=True),
        sa.Column("trust_score", sa.Integer(), nullable=False),
        sa.Column("trust_level", sa.Integer(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("intent_id"),
    )
    op.create_index("ix_intent_records_intent_id", "intent_records", ["intent_id"])
    op.create_index("ix_intent_records_entity_id", "intent_records", ["entity_id"])
    op.create_index("ix_intent_records_created_at", "intent_records", ["created_at"])

    # -- control_evidence --
    op.create_table(
        "control_evidence",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("evidence_id", sa.String(64), nullable=False),
        sa.Column("proof_id", sa.String(64), nullable=False),
        sa.Column("control_id", sa.String(32), nullable=False),
        sa.Column("framework", sa.String(32), nullable=False),
        sa.Column("evidence_type", sa.String(32), nullable=False),
        sa.Column("evidence_category", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("compliance_status", sa.String(32), nullable=False),
        sa.Column("collected_at", sa.DateTime(), nullable=False),
        sa.Column("retention_expires", sa.DateTime(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evidence_id"),
    )
    op.create_index("ix_control_evidence_evidence_id", "control_evidence", ["evidence_id"])
    op.create_index("ix_control_evidence_proof_id", "control_evidence", ["proof_id"])
    op.create_index("ix_control_evidence_control_id", "control_evidence", ["control_id"])
    op.create_index("ix_control_evidence_framework", "control_evidence", ["framework"])
    op.create_index("ix_control_evidence_collected_at", "control_evidence", ["collected_at"])
    op.create_index("ix_control_evidence_retention_expires", "control_evidence", ["retention_expires"])

    # -- control_health --
    op.create_table(
        "control_health",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("control_id", sa.String(32), nullable=False),
        sa.Column("framework", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("last_evidence_at", sa.DateTime(), nullable=True),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("issues_json", sa.Text(), nullable=True),
        sa.Column("remediation", sa.Text(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_control_health_control_id", "control_health", ["control_id"])
    op.create_index("ix_control_health_framework", "control_health", ["framework"])
    op.create_index("ix_control_health_recorded_at", "control_health", ["recorded_at"])

    # -- compliance_snapshots --
    op.create_table(
        "compliance_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("snapshot_id", sa.String(64), nullable=False),
        sa.Column("framework", sa.String(32), nullable=False),
        sa.Column("total_controls", sa.Integer(), nullable=False),
        sa.Column("compliant", sa.Integer(), nullable=False),
        sa.Column("non_compliant", sa.Integer(), nullable=False),
        sa.Column("degraded", sa.Integer(), nullable=False),
        sa.Column("unknown", sa.Integer(), nullable=False),
        sa.Column("controls_json", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id"),
    )
    op.create_index("ix_compliance_snapshots_snapshot_id", "compliance_snapshots", ["snapshot_id"])
    op.create_index("ix_compliance_snapshots_framework", "compliance_snapshots", ["framework"])
    op.create_index("ix_compliance_snapshots_timestamp", "compliance_snapshots", ["timestamp"])


def downgrade() -> None:
    op.drop_table("compliance_snapshots")
    op.drop_table("control_health")
    op.drop_table("control_evidence")
    op.drop_table("intent_records")
    op.drop_table("trust_signals")
    op.drop_table("trust_state")
    op.drop_table("chain_state")
    op.drop_table("proof_records")
