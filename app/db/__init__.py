"""
Database module for Cognigate.

Provides SQLAlchemy async database support for:
- Proof record persistence
- Chain state tracking
"""

from .database import init_db, close_db, get_session, Base
from .models import ProofRecordDB, ChainStateDB
from .proof_repository import ProofRepository, GENESIS_HASH

__all__ = [
    # Database lifecycle
    "init_db",
    "close_db",
    "get_session",
    "Base",
    # Models
    "ProofRecordDB",
    "ChainStateDB",
    # Repositories
    "ProofRepository",
    "GENESIS_HASH",
]
