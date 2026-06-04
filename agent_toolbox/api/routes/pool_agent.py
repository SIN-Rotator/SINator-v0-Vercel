"""
Pool agent endpoints — soft-ownership key assignment.

Docs: pool_agent.doc.md
"""
from fastapi import APIRouter, HTTPException, Depends

from agent_toolbox.api.routes.pool_deps import logger, verify_auth_token
from agent_toolbox.core.pool_manager import get_pool_manager
from agent_toolbox.core.keychain_store import hydrate_single as _hydrate_single

router = APIRouter(tags=["API Key Pool"])


@router.post("/agent-key")
async def get_agent_key(request: dict, _=Depends(verify_auth_token)):
    """V19.14: Soft-ownership key assignment — never blocks.

    Body: {
      "agent_id": "opencode-main-a3f8b2c1",  // required
      "preferred_key_id": "uuid..."          // optional, for sticky
    }

    Returns:
      200 + key info, shared flag, active_consumers count
      409 if no keys available (all suspended/used)
    """
    pool_mgr = get_pool_manager()
    agent_id = request.get("agent_id")
    if not agent_id:
        raise HTTPException(status_code=400, detail="Missing 'agent_id' in request body")

    preferred_key_id = request.get("preferred_key_id")
    result = pool_mgr.get_key_for_agent(
        agent_id=agent_id,
        preferred_key_id=preferred_key_id,
    )

    if not result:
        raise HTTPException(status_code=409, detail="No keys available (all suspended/used)")

    # Safety hydration (belt-and-suspenders, same as /lease)
    if not result.get("api_key"):
        hydrated = _hydrate_single(dict(result))
        if hydrated.get("api_key"):
            result["api_key"] = hydrated["api_key"]

    return {
        "status": "success",
        "api_key": result["api_key"],
        "key_id": result["key_id"],
        "alias_email": result.get("alias_email", ""),
        "key_name": result.get("key_name", ""),
        "shared": result.get("shared", False),
        "active_consumers": result.get("active_consumers", []),
        "assigned_to": result.get("assigned_to"),
        "shared_count": result.get("shared_count", 0),
    }


@router.post("/agent-release")
async def release_agent_key(request: dict, _=Depends(verify_auth_token)):
    """V19.14: Agent releases a key.

    Body: {"agent_id": "...", "key_id": "..."}

    Returns:
      200 if key was released
      404 if key not found
    """
    pool_mgr = get_pool_manager()
    agent_id = request.get("agent_id")
    key_id = request.get("key_id")

    if not agent_id or not key_id:
        raise HTTPException(status_code=400, detail="Missing 'agent_id' or 'key_id'")

    success = pool_mgr.release_key_for_agent(agent_id=agent_id, key_id=key_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"Key '{key_id}' not found")

    return {"status": "success", "released": True, "key_id": key_id}


@router.post("/agent-heartbeat")
async def agent_heartbeat(request: dict, _=Depends(verify_auth_token)):
    """V19.14: Agent sends heartbeat to keep active_consumers alive.

    Body: {"agent_id": "...", "key_id": "..."}

    Returns:
      200 always (heartbeat is fire-and-forget)
    """
    import time as _time
    pool_mgr = get_pool_manager()
    agent_id = request.get("agent_id")
    key_id = request.get("key_id")

    if not agent_id or not key_id:
        raise HTTPException(status_code=400, detail="Missing 'agent_id' or 'key_id'")

    pool_mgr.reload()
    for k in pool_mgr.keys:
        if k["id"] == key_id:
            k["last_heartbeat"] = _time.time()
            pool_mgr.save()
            break

    return {"status": "success", "heartbeat": True}
