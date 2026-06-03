"""Pool Lease mixin.

Docs: lease.doc.md
"""
import json
import re
import time
import uuid
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class PoolManagerLeaseMixin:
    """Auto-generated mixin from pool_manager.py split."""

    def lease_key(self, ttl_seconds: int = 1800, leased_to: str = "proxy",
                  lease_backup: bool = False) -> Optional[Dict[str, Any]]:
        """
        Leases an available key atomically. Key becomes unavailable to other
        consumers until the lease expires or is returned.

        Args:
            ttl_seconds: Lease duration in seconds (default 30min)
            leased_to: Identifier of the lessee (e.g. "proxy-macbook-1")
            lease_backup: If True, also lease a second key as backup

        Returns:
            Dict with api_key, key_id, lease_id, expires_at or None
        """
        self.reload()
        self.expire_leases()
        now = time.time()
        expires_at = now + ttl_seconds
        for key in self.keys:
            if key.get("used", False) or key.get("suspended", False):
                continue
            leased_until = key.get("leased_until")
            if leased_until is not None and leased_until > now:
                continue
            lease_id = uuid.uuid4().hex[:12]
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
            logger.info(f"Key leased: {key['id'][:8]}... → {leased_to} (TTL={ttl_seconds}s)")
            hydrated = self._hydrate_key(key)
            result = {
                "api_key": hydrated["api_key"],
                "key_id": key["id"],
                "lease_id": lease_id,
                "expires_at": expires_at,
                "alias_email": key["alias_email"],
                "key_name": key.get("key_name", ""),
            }
            if lease_backup:
                backup = self.lease_key(ttl_seconds=ttl_seconds, leased_to=leased_to + "-backup")
                if backup:
                    result["backup"] = backup
            return result
        logger.warning("No available keys to lease")
        return None

