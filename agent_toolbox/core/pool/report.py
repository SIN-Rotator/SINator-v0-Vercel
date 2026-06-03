"""Pool Report mixin.

Docs: report.doc.md
"""
import json
import re
import time
import uuid
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class PoolManagerReportMixin:
    """Auto-generated mixin from pool_manager.py split."""

    def report_key(self, api_key: Optional[str] = None, key_id: Optional[str] = None,
                   reason: str = "unknown", leased_to: str = "proxy",
                   ttl_seconds: int = 1800) -> Optional[Dict[str, Any]]:
        """
        Report a key as bad (suspended/rate-limited/invalid). Marks it as suspended
        (NOT used!), leases a replacement key atomically, and returns the new key.

        This replaces the old pattern of report() + separate lease() which caused
        double-key waste (2 keys touched per swap).

        Args:
            api_key: API key string to find (alternative to key_id)
            key_id: Key ID to find
            reason: Why the key was reported
            leased_to: Identifier for the lease (e.g. "proxy-8888")
            ttl_seconds: Lease TTL (default 30min)

        Returns:
            Dict with new_key info (including lease_id, expires_at) or None
        """
        import uuid as _uuid
        self.reload()
        self.expire_leases()
        found_id = key_id
        if not found_id and api_key:
            for k in self.keys:
                if k.get("api_key") == api_key:
                    found_id = k["id"]
                    break
        if not found_id:
            return None
        old_alias = ""
        for k in self.keys:
            if k["id"] == found_id:
                old_alias = k.get("alias_email", "")
                break

        # Suspend the old key
        self.mark_suspended(found_id, reason=reason)
        _emit_event("key_swapped", {
            "old_key_id": found_id,
            "old_alias": old_alias,
            "reason": reason,
        })
        logger.info(f"Key reported as {reason}: {found_id[:8]}...")

        # Atomically lease a replacement key (same logic as lease_key)
        now = time.time()
        expires_at = now + ttl_seconds
        for key in self.keys:
            if key.get("used", False) or key.get("suspended", False):
                continue
            leased_until = key.get("leased_until")
            if leased_until is not None and leased_until > now:
                continue
            lease_id = _uuid.uuid4().hex[:12]
            key["leased_until"] = expires_at
            key["leased_to"] = leased_to
            key["lease_id"] = lease_id
            key["leased_at"] = now
            self.save()
            _emit_event("key_leased", {
                "key_id": key["id"],
                "lease_id": lease_id,
                "leased_to": leased_to,
                "expires_at": expires_at,
            })
            logger.info(f"Replacement key leased: {key['id'][:8]}... → {leased_to} (TTL={ttl_seconds}s)")
            hydrated = self._hydrate_key(key)
            return {
                "status": "swapped",
                "new_api_key": hydrated["api_key"],
                "new_key_id": key["id"],
                "new_alias": key.get("alias_email", ""),
                "new_key_name": key.get("key_name", ""),
                "lease_id": lease_id,
                "expires_at": expires_at,
            }

        logger.warning("No replacement key available after report")
        return {"status": "no_keys_available", "swapped": False}


_SSE_LISTENERS: List = []


