# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""Add last_activity_at column to trust_state for 182-day decay tracking.

Revision ID: 002
Revises: 001
Create Date: 2026-03-10

Supports the stepped inactivity decay system (182-day half-life, 50% floor).
The column tracks the timestamp of the agent's last trust-relevant activity.
When no activity occurs, the trust score decays along a 9-milestone schedule.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: str = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add last_activity_at with default = current timestamp.
    # For existing rows, backfill from updated_at (most recent activity proxy).
    op.add_column(
        "trust_state",
        sa.Column("last_activity_at", sa.DateTime(), nullable=True),
    )
    # Backfill: use updated_at as the best available proxy for last activity
    op.execute("UPDATE trust_state SET last_activity_at = COALESCE(updated_at, admitted_at)")
    # Now set NOT NULL (SQLite: this is a no-op, but documents intent for Postgres)
    # op.alter_column("trust_state", "last_activity_at", nullable=False)


def downgrade() -> None:
    op.drop_column("trust_state", "last_activity_at")
