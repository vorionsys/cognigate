"""
API Key Management Router

Port of apps/cognigate-api/src/middleware/auth.ts key management to Python/FastAPI.
Provides CRUD for API keys used to authenticate with the Cognigate API.
"""

import secrets
import hashlib
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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
async def create_key(body: CreateKeyRequest) -> dict:
    """
    Create a new API key. The raw key is returned **only once** in this response.
    Store it securely — it cannot be retrieved again.
    """
    key_id = f"key_{secrets.token_hex(6)}"
    raw_key = f"cg_{secrets.token_hex(24)}"
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
async def list_keys() -> dict:
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
async def delete_key(key_id: str) -> None:
    """
    Delete (revoke) an API key. This is irreversible.
    """
    if key_id not in _api_keys:
        raise HTTPException(status_code=404, detail=f"API key not found: {key_id}")

    del _api_keys[key_id]
