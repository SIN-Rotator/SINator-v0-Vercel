"""
Pool CRUD and mutating endpoints.

Docs: pool_crud.doc.md
"""
import time
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends

from agent_toolbox.api.routes.pool_deps import logger, verify_auth_token
from agent_toolbox.core.pool_manager import get_pool_manager
from agent_toolbox.api.schemas import PoolAddKeyRequest, PoolAddKeyResponse
from agent_toolbox.core.keychain_store import migrate_pool as _migrate_pool

router = APIRouter(tags=["API Key Pool"])


@router.post("/add", response_model=PoolAddKeyResponse)
async def add_key_to_pool(request: PoolAddKeyRequest, _=Depends(verify_auth_token)):
    """
    Fügt einen neuen API-Key zum Pool hinzu.
    """
    start_time = time.time()
    pool_mgr = get_pool_manager()

    try:
        result = pool_mgr.add_key(
            api_key=request.api_key,
            alias_email=request.alias_email,
            key_name=request.key_name,
        )
        elapsed = time.time() - start_time

        return PoolAddKeyResponse(
            status="success",
            key_id=result["key_id"],
            execution_time=f"{elapsed:.2f}s",
        )

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Key-Hinzufügung fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/use")
async def mark_key_used(key_id: str, _=Depends(verify_auth_token)):
    """
    Markiert einen API-Key als verwendet.
    """
    start_time = time.time()
    pool_mgr = get_pool_manager()

    try:
        success = pool_mgr.mark_used(key_id)
        elapsed = time.time() - start_time

        return {
            "status": "success" if success else "not_found",
            "key_id": key_id,
            "execution_time": f"{elapsed:.2f}s",
        }

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Key-Markierung fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/report")
async def report_bad_key(request: dict, _=Depends(verify_auth_token)):
    """
    Key als verbraucht melden (Rate-Limit/Suspended).
    Markiert den Key als used und liefert einen neuen.

    Body: {"api_key": "fw_xxx"} oder {"key_id": "xxx"}
    Optional: {"reason": "suspended" | "rate_limited" | "unauthorized" | "credits_exhausted"}

    Returns:
      200 + swapped=true + new_key wenn Key gefunden und markiert wurde
      404 wenn der gemeldete Key nicht im Pool existiert
      400 wenn kein api_key oder key_id angegeben wurde
    """
    pool_mgr = get_pool_manager()
    key_id = request.get("key_id") or request.get("id")
    api_key = request.get("api_key") or request.get("key")
    reason = request.get("reason", "unknown")

    if not key_id and not api_key:
        raise HTTPException(status_code=400, detail="Missing 'api_key' or 'key_id' in request body")

    leased_to = request.get("leased_to", "proxy")
    ttl_seconds = request.get("ttl_seconds", 1800)
    result = pool_mgr.report_key(
        api_key=api_key, key_id=key_id, reason=reason,
        leased_to=leased_to, ttl_seconds=ttl_seconds,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Key '{api_key or key_id}' not found in pool"
        )

    return {
        "status": result.get("status", "success"),
        "swapped": result.get("swapped", False),
        "new_key": result.get("new_api_key"),
        "new_key_id": result.get("new_key_id"),
        "new_alias": result.get("new_alias"),
        "new_key_name": result.get("new_key_name", ""),
        "lease_id": result.get("lease_id"),
        "expires_at": result.get("expires_at"),
        "reason": reason,
    }


@router.post("/migrate-to-keychain")
async def migrate_to_keychain(dry_run: bool = False, _=Depends(verify_auth_token)):
    """
    Migriert alle Plaintext API-Keys in macOS Keychain.
    Nach der Migration enthält die Pool-JSON nur noch SENTINEL-Werte.

    Query-Parameter:
      dry_run=true  — nur zählen, nicht wirklich migrieren
    """
    from agent_toolbox.core.pool_manager import DEFAULT_POOL_PATH
    result = _migrate_pool(DEFAULT_POOL_PATH, dry_run=dry_run)
    return result


@router.delete("/{key_id}")
async def delete_key(key_id: str, _=Depends(verify_auth_token)):
    """
    Löscht einen API-Key aus dem Pool.
    """
    start_time = time.time()
    pool_mgr = get_pool_manager()

    try:
        success = pool_mgr.delete_key(key_id)
        elapsed = time.time() - start_time

        return {
            "status": "success" if success else "not_found",
            "key_id": key_id,
            "execution_time": f"{elapsed:.2f}s",
        }

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Key-Löschung fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))
