"""
Pool lease endpoints — key leasing and returning.

Docs: pool_lease.doc.md
"""
from fastapi import APIRouter, HTTPException, Depends

from agent_toolbox.api.routes.pool_deps import logger, verify_auth_token
from agent_toolbox.core.pool_manager import get_pool_manager
from agent_toolbox.core.keychain_store import hydrate_single as _hydrate_single

router = APIRouter(tags=["Pool Lease"])
lease_router = APIRouter(tags=["Pool Lease"])


@router.post("/lease")
async def lease_key(request: dict, _=Depends(verify_auth_token)):
    """
    Lease an available key atomically with TTL.

    Body: {
      "ttl_seconds": 1800,        // Lease duration (default 30min)
      "leased_to": "proxy-1",     // Identifier of lessee
      "lease_backup": false       // Also lease a backup key?
    }

    Returns:
      200 + key info + lease_id + expires_at
      404 if no available keys
    """
    pool_mgr = get_pool_manager()
    ttl_seconds = request.get("ttl_seconds", 1800)
    leased_to = request.get("leased_to", "proxy")
    lease_backup = request.get("lease_backup", False)

    result = pool_mgr.lease_key(
        ttl_seconds=ttl_seconds,
        leased_to=leased_to,
        lease_backup=lease_backup,
    )

    if not result:
        raise HTTPException(status_code=404, detail="No available keys to lease")

    # Hydrate api_key from keychain if it's still the SENTINEL placeholder.
    if not result.get("api_key"):
        hydrated = _hydrate_single(dict(result))
        if hydrated.get("api_key"):
            result["api_key"] = hydrated["api_key"]
        if result.get("backup") and not result["backup"].get("api_key"):
            backup_hydrated = _hydrate_single(dict(result["backup"]))
            if backup_hydrated.get("api_key"):
                result["backup"]["api_key"] = backup_hydrated["api_key"]

    return {
        "status": "success",
        "api_key": result["api_key"],
        "key_id": result["key_id"],
        "lease_id": result["lease_id"],
        "expires_at": result["expires_at"],
        "alias_email": result["alias_email"],
        "key_name": result.get("key_name", ""),
        "backup": result.get("backup"),
    }


@router.post("/return")
async def return_leased_key(request: dict, _=Depends(verify_auth_token)):
    """
    Return a leased key, making it available again.

    Body: {"key_id": "xxx"} or {"key_id": "xxx", "lease_id": "yyy"}

    Returns:
      200 if key was returned
      404 if key not found
      400 if lease_id mismatch
    """
    pool_mgr = get_pool_manager()
    key_id = request.get("key_id")
    lease_id = request.get("lease_id")

    if not key_id:
        raise HTTPException(status_code=400, detail="Missing 'key_id' in request body")

    success = pool_mgr.return_key(key_id=key_id, lease_id=lease_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Key '{key_id}' not found or lease_id mismatch")

    return {"status": "success", "key_id": key_id}


@lease_router.get("/pool-lease")
async def lease_key_get(leased_to: str = "dashboard", ttl_seconds: int = 1800):
    """Lease a key via GET (Dashboard compatibility — same as POST /pool/lease)."""
    pool_mgr = get_pool_manager()
    result = pool_mgr.lease_key(ttl_seconds=ttl_seconds, leased_to=leased_to)
    if not result:
        raise HTTPException(status_code=404, detail="No available keys to lease")
    # Hydrate api_key from keychain if it's still the SENTINEL placeholder.
    if not result.get("api_key"):
        hydrated = _hydrate_single(dict(result))
        if hydrated.get("api_key"):
            result["api_key"] = hydrated["api_key"]
    return {
        "status": "success",
        "api_key": result["api_key"],
        "key_id": result["key_id"],
        "lease_id": result["lease_id"],
        "expires_at": result["expires_at"],
        "alias_email": result["alias_email"],
        "key_name": result.get("key_name", ""),
    }
