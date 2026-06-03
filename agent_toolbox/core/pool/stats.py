"""Pool Stats mixin.

Docs: stats.doc.md
"""
import json
import re
import time
import uuid
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class PoolManagerStatsMixin:
    """Auto-generated mixin from pool_manager.py split."""

    def get_stats(self) -> Dict[str, Any]:
        """
        Generiert Pool-Statistiken.
        available = total - used - suspended - leased (nur nicht-geleaste Keys)
        """
        self.reload()
        self.expire_leases()
        now = time.time()
        total = len(self.keys)
        used = sum(1 for k in self.keys if k.get("used", False))
        suspended = sum(1 for k in self.keys if k.get("suspended") is True and not k.get("used", False))
        leased = sum(1 for k in self.keys
                     if not k.get("used", False)
                     and not k.get("suspended", False)
                     and k.get("leased_until") is not None
                     and k.get("leased_until") > now)
        available = total - used - suspended - leased

        keys_list = []
        for k in self.keys:
            is_leased = (not k.get("used", False)
                         and not k.get("suspended", False)
                         and k.get("leased_until") is not None
                         and k.get("leased_until") > now)
            keys_list.append({
                "id": k["id"],
                "alias_email": k["alias_email"],
                "key_name": k["key_name"],
                "api_key": "",
                "created_at": k["created_at"],
                "used": k.get("used", False),
                "used_at": k.get("used_at"),
                "suspended": k.get("suspended", False),
                "suspended_at": k.get("suspended_at"),
                "suspended_reason": k.get("suspended_reason"),
                "leased": is_leased,
                "leased_to": k.get("leased_to"),
                "credits_initial": k.get("credits_initial", 6.0),
                "credits_remaining": k.get("credits_remaining", 6.0),
                "credits_checked_at": k.get("credits_checked_at"),
                "assigned_to": k.get("assigned_to"),
                "active_consumers": k.get("active_consumers", []),
                "shared_count": k.get("shared_count", 0),
            })

        return {
            "total": total,
            "used": used,
            "suspended": suspended,
            "leased": leased,
            "available": available,
            "assigned": sum(1 for k in self.keys if k.get("assigned_to") and not k.get("used") and not k.get("suspended")),
            "shared": sum(1 for k in self.keys if len(k.get("active_consumers", [])) > 1 and not k.get("used") and not k.get("suspended")),
            "keys": keys_list,
        }

    def update_credits(self, key_id: str, credits_remaining: float) -> bool:
        """
        Aktualisiert das verbleibende Guthaben eines Keys.

        Args:
            key_id: ID des Keys
            credits_remaining: Verbleibendes Guthaben in USD

        Returns:
            True wenn Key gefunden und aktualisiert
        """
        self.reload()
        for key in self.keys:
            if key["id"] == key_id:
                key["credits_remaining"] = round(credits_remaining, 2)
                key["credits_checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                self.save()
                logger.info(f"Credits aktualisiert: {key_id[:8]}... = ${credits_remaining:.2f}")
                if credits_remaining <= 0.01:
                    key["suspended"] = True
                    key["suspended_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                    key["suspended_reason"] = "credits_exhausted"
                    self.save()
                    logger.warning(f"Key suspended (0 Credits): {key_id[:8]}...")
                return True
        return False

