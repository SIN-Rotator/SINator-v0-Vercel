"""
Pool Proxy key lifecycle methods — ensure, swap, verify, backup.

Docs: key_lifecycle.doc.md
"""
import asyncio
import logging
import time
from typing import Dict, Any, Optional

import aiohttp
from aiohttp import web

logger = logging.getLogger("pool-proxy")


class KeyLifecycleMixin:
    """Mixin for key lifecycle management in PoolProxy."""

    async def _ensure_key(self, agent_id: str = None):
        """V19.14: Soft-ownership — never blocks, never retries.

        Uses per-session AgentKeyCache if x-agent-id header is present.
        Falls back to proxy's default agent_id.
        """
        if agent_id is None:
            agent_id = self.agent_id

        # Get the right cache for this session
        cache = self._get_session_cache(agent_id)

        # 1. Cache hit
        key = cache.get_primary()
        if key:
            return key

        # 2. Get from backend (no retry loop!)
        result = await self.pool_client.get_agent_key(
            agent_id=agent_id,
            preferred_key_id=cache.preferred_key_id,
        )

        if result and result.get("api_key"):
            cache.set_primary(result)
            return result

        return None

    @staticmethod
    def _lease_to_key_info(lease: dict) -> dict:
        return {
            "api_key": lease["api_key"],
            "key_id": lease["key_id"],
            "lease_id": lease.get("lease_id", ""),
            "expires_at": lease.get("expires_at", 0),
            "alias_email": lease.get("alias_email", ""),
            "key_name": lease.get("key_name", ""),
        }

    async def _fetch_backup(self):
        """V19.14: No backup keys needed — sharing is the fallback."""
        pass

    async def _swap_key(self, reason: str) -> Optional[dict]:
        old = self.cache.primary
        if old:
            report_result = await self.pool_client.report(
                key_id=old.get("key_id"),
                api_key=old.get("api_key"),
                reason=reason,
                leased_to=self.proxy_id,
            )
            self.cache.clear_primary()
            # Use the replacement key returned by report() (already leased atomically)
            if report_result and report_result.get("new_api_key"):
                key_info = {
                    "api_key": report_result["new_api_key"],
                    "key_id": report_result.get("new_key_id", ""),
                    "lease_id": report_result.get("lease_id", ""),
                    "expires_at": report_result.get("expires_at", 0),
                    "alias_email": report_result.get("new_alias", ""),
                    "key_name": report_result.get("new_key_name", ""),
                }
                self.cache.set_primary(key_info)
                logger.info(f"Key swapped ({reason}): new key {key_info.get('key_id','?')[:8]}... (from report+lease)")
                return key_info

        # Fallback: report didn't return a replacement → lease one
        if not getattr(self, "no_backup", False):
            promoted = self.cache.promote_backup()
            if promoted:
                asyncio.create_task(self._fetch_backup())
                return promoted
        lease_result = await self.pool_client.lease(leased_to=self.proxy_id)
        if not lease_result:
            logger.error("No replacement key available!")
            return None
        key_info = self._lease_to_key_info(lease_result)
        self.cache.set_primary(key_info)
        if not getattr(self, "no_backup", False):
            if lease_result.get("backup"):
                self.cache.set_backup(self._lease_to_key_info(lease_result["backup"]))
            else:
                asyncio.create_task(self._fetch_backup())
        logger.info(f"Key swapped ({reason}): new key {key_info.get('key_id','?')[:8]}...")
        return key_info

    async def _verify_key_dead(self, api_key: str) -> bool:
        """Verify key via lightweight chat request — more accurate than /models."""
        try:
            body = {
                "model": "accounts/fireworks/models/deepseek-v4-flash",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 1,
                "stream": False,
            }
            async with self.fw_session.post(
                f"{self.fireworks_base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                if r.status == 200:
                    return False
                text = await r.text()
                is_dead = any(kw in text.lower() for kw in getattr(self, "PERMANENT_ERROR_KEYWORDS", ()))
                logger.debug(f"Key verification: HTTP {r.status}, dead={is_dead}, body={text[:120]}")
                return is_dead
        except Exception:
            return False

    async def _ensure_key_with_retry(self, agent_id: str = None, max_attempts: int = 5, delay: float = 2.0) -> Optional[Dict[str, Any]]:
        """V19.14: Short retry for transient empty-pool resets (max 5 attempts, 2s each).

        Down from 300 attempts (5min) in V19.12. Soft-ownership means keys
        are never permanently blocked by leases.
        """
        for attempt in range(max_attempts):
            key_info = await self._ensure_key(agent_id=agent_id)
            if key_info:
                return key_info
            if attempt < max_attempts - 1:
                await asyncio.sleep(delay)
        return None
