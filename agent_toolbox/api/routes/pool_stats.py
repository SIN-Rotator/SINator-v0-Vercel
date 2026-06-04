"""
Pool statistics and read-only endpoints.

Docs: pool_stats.doc.md
"""
import time
import asyncio
import logging
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from agent_toolbox.api.routes.pool_deps import logger
from agent_toolbox.core.pool_manager import get_pool_manager
from agent_toolbox.core.keychain_store import migrate_pool as _migrate_pool, hydrate_single as _hydrate_single

router = APIRouter(tags=["API Key Pool"])


@router.get("/stats")
async def get_pool_stats():
    """
    Liefert Statistiken über den API-Key-Pool.
    """
    start_time = time.time()
    pool_mgr = get_pool_manager()

    try:
        stats = pool_mgr.get_stats()
        elapsed = time.time() - start_time

        from agent_toolbox.api.schemas import PoolStatsResponse
        return PoolStatsResponse(
            status="success",
            total=stats["total"],
            used=stats["used"],
            suspended=stats.get("suspended", 0),
            leased=stats.get("leased", 0),
            available=stats["available"],
            assigned=stats.get("assigned", 0),
            shared=stats.get("shared", 0),
            keys=stats["keys"],
            execution_time=f"{elapsed:.2f}s",
        )

    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Pool-Statistiken fehlgeschlagen: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/key")
async def get_api_key():
    """
    Liefert den nächsten verfügbaren API-Key (hydratisiert aus Keychain).
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


@router.get("/events")
async def pool_events():
    """
    SSE stream for dashboard live updates.

    Events:
      key_leased   — key was leased by a proxy
      key_returned — key was returned
      key_swapped  — bad key was swapped for a new one
      stats        — periodic pool stats update (every 30s)
    """
    from agent_toolbox.core.pool.sse import register_sse_listener, unregister_sse_listener
    queue = register_sse_listener()

    async def event_generator():
        try:
            stats_interval = 30
            last_stats = time.time()
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=1.0)
                    event_type = payload.get("event", "stats")
                    data = payload.get("data", {})
                    yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    pass
                now = time.time()
                if now - last_stats >= stats_interval:
                    pool_mgr = get_pool_manager()
                    stats = pool_mgr.get_stats()
                    yield f"event: stats\ndata: {json.dumps({'total': stats['total'], 'used': stats['used'], 'leased': stats['leased'], 'available': stats['available']})}\n\n"
                    last_stats = now
        except asyncio.CancelledError:
            pass
        finally:
            unregister_sse_listener(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
    from agent_toolbox.core.keychain_store import retrieve_key as _retrieve_from_keychain, SENTINEL as _KC_SENTINEL

    pool_path = Path("data/fireworksai-pool.json")
    if not pool_path.exists():
        return {"status": "empty", "healthy": 0, "suspended": 0, "total": 0, "checked": []}

    all_keys = json.loads(pool_path.read_text())
    if not all_keys:
        return {"status": "empty", "healthy": 0, "suspended": 0, "total": 0, "checked": []}

    async def check_key(k: dict) -> dict:
        key_id = k.get("id", "?")
        raw_api_key = k.get("api_key", "")
        if raw_api_key == _KC_SENTINEL:
            api_key = _retrieve_from_keychain(key_id) or ""
        else:
            api_key = raw_api_key
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


@router.get("/reveal/{key_id}")
async def reveal_key(key_id: str):
    """
    Gibt den echten API-Key für einen Pool-Eintrag zurück (aus Keychain).
    Nur für localhost/Tauri Dashboard — nicht öffentlich exponieren.
    """
    pool_mgr = get_pool_manager()
    pool_mgr.reload()
    for k in pool_mgr.keys:
        if k["id"] == key_id:
            hydrated = pool_mgr._hydrate_key(k)
            return {
                "status": "success",
                "api_key": hydrated.get("api_key", ""),
                "key_id": key_id,
                "alias_email": k.get("alias_email", ""),
            }
    raise HTTPException(status_code=404, detail="Key not found")
