"""Pool Crud mixin.

Docs: crud.doc.md
"""
import json
import re
import time
import uuid
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class PoolManagerCrudMixin:
    """Auto-generated mixin from pool_manager.py split."""

    def add_key(self, api_key: str, alias_email: str, key_name: str = "sinator-key",
                credits_initial: float = 6.0) -> Dict[str, Any]:
        """
        Fügt einen neuen API-Key zum Pool hinzu.

        Args:
            api_key: Fireworks API-Key
            alias_email: Zugehörige GMX Alias-Email
            key_name: Name des Keys
            credits_initial: Startguthaben in USD (default 6.0 = $6 Free Credits)

        Returns:
            Dict mit status und key_id
        """
        self.reload()
        key_id = str(uuid.uuid4())
        now_ts = time.time()
        _store_to_keychain(key_id, api_key)
        key_entry = {
            "id": key_id,
            "api_key": _KEYCHAIN_SENTINEL,
            "alias_email": alias_email,
            "key_name": key_name,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "used": False,
            "used_at": None,
            "credits_initial": credits_initial,
            "credits_remaining": credits_initial,
            "credits_checked_at": None,
            "assigned_to": None,
            "active_consumers": [],
            "shared_count": 0,
            "last_heartbeat": now_ts,
        }

        self.keys.append(key_entry)
        self.save()

        logger.info(f"Neuer API-Key hinzugefügt: {key_entry['id'][:8]}...")
        return {
            "status": "success",
            "key_id": key_entry["id"],
        }

    def get_available_key(self) -> Optional[Dict[str, Any]]:
        """
        Liefert den nächsten unverwendeten, nicht-suspended und nicht-geleasten API-Key.
        """
        self.reload()
        self.expire_leases()
        now = time.time()
        for key in self.keys:
            if key.get("used", False) or key.get("suspended", False):
                continue
            leased_until = key.get("leased_until")
            if leased_until is not None and leased_until > now:
                continue
            return self._hydrate_key(key)
        return None

    def _hydrate_key(self, key: Dict[str, Any]) -> Dict[str, Any]:
        """Return a copy of the key dict with api_key hydrated from Keychain."""
        out = dict(key)
        api_key = out.get("api_key", "")
        if api_key == _KEYCHAIN_SENTINEL:
            real = _retrieve_from_keychain(out["id"])
            out["api_key"] = real or ""
        return out

    def mark_suspended(self, key_id: str, reason: str = "unknown") -> bool:
        self.reload()
        for key in self.keys:
            if key["id"] == key_id:
                key["suspended"] = True
                key["suspended_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                key["suspended_reason"] = reason
                # V19.11: Clear lease fields — a suspended key can never be
                # "actively leased". Before this fix, get_stats() excluded
                # suspended keys from the leased count (because `not suspended`
                # in the AND chain), so the stats were correct. BUT the raw JSON
                # still had `leased_until` etc. set, which:
                #   1. Confused debugging (looked like the key was still leased)
                #   2. Could cause issues if unsuspend_key() (V19.9) was called
                #      — the stale lease fields would make it look actively leased
                # Setting them to None keeps the JSON state consistent.
                key["leased_until"] = None
                key["leased_to"] = None
                key["lease_id"] = None
                key["leased_at"] = None
                self.save()
                logger.info(f"Key suspended ({reason}): {key_id[:8]}...")
                return True
        return False

    def unsuspend_key(self, key_id: str, reason: str = "test_verified_alive") -> bool:
        """
        Re-aktiviert einen suspended Key (false-positive recovery).

        Wird von tools/test_keys.py genutzt um Keys die als suspended markiert wurden
        (z.B. transient 412) aber tatsächlich noch alive sind, zurück in den Pool
        zu holen.
        """
        self.reload()
        for key in self.keys:
            if key["id"] == key_id:
                key["suspended"] = False
                key["suspended_at"] = None
                key["suspended_reason"] = None
                key["reactivated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                key["reactivation_reason"] = reason
                self.save()
                logger.info(f"Key reactivated ({reason}): {key_id[:8]}...")
                return True
        return False

    def mark_used(self, key_id: str) -> bool:
        """
        Markiert einen API-Key als verwendet (manuell, z.B. nach Rotation).

        Args:
            key_id: ID des Keys

        Returns:
            True wenn Key gefunden und markiert
        """
        self.reload()
        for key in self.keys:
            if key["id"] == key_id:
                key["used"] = True
                key["used_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
                self.save()
                logger.info(f"API-Key markiert als verwendet: {key_id[:8]}...")
                return True
        return False

