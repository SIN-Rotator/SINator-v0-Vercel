"""Pool Agent mixin.

Docs: agent.doc.md
"""
import json
import re
import time
import uuid
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class PoolManagerAgentMixin:
    """Auto-generated mixin from pool_manager.py split."""

    def get_key_for_agent(self, agent_id: str, preferred_key_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """V19.14: Soft-ownership key assignment. Never blocks.

        Priority:
          1. preferred_key_id (sticky — agent requests its known key)
          2. assigned_to == agent_id (agent's own key)
          3. assigned_to is None (unassigned → assign now)
          4. Least-shared key (min active_consumers) as fallback sharing

        Returns None only if ALL keys are suspended/used.
        """
        self.reload()
        now = time.time()
        active = [k for k in self.keys if not k.get("used") and not k.get("suspended")]
        if not active:
            return None

        if preferred_key_id:
            for k in active:
                if k["id"] == preferred_key_id:
                    return self._register_consumer(k, agent_id)

        for k in active:
            if k.get("assigned_to") == agent_id:
                return self._register_consumer(k, agent_id)

        for k in active:
            if not k.get("assigned_to"):
                k["assigned_to"] = agent_id
                self.save()
                return self._register_consumer(k, agent_id)

        best = min(active, key=lambda k: len(k.get("active_consumers", [])))
        best.setdefault("shared_count", 0)
        best["shared_count"] += 1
        logger.info(f"V19.14: Key {best['id'][:8]} SHARED ({agent_id} joins {len(best.get('active_consumers',[]))} existing consumers)")
        return self._register_consumer(best, agent_id)

    def _register_consumer(self, key: Dict[str, Any], agent_id: str) -> Dict[str, Any]:
        """V19.14: Register an agent as active consumer of a key, hydrate, save."""
        consumers = key.setdefault("active_consumers", [])
        if agent_id not in consumers:
            consumers.append(agent_id)
        key["last_heartbeat"] = time.time()
        self.save()
        hydrated = self._hydrate_key(key)
        return {
            "api_key": hydrated["api_key"],
            "key_id": key["id"],
            "alias_email": key.get("alias_email", ""),
            "key_name": key.get("key_name", ""),
            "shared": len(consumers) > 1,
            "active_consumers": consumers.copy(),
            "assigned_to": key.get("assigned_to"),
            "shared_count": key.get("shared_count", 0),
        }

    def release_key_for_agent(self, agent_id: str, key_id: str) -> bool:
        """V19.14: Agent releases a key. Removes from active_consumers only."""
        self.reload()
        for k in self.keys:
            if k["id"] == key_id:
                consumers = k.get("active_consumers", [])
                if agent_id in consumers:
                    consumers.remove(agent_id)
                k["active_consumers"] = consumers
                self.save()
                logger.info(f"V19.14: Agent {agent_id} released key {key_id[:8]} (remaining consumers: {len(consumers)})")
                return True
        return False

    def cleanup_stale_consumers(self, timeout_seconds: int = 300) -> int:
        """V19.14: Remove consumers that haven't sent a heartbeat in timeout_seconds.

        Called periodically by the backend lifespan task.

        Returns: number of consumers cleaned up.
        """
        self.reload()
        now = time.time()
        cleaned = 0
        for k in self.keys:
            last_hb = k.get("last_heartbeat", 0)
            consumers = k.get("active_consumers", [])
            if consumers and now - last_hb > timeout_seconds:
                k["active_consumers"] = []
                cleaned += len(consumers)
        if cleaned > 0:
            self.save()
            logger.info(f"V19.14: Cleaned {cleaned} stale consumers (timeout={timeout_seconds}s)")
        return cleaned

