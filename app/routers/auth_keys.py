"""
API Key Management Router

Port of apps/cognigate-api/src/middleware/auth.ts key management to Python/FastAPI.
Provides CRUD for API keys used to authenticate with the Cognigate API.
"""

import secrets
import hashlib
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import validate_api_key_strength, verify_api_key

router = APIRouter()


# =============================================================================
# IN-MEMORY KEY STORE
# =============================================================================

_api_keys: dict[str, dict[str, Any]] = {}


# =============================================================================
# REQUEST MODELS
# =============================================================================

class CreateKeyRequest(BaseModel):
    name: str
    scopes: list[str] = ["read", "write"]


# =============================================================================
# HELPERS
# =============================================================================

def _hash_key(raw_key: str) -> str:
    """Hash an API key for storage (never store raw keys)."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


# =============================================================================
# ROUTES
# =============================================================================

@router.post("/auth/keys", status_code=201, summary="Create API key")
async def create_key(body: CreateKeyRequest, _: str = Depends(verify_api_key)) -> dict:
    """
    Create a new API key. The raw key is returned **only once** in this response.
    Store it securely — it cannot be retrieved again.
    """
    key_id = f"key_{secrets.token_hex(6)}"
    raw_key = f"cg_{secrets.token_hex(24)}"

    # IA-5(1): Validate key strength before storing
    is_valid, reason = validate_api_key_strength(raw_key)
    if not is_valid:
        # Regenerate once — cryptographically random keys should always pass,
        # but defense-in-depth requires verification.
        raw_key = f"cg_{secrets.token_hex(24)}"
        is_valid, reason = validate_api_key_strength(raw_key)
        if not is_valid:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate sufficiently strong API key: {reason}",
            )

    hashed = _hash_key(raw_key)

    _api_keys[key_id] = {
        "keyId": key_id,
        "name": body.name,
        "hashedKey": hashed,
        "scopes": body.scopes,
        "createdAt": datetime.utcnow().isoformat(),
        "lastUsedAt": None,
    }

    return {
        "keyId": key_id,
        "name": body.name,
        "key": raw_key,
        "scopes": body.scopes,
        "createdAt": _api_keys[key_id]["createdAt"],
        "warning": "Store this key securely. It will not be shown again.",
    }


@router.get("/auth/keys", summary="List API keys")
async def list_keys(_: str = Depends(verify_api_key)) -> dict:
    """
    List all API keys. Raw keys are never shown — only metadata.
    """
    keys = []
    for key_data in _api_keys.values():
        keys.append({
            "keyId": key_data["keyId"],
            "name": key_data["name"],
            "scopes": key_data["scopes"],
            "createdAt": key_data["createdAt"],
            "lastUsedAt": key_data["lastUsedAt"],
        })

    return {"keys": keys, "count": len(keys)}


@router.delete("/auth/keys/{key_id}", status_code=204, summary="Delete API key")
async def delete_key(key_id: str, _: str = Depends(verify_api_key)) -> None:
    """
    Delete (revoke) an API key. This is irreversible.
    """
    if key_id not in _api_keys:
        raise HTTPException(status_code=404, detail=f"API key not found: {key_id}")

    del _api_keys[key_id]
