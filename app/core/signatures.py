"""
Cryptographic Signature System for Cognigate Proof Records.

Provides Ed25519 digital signatures for proof record integrity.
Ed25519 is chosen for:
- Fast signing and verification
- Small signature size (64 bytes)
- Strong security (128-bit)
- Deterministic (same input = same signature)
"""

import base64
import logging
from pathlib import Path
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

# Try to import cryptography, gracefully handle if not installed
try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.exceptions import InvalidSignature
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography package not installed - signatures disabled")


class SignatureManager:
    """
    Manages Ed25519 key pairs for signing proof records.

    Keys can be:
    1. Generated in-memory (development)
    2. Loaded from files (production)
    3. Loaded from environment variables (cloud deployment)
    """

    def __init__(self):
        self._private_key: Optional[Ed25519PrivateKey] = None
        self._public_key: Optional[Ed25519PublicKey] = None
        self._initialized: bool = False

    def initialize(self, key_path: Optional[str] = None) -> bool:
        """
        Initialize the signature manager.

        Args:
            key_path: Path to private key file (PEM format).
                     If None, generates a new key pair (dev mode).

        Returns:
            bool: True if initialized successfully
        """
        if not CRYPTO_AVAILABLE:
            logger.info("signatures_disabled reason='cryptography not installed'")
            return False

        settings = get_settings()

        if key_path and Path(key_path).exists():
            # Load from file
            return self._load_key_from_file(key_path)
        elif settings.signature_private_key:
            # Load from environment
            return self._load_key_from_env(settings.signature_private_key)
        else:
            # Generate new key pair (development mode)
            return self._generate_key_pair()

    def _generate_key_pair(self) -> bool:
        """Generate a new Ed25519 key pair."""
        try:
            self._private_key = Ed25519PrivateKey.generate()
            self._public_key = self._private_key.public_key()
            self._initialized = True

            logger.warning(
                "signatures_dev_mode: Generated ephemeral key pair - not for production"
            )
            return True
        except Exception as e:
            logger.error(f"signature_key_generation_error: {e}")
            return False

    def _load_key_from_file(self, key_path: str) -> bool:
        """Load private key from PEM file."""
        try:
            with open(key_path, "rb") as f:
                self._private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,  # Add password support if needed
                )
            self._public_key = self._private_key.public_key()
            self._initialized = True

            logger.info(
                "signature_key_loaded",
                extra={"key_path": key_path}
            )
            return True
        except Exception as e:
            logger.error(f"signature_key_load_error: {e}")
            return False

    def _load_key_from_env(self, key_b64: str) -> bool:
        """Load private key from base64-encoded environment variable."""
        try:
            key_bytes = base64.b64decode(key_b64)
            self._private_key = serialization.load_pem_private_key(
                key_bytes,
                password=None,
            )
            self._public_key = self._private_key.public_key()
            self._initialized = True

            logger.info("signature_key_loaded_from_env")
            return True
        except Exception as e:
            logger.error(f"signature_key_env_load_error: {e}")
            return False

    def sign(self, data: bytes) -> Optional[str]:
        """
        Sign data with the private key.

        Args:
            data: The bytes to sign

        Returns:
            Base64-encoded signature string, or None if signing fails
        """
        if not CRYPTO_AVAILABLE or not self._initialized or not self._private_key:
            return None

        try:
            signature = self._private_key.sign(data)
            return base64.b64encode(signature).decode("utf-8")
        except Exception as e:
            logger.error(f"signature_sign_error: {e}")
            return None

    def verify(self, data: bytes, signature_b64: str) -> bool:
        """
        Verify a signature against data.

        Args:
            data: The original bytes that were signed
            signature_b64: Base64-encoded signature

        Returns:
            bool: True if signature is valid
        """
        if not CRYPTO_AVAILABLE or not self._initialized or not self._public_key:
            return False

        try:
            signature = base64.b64decode(signature_b64)
            self._public_key.verify(signature, data)
            return True
        except InvalidSignature:
            return False
        except Exception as e:
            logger.error(f"signature_verify_error: {e}")
            return False

    def get_public_key_pem(self) -> Optional[str]:
        """Get the public key in PEM format for sharing."""
        if not self._initialized or not self._public_key:
            return None

        try:
            pem = self._public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            return pem.decode("utf-8")
        except Exception as e:
            logger.error(f"signature_public_key_export_error: {e}")
            return None

    def export_private_key_pem(self) -> Optional[str]:
        """
        Export the private key in PEM format.

        WARNING: Only use for backup/migration. Never log or expose this.
        """
        if not self._initialized or not self._private_key:
            return None

        try:
            pem = self._private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            return pem.decode("utf-8")
        except Exception as e:
            logger.error(f"signature_private_key_export_error: {e}")
            return None

    @property
    def is_initialized(self) -> bool:
        """Check if signature manager is ready to use."""
        return self._initialized


def sign_proof_record(record_data: dict) -> Optional[str]:
    """
    Sign a proof record's data.

    Args:
        record_data: Dictionary containing the proof record fields

    Returns:
        Base64-encoded signature, or None if signing is disabled
    """
    import json

    if not signature_manager.is_initialized:
        return None

    # Serialize deterministically
    serialized = json.dumps(record_data, sort_keys=True, default=str)
    return signature_manager.sign(serialized.encode("utf-8"))


def verify_proof_signature(record_data: dict, signature: str) -> bool:
    """
    Verify a proof record's signature.

    Args:
        record_data: Dictionary containing the proof record fields
        signature: Base64-encoded signature

    Returns:
        bool: True if signature is valid
    """
    import json

    if not signature_manager.is_initialized:
        return False

    serialized = json.dumps(record_data, sort_keys=True, default=str)
    return signature_manager.verify(serialized.encode("utf-8"), signature)


# Global signature manager instance
signature_manager = SignatureManager()
