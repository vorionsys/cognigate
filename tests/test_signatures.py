"""
Tests for Ed25519 cryptographic signature system.

Tests key generation, signing, verification, tamper detection,
and proof record signing/verification.
"""

import json

import pytest

from app.core.signatures import (
    SignatureManager,
    sign_proof_record,
    verify_proof_signature,
)


@pytest.fixture
def sig_manager():
    """Initialize a signature manager with ephemeral keys."""
    manager = SignatureManager()
    assert manager.initialize()  # Generates dev key pair
    return manager


class TestSignatureManagerInit:
    """Test signature manager initialization."""

    def test_uninitialized_manager(self):
        manager = SignatureManager()
        assert not manager.is_initialized

    def test_initialize_generates_keys(self, sig_manager):
        assert sig_manager.is_initialized

    def test_public_key_available(self, sig_manager):
        pem = sig_manager.get_public_key_pem()
        assert pem is not None
        assert "PUBLIC KEY" in pem

    def test_private_key_exportable(self, sig_manager):
        pem = sig_manager.export_private_key_pem()
        assert pem is not None
        assert "PRIVATE KEY" in pem

    def test_uninitialized_returns_none(self):
        manager = SignatureManager()
        assert manager.sign(b"data") is None
        assert not manager.verify(b"data", "fake_sig")
        assert manager.get_public_key_pem() is None
        assert manager.export_private_key_pem() is None


class TestSignAndVerify:
    """Test basic sign and verify operations."""

    def test_sign_returns_base64_string(self, sig_manager):
        sig = sig_manager.sign(b"hello world")
        assert sig is not None
        assert isinstance(sig, str)
        assert len(sig) > 0

    def test_verify_valid_signature(self, sig_manager):
        data = b"important data"
        sig = sig_manager.sign(data)
        assert sig_manager.verify(data, sig)

    def test_verify_rejects_tampered_data(self, sig_manager):
        data = b"original data"
        sig = sig_manager.sign(data)
        # Tamper with data
        assert not sig_manager.verify(b"tampered data", sig)

    def test_verify_rejects_wrong_signature(self, sig_manager):
        import base64
        data = b"some data"
        # Create a fake signature (64 bytes for Ed25519)
        fake_sig = base64.b64encode(b"\x00" * 64).decode("utf-8")
        assert not sig_manager.verify(data, fake_sig)

    def test_different_data_produces_different_signatures(self, sig_manager):
        sig1 = sig_manager.sign(b"data one")
        sig2 = sig_manager.sign(b"data two")
        assert sig1 != sig2

    def test_deterministic_signatures(self, sig_manager):
        """Ed25519 is deterministic: same input → same signature."""
        data = b"deterministic test"
        sig1 = sig_manager.sign(data)
        sig2 = sig_manager.sign(data)
        assert sig1 == sig2

    def test_sign_empty_data(self, sig_manager):
        sig = sig_manager.sign(b"")
        assert sig is not None
        assert sig_manager.verify(b"", sig)

    def test_sign_large_data(self, sig_manager):
        data = b"x" * 100_000
        sig = sig_manager.sign(data)
        assert sig is not None
        assert sig_manager.verify(data, sig)


class TestProofRecordSigning:
    """Test proof record signing helpers."""

    def test_sign_proof_record_returns_signature(self, sig_manager):
        # The global signature_manager needs to be initialized
        from app.core.signatures import signature_manager
        signature_manager.initialize()

        record_data = {
            "proof_id": "prf_test123",
            "chain_position": 0,
            "intent_id": "int_test",
            "decision": "allowed",
        }
        sig = sign_proof_record(record_data)
        assert sig is not None

    def test_verify_proof_record_signature(self, sig_manager):
        from app.core.signatures import signature_manager
        signature_manager.initialize()

        record_data = {
            "proof_id": "prf_test456",
            "chain_position": 1,
            "intent_id": "int_test",
            "decision": "denied",
        }
        sig = sign_proof_record(record_data)
        assert verify_proof_signature(record_data, sig)

    def test_tampered_proof_record_fails_verification(self, sig_manager):
        from app.core.signatures import signature_manager
        signature_manager.initialize()

        record_data = {
            "proof_id": "prf_tamper",
            "decision": "allowed",
        }
        sig = sign_proof_record(record_data)

        # Tamper with the record
        record_data["decision"] = "denied"
        assert not verify_proof_signature(record_data, sig)

    def test_proof_signing_deterministic(self, sig_manager):
        """Same record data produces same signature (due to sort_keys)."""
        from app.core.signatures import signature_manager
        signature_manager.initialize()

        record = {"b": 2, "a": 1}
        sig1 = sign_proof_record(record)
        sig2 = sign_proof_record(record)
        assert sig1 == sig2

    def test_key_order_doesnt_matter(self, sig_manager):
        """sort_keys=True ensures order independence."""
        from app.core.signatures import signature_manager
        signature_manager.initialize()

        record1 = {"a": 1, "b": 2}
        record2 = {"b": 2, "a": 1}
        sig1 = sign_proof_record(record1)
        sig2 = sign_proof_record(record2)
        assert sig1 == sig2


class TestCrossKeyVerification:
    """Test that signatures from one key don't verify with another."""

    def test_different_keys_dont_verify(self):
        mgr1 = SignatureManager()
        mgr1.initialize()
        mgr2 = SignatureManager()
        mgr2.initialize()

        data = b"cross-key test"
        sig = mgr1.sign(data)
        # Different key should not verify
        assert not mgr2.verify(data, sig)
