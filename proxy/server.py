"""
Fireworks Pool Proxy — aiohttp-based async proxy with SSE streaming.

Features:
  - SSE streaming for chat/completions (CRITICAL — old proxy couldn't do this)
  - Auto-swap on 401/402/403/412/429 errors
  - Lease-based key management (atomic, TTL-based)
  - Pre-fetch backup key for 0ms swap
  - Health + status endpoints

Usage:
  python -m proxy.server
  SIN_PROXY_PORT=8888 python -m proxy.server

Docs: server.doc.md
"""
import os
import sys
import asyncio
import logging
import time
import json
from pathlib import Path
from typing import Any, Dict, Optional

import aiohttp
from aiohttp import web

_script_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_script_dir))
sys.path.insert(0, str(_script_dir.parent))

try:
    from proxy.config import load_config, FIREWORKS_BASE
    from proxy.pool_client import PoolClient
    from proxy.key_cache import KeyCache
except ImportError:
    from config import load_config, FIREWORKS_BASE
    from pool_client import PoolClient
    from key_cache import KeyCache

try:
    from proxy.config import AGENT_ID
except ImportError:
    from config import AGENT_ID

try:
    from proxy.key_lifecycle import KeyLifecycleMixin
except ImportError:
    from key_lifecycle import KeyLifecycleMixin

try:
    from proxy.handlers import ProxyHandlersMixin
except ImportError:
    from handlers import ProxyHandlersMixin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("pool-proxy")

POOL_AUTH_TOKEN = os.environ.get("SINATOR_AUTH_TOKEN", "").strip()
NO_BACKUP = os.environ.get("SIN_NO_BACKUP", "false").lower() == "true"

PUBLIC_PROXY_PATHS = ("/health", "/pool-status", "/v1/models")

CORS_ALLOW_HEADERS = "Authorization, Content-Type, Accept, Origin"

@web.middleware
async def _cors_middleware(request: web.Request, handler) -> web.Response:
    origin = request.headers.get("Origin", "*")
    cors_hdrs = {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": CORS_ALLOW_HEADERS,
        "Access-Control-Max-Age": "86400",
    }
    if request.method == "OPTIONS":
        return web.Response(status=204, headers=cors_hdrs)
    resp = await handler(request)
    for k, v in cors_hdrs.items():
        resp.headers[k] = v
    return resp

@web.middleware
async def _pool_auth_middleware(request: web.Request, handler) -> web.Response:
    if not POOL_AUTH_TOKEN:
        return await handler(request)
    path = request.path
    if path in PUBLIC_PROXY_PATHS:
        return await handler(request)
    peer = request.transport.get_extra_info("peername")
    if peer:
        host = peer[0]
        if host.startswith("::ffff:"):
            host = host[7:]
        if host in ("127.0.0.1", "::1"):
            return await handler(request)
    if path.startswith("/inference/") or path.startswith("/v1/") or path == "/pool-lease":
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {POOL_AUTH_TOKEN}":
            return web.json_response(
                {"error": "unauthorized", "message": "Invalid or missing auth token"},
                status=401,
            )
    return await handler(request)


class PoolProxy(KeyLifecycleMixin, ProxyHandlersMixin):
    DEAD_KEY_CODES = {401, 402, 403, 412}
    SWAP_REASONS = {
        401: "unauthorized",
        402: "credits_exhausted",
        403: "suspended",
        412: "suspended",
        429: "rate_limited",
    }
    PERMANENT_429_KEYWORDS = ("account.*suspended", "monthly spending limit", "reached.*limit", "suspended due to", "spending limit")
    # Keine "monthly" oder "quota exceeded" allein — zu viele False Positives

    # Alle Codes werden VERIFIZIERT (Body-Check + /chat/completions) bevor ein Swap passiert.
    # NICHTS wird blind als "tot" angenommen — auch 402 nicht.
    PERMANENT_ERROR_KEYWORDS = ("suspended", "deactivated", "disabled", "invalid api key", "revoked", "expired", "payment required")
    CONFIRMED_DEAD_CODES = set()  # LEER — alles wird verifiziert
    MAYBE_DEAD_CODES = {401, 402, 403, 412}

    MAX_CONSECUTIVE_SWAPS = 2

    def __init__(self):
        cfg = load_config()
        self.port = cfg.get("proxy_port", 8888)
        self.fireworks_base = cfg.get("fireworks_base", FIREWORKS_BASE)
        self.max_retries = cfg.get("max_retries", 3)
        self.pool_client = PoolClient(cfg.get("pool_api_url"))
        self.fw_session: Optional[aiohttp.ClientSession] = None
        # V19.10: Unique proxy ID — port + random suffix.
        # Before: f"proxy-{int(time.time())}" — all 10 proxies in start-multi.sh
        # started within the same second, so they ALL got the same ID.
        # This caused 52+20 leases to pile up under one leased_to and
        # made the pool unusable (only 12 available of 256 total).
        import random as _random
        self.proxy_id = f"proxy-{self.port}-{_random.randint(1000, 9999)}"
        self.agent_id = getattr(load_config(), 'agent_id', AGENT_ID)  # V19.14
        try:
            from proxy.key_cache import AgentKeyCache
        except ImportError:
            from key_cache import AgentKeyCache
        self.cache = AgentKeyCache(agent_id=self.agent_id)
        # V19.14 Phase 2: Per-session AgentKeyCaches, keyed by x-agent-id header
        self._session_caches: Dict[str, Any] = {}
        self._session_caches[self.agent_id] = self.cache  # default proxy cache
        self.no_backup = NO_BACKUP

    def _get_session_cache(self, agent_id: str):
        """V19.14 Phase 2: Get or create AgentKeyCache for a session agent_id."""
        if agent_id not in self._session_caches:
            try:
                from proxy.key_cache import AgentKeyCache
            except ImportError:
                from key_cache import AgentKeyCache
            self._session_caches[agent_id] = AgentKeyCache(agent_id=agent_id)
            logger.info(f"V19.14: New session cache for {agent_id} (total sessions: {len(self._session_caches)})")
        return self._session_caches[agent_id]

    def create_app(self) -> web.Application:
        app = web.Application()
        app.middlewares.append(_cors_middleware)
        app.middlewares.append(_pool_auth_middleware)
        app.router.add_get("/health", self._health)
        app.router.add_get("/pool-status", self._pool_status)
        app.router.add_get("/pool-lease", self._lease_key)
        app.router.add_get("/v1/models", self._handle_v1_models)
        app.router.add_get("/inference/v1/models", self._handle_v1_models)
        app.router.add_route("*", "/inference/v1/{path:.*}", self._handle_proxy)
        app.router.add_route("*", "/v1/{path:.*}", self._handle_proxy_v1)
        app.on_startup.append(self._on_startup)
        app.on_shutdown.append(self._on_shutdown)
        return app

    async def _on_startup(self, app):
        self.fw_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=300, sock_read=120),
        )
        logger.info(f"Pool Proxy starting on :{self.port}")
        logger.info(f"  Fireworks base: {self.fireworks_base}")
        logger.info(f"  Pool API: {self.pool_client.pool_api_url}")

    async def _on_shutdown(self, app):
        """V19.14: Release ALL session keys on shutdown."""
        for agent_id, cache in list(self._session_caches.items()):
            if cache.primary:
                await self.pool_client.release_agent_key(
                    agent_id,
                    cache.primary.get("key_id", ""),
                )
                logger.info(f"Released session key for {agent_id}")
        await self.pool_client.close()
        if self.fw_session:
            await self.fw_session.close()

    async def _health(self, request: web.Request) -> web.Response:
        key = self.cache.get_primary()
        return web.json_response({
            "status": "ok" if key else "no_key",
            "proxy_id": self.proxy_id,
            "primary_key": key.get("key_id", "")[:8] + "..." if key else None,
            "primary_alias": key.get("alias_email") if key else None,
            "backup_key": self.cache.backup.get("key_id", "")[:8] + "..." if self.cache.backup else None,
            "request_count": self.cache.request_count,
        })

    async def _lease_key(self, request: web.Request) -> web.Response:
        """Lease a single API key from the pool."""
        try:
            leased_to = request.query.get("leased_to", f"app-{time.time():.0f}")
            result = await self.pool_client.lease(leased_to=leased_to)
            if not result:
                return web.json_response(
                    {"error": "no_keys", "message": "No API keys available"},
                    status=503,
                )
            return web.json_response({
                "api_key": result["api_key"],
                "key_name": result.get("key_name", ""),
                "alias_email": result.get("alias_email", ""),
                "key_id": result.get("key_id", ""),
            })
        except Exception as e:
            logger.error(f"Lease key error: {e}")
            return web.json_response(
                {"error": "lease_failed", "message": str(e)},
                status=500,
            )

    async def _pool_status(self, request: web.Request) -> web.Response:
        stats = await self.pool_client.stats()
        cache_status = self.cache.status()
        return web.json_response({
            "pool": stats,
            "cache": cache_status,
            "proxy_id": self.proxy_id,
        })


def main():
    import urllib.request
    backend_wait = int(os.environ.get("SIN_BACKEND_WAIT", "5"))
    backend_url = os.environ.get("SIN_BACKEND_HEALTH_URL", "http://localhost:8100/health")
    for i in range(backend_wait):
        try:
            urllib.request.urlopen(backend_url, timeout=2)
            logger.info(f"✅ Backend ready (waited {i}s) at {backend_url}")
            break
        except Exception:
            if i == 0:
                logger.info(f"⏳ Waiting for backend at {backend_url} (max {backend_wait}s)...")
            time.sleep(1)
    else:
        logger.warning(f"⚠️ Backend not ready at {backend_url} — proxy will start anyway")

    proxy = PoolProxy()
    app = proxy.create_app()
    web.run_app(app, host="127.0.0.1", port=proxy.port, print=logger.info)


if __name__ == "__main__":
    main()
