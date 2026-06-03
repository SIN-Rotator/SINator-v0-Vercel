"""Pool Return mixin.

Docs: return.doc.md
"""
import json
import re
import time
import uuid
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class PoolManagerReturnMixin:
    """Auto-generated mixin from pool_manager.py split."""

    def return_key(self, key_id: str, lease_id: Optional[str] = None) -> bool:
        """
        Returns a leased key, making it available again.

        Args:
            key_id: ID of the key to return
            lease_id: Optional lease_id for verification

        Returns:
            True if key was found and returned
        """
        self.reload()
        for key in self.keys:
            if key["id"] == key_id:
                if lease_id and key.get("lease_id") != lease_id:
                    logger.warning(f"Lease ID mismatch for key {key_id[:8]}...")
                    return False
                key["leased_until"] = None
                key["leased_to"] = None
                key["lease_id"] = None
                key["leased_at"] = None
                self.save()
                _emit_event("key_returned", {
                    "key_id": key_id,
                    "from": key.get("leased_to", "unknown"),
                })
                logger.info(f"Key returned: {key_id[:8]}...")
                return True
        return False

    def expire_leases(self) -> int:
        """
        Expires all leases whose TTL has passed. Called automatically
        before lease_key() and in get_stats().

        Returns:
            Number of leases expired
        """
        now = time.time()
        expired = 0
        for key in self.keys:
            leased_until = key.get("leased_until")
            if leased_until is not None and leased_until <= now:
                key["leased_until"] = None
                key["leased_to"] = None
                key["lease_id"] = None
                key["leased_at"] = None
                expired += 1
        if expired > 0:
            self.save()
            logger.info(f"Expired {expired} lease(s)")
        return expired

    def get_leased_keys(self) -> List[Dict[str, Any]]:
        """
        Returns all currently leased keys (active leases only).

        Returns:
            List of leased key dicts
        """
        self.reload()
        self.expire_leases()
        now = time.time()
        leased = []
        for key in self.keys:
            if key.get("used", False) or key.get("suspended", False):
                continue
            leased_until = key.get("leased_until")
            if not key.get("used", False) and leased_until is not None and leased_until > now:
                hydrated = self._hydrate_key(key)
                leased.append({
                    "id": key["id"],
                    "alias_email": key["alias_email"],
                    "key_name": key.get("key_name", ""),
                    "api_key": hydrated["api_key"],
                    "leased_to": key.get("leased_to"),
                    "lease_id": key.get("lease_id"),
                    "leased_at": key.get("leased_at"),
                    "leased_until": leased_until,
                })
        return leased

