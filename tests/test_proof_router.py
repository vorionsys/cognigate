"""
Tests for the PROOF router endpoints.

Tests proof record creation, retrieval, verification, and querying
using the proof chain's cryptographic integrity guarantees.
"""

import pytest
from app.routers.proof import calculate_hash, ACTION_TO_DECISION


class TestCalculateHash:
    """Test the hash calculation utility."""

    def test_deterministic(self):
        data = {"a": 1, "b": "hello"}
        assert calculate_hash(data) == calculate_hash(data)

    def test_different_data_different_hash(self):
        h1 = calculate_hash({"a": 1})
        h2 = calculate_hash({"a": 2})
        assert h1 != h2

    def test_key_order_independent(self):
        h1 = calculate_hash({"a": 1, "b": 2})
        h2 = calculate_hash({"b": 2, "a": 1})
        assert h1 == h2

    def test_sha256_hex_format(self):
        h = calculate_hash({"test": True})
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_handles_datetime(self):
        """datetime values should be serialized via default=str."""
        from datetime import datetime
        h = calculate_hash({"time": datetime(2025, 1, 1)})
        assert len(h) == 64

    def test_empty_dict(self):
        h = calculate_hash({})
        assert len(h) == 64


class TestActionToDecision:
    """Test the action mapping dictionary."""

    def test_allow_maps_to_allowed(self):
        assert ACTION_TO_DECISION["allow"] == "allowed"

    def test_deny_maps_to_denied(self):
        assert ACTION_TO_DECISION["deny"] == "denied"

    def test_escalate_maps_to_escalated(self):
        assert ACTION_TO_DECISION["escalate"] == "escalated"

    def test_modify_maps_to_modified(self):
        assert ACTION_TO_DECISION["modify"] == "modified"

    def test_all_actions_covered(self):
        assert set(ACTION_TO_DECISION.keys()) == {"allow", "deny", "escalate", "modify"}
