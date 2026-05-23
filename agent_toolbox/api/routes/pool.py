"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              SINATOR AGENT-TOOLBOX — Pool Routes                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ENDPOINTS:                                                                   ║
║  GET  /pool/stats        → API-Key-Pool Status                              ║
║  POST /pool/add          → API-Key zum Pool hinzufügen                      ║
║  POST /pool/use          → API-Key als verwendet markieren                  ║
║  GET  /pool/key          → Nächsten verfügbaren API-Key (Klartext)          ║
║  GET  /pool/health       → Validiert alle Keys via Fireworks API            ║
║  DELETE /pool/{key_id}   → API-Key aus Pool löschen                         ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
import time
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from agent_toolbox.core.pool_manager import get_pool_manager
from agent_toolbox.api.schemas import (
    PoolStatsResponse,
    PoolAddKeyRequest,
    PoolAddKeyResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/pool", tags=["API Key Pool"])


@router.get("/stats", response_model=PoolStatsResponse)
async def get_pool_stats():
    """
    Liefert Statistiken über den API-Key-Pool.
    """
    start_time = time.time()
    pool_mgr = get_pool_manager()

    try:
        stats = pool_mgr.get_stats()
        elapsed = time.time() - start_time

        return PoolStatsResponse(
            status="success",
            total=stats["total"],
            used=stats["used"],
            available=stats["available"],
            keys=stats["keys"],
            execution_time=f"{elapsed:.2f}s",
        )

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Pool-Statistiken fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add", response_model=PoolAddKeyResponse)
async def add_key_to_pool(request: PoolAddKeyRequest):
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
async def mark_key_used(key_id: str):
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


@router.get("/key")
async def get_api_key():
    """
    Liefert den nächsten verfügbaren API-Key im Klartext (für Chat/LLM).
    """
    pool_mgr = get_pool_manager()
    key = pool_mgr.get_available_key()
    if not key:
        raise HTTPException(status_code=404, detail="No available API keys")
    return {
        "status": "success",
        "api_key": key.get("api_key"),
        "key_id": key.get("id"),
        "alias_email": key.get("alias_email"),
    }


@router.post("/report")
async def report_bad_key(request: dict):
    """
    Key als verbraucht melden (Rate-Limit/Suspended).
    Markiert den Key als used und liefert einen neuen.
    
    Body: {"api_key": "fw_xxx"} oder {"key_id": "xxx"}
    
    Returns:
      200 + swapped=true + new_key wenn Key gefunden und markiert wurde
      404 wenn der gemeldete Key nicht im Pool existiert
      400 wenn kein api_key oder key_id angegeben wurde
    """
    pool_mgr = get_pool_manager()
    key_id = request.get("key_id") or request.get("id")
    api_key = request.get("api_key") or request.get("key")

    if not key_id and not api_key:
        raise HTTPException(status_code=400, detail="Missing 'api_key' or 'key_id' in request body")

    found_key_id = None
    found_key_api = None
    if key_id:
        # Verifiziere dass key_id existiert
        for k in pool_mgr.get_stats()["keys"]:
            if k["id"] == key_id:
                found_key_id = key_id
                found_key_api = k.get("api_key", "")
                break
    elif api_key:
        for k in pool_mgr.get_stats()["keys"]:
            if k.get("api_key") == api_key:
                found_key_id = k["id"]
                found_key_api = api_key
                break
        if not found_key_id:
            import json as _json
            for k in _json.loads(Path("data/fireworksai-pool.json").read_text()):
                if k.get("api_key") == api_key:
                    found_key_id = k["id"]
                    found_key_api = api_key
                    break

    if not found_key_id:
        raise HTTPException(
            status_code=404,
            detail=f"Key '{api_key or key_id}' not found in pool"
        )

    pool_mgr.mark_used(found_key_id)

    new_key = pool_mgr.get_available_key()
    if not new_key:
        return {"status": "no_keys_available", "swapped": False}

    return {
        "status": "success",
        "swapped": True,
        "new_key": new_key.get("api_key"),
        "new_key_id": new_key.get("id"),
        "new_alias": new_key.get("alias_email"),
    }


@router.get("/health")
async def check_pool_health(deep_check: bool = False):
    """
    Validiert ALLE Pool-Keys via Fireworks API.
    Markiert gesperrte Keys (401/402/403/412) automatisch als used.

    Query-Parameter:
      deep_check=false  — nur HTTP-Health-Check (schnell)
      deep_check=true   — zusätzlich CDP-Billing-Check für aktive Keys (langsam)
    """
    import httpx
    import asyncio
    import json
    from pathlib import Path

    pool_path = Path("data/fireworksai-pool.json")
    if not pool_path.exists():
        return {"status": "empty", "healthy": 0, "suspended": 0, "total": 0, "checked": []}

    all_keys = json.loads(pool_path.read_text())
    if not all_keys:
        return {"status": "empty", "healthy": 0, "suspended": 0, "total": 0, "checked": []}

    async def check_key(k: dict) -> dict:
        key_id = k.get("id", "?")
        api_key = k.get("api_key", "")
        email = k.get("alias_email", "?")
        result = {
            "key_id": key_id, "email": email, "status": "unknown",
            "credits_initial": k.get("credits_initial", 6.0),
            "credits_remaining": k.get("credits_remaining"),
            "credits_checked_at": k.get("credits_checked_at"),
        }

        if not api_key:
            result["status"] = "no_key"
            return result

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    "https://api.fireworks.ai/inference/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if r.status_code == 200:
                    result["status"] = "healthy"
                elif r.status_code in (401, 402, 403, 412):
                    result["status"] = "suspended"
                else:
                    result["status"] = f"error_{r.status_code}"
        except Exception as e:
            result["status"] = "error"
            result["error"] = str(e)[:100]

        return result

    results = await asyncio.gather(*[check_key(k) for k in all_keys])
    healthy = sum(1 for r in results if r["status"] == "healthy")
    suspended = sum(1 for r in results if r["status"] == "suspended")
    total_credits = sum(r.get("credits_remaining", 0) or 0 for r in results if r.get("credits_remaining"))

    return {
        "status": "success",
        "total": len(results),
        "healthy": healthy,
        "suspended": suspended,
        "total_credits_remaining": round(total_credits, 2),
        "checked": results,
    }


@router.delete("/{key_id}")
async def delete_key(key_id: str):
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
