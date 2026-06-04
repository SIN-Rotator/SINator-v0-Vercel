"""
SINATOR AGENT-TOOLBOX — Pool Routes Facade

Re-exports all pool sub-routers so the main FastAPI app can include them
via a single import (`from agent_toolbox.api.routes.pool import router,
lease_router`).

Docs: pool.doc.md
"""
from fastapi import APIRouter

from agent_toolbox.api.routes.pool_stats import router as stats_router
from agent_toolbox.api.routes.pool_crud import router as crud_router
from agent_toolbox.api.routes.pool_lease import router as lease_router_main, lease_router
from agent_toolbox.api.routes.pool_agent import router as agent_router

# Main pool router — everything under /pool
router = APIRouter(prefix="/pool", tags=["API Key Pool"])
router.include_router(stats_router)
router.include_router(crud_router)
router.include_router(lease_router_main)
router.include_router(agent_router)

# Dashboard-compatible lease endpoint (no /pool prefix)
# lease_router is already exported by pool_lease.py and re-exported here
