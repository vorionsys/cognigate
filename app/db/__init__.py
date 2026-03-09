# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Vorion LLC

"""
Database module for Cognigate.

Provides SQLAlchemy async database support for:
- Proof record persistence
- Chain state tracking
- Compliance evidence persistence
"""

from .database import init_db, close_db, get_session, Base
from .models import ProofRecordDB, ChainStateDB, TrustStateDB, TrustSignalDB
from .evidence_models import ControlEvidenceDB, ControlHealthDB, ComplianceSnapshotDB
from .proof_repository import ProofRepository, GENESIS_HASH
from .evidence_repository import EvidenceRepository

__all__ = [
    # Database lifecycle
    "init_db",
    "close_db",
    "get_session",
    "Base",
    # Models
    "ProofRecordDB",
    "ChainStateDB",
    "TrustStateDB",
    "TrustSignalDB",
    # Evidence models
    "ControlEvidenceDB",
    "ControlHealthDB",
    "ComplianceSnapshotDB",
    # Repositories
    "ProofRepository",
    "GENESIS_HASH",
    "EvidenceRepository",
]
