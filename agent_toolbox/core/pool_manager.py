"""API Key pool manager — add, lease, return, mark, report, stats, SSE events.

Docs: pool_manager.doc.md
"""
import json
import re
import time
import uuid
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from agent_toolbox.core.keychain_store import (
    store_key as _store_to_keychain,
    retrieve_key as _retrieve_from_keychain,
    delete_key as _delete_from_keychain,
    SENTINEL as _KEYCHAIN_SENTINEL,
)

logger = logging.getLogger(__name__)

UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.I,
)

DEFAULT_POOL_PATH = Path(__file__).parent.parent.parent / "data" / "fireworksai-pool.json"


class PoolManager:
    """
    Verwaltet den API-Key-Pool: Hinzufügen, Abrufen, Markieren, Statistiken.
    """

    def __init__(self, pool_path: Optional[Path] = None):
        """
        Initialisiert den Pool-Manager.

        Args:
            pool_path: Pfad zur Pool-JSON-Datei
        """
        self.pool_path = pool_path or DEFAULT_POOL_PATH
        self.pool_path.parent.mkdir(parents=True, exist_ok=True)
        self.keys: List[Dict[str, Any]] = []
        self._load()


# Mixins (split from monolith pool_manager.py)
from agent_toolbox.core.pool.state import PoolManagerStateMixin
from agent_toolbox.core.pool.crud import PoolManagerCrudMixin
from agent_toolbox.core.pool.stats import PoolManagerStatsMixin
from agent_toolbox.core.pool.lease import PoolManagerLeaseMixin
from agent_toolbox.core.pool.agent import PoolManagerAgentMixin
from agent_toolbox.core.pool.lease_return import PoolManagerReturnMixin
from agent_toolbox.core.pool.report import PoolManagerReportMixin
from agent_toolbox.core.pool.sse import PoolManagerSseMixin


class PoolManager(
    PoolManagerStateMixin,
    PoolManagerCrudMixin,
    PoolManagerStatsMixin,
    PoolManagerLeaseMixin,
    PoolManagerAgentMixin,
    PoolManagerReturnMixin,
    PoolManagerReportMixin,
    PoolManagerSseMixin,
):
    """API Key pool manager — composed from mixins.

    All methods inherited from mixins:
      - State: _load, reload, save, _try_recover_from_keychain, _hydrate_key
      - CRUD: add_key, mark_suspended, unsuspend_key, mark_used, update_credits, delete_key
      - Stats: get_stats
      - Lease: lease_key, get_available_key
      - Agent: get_key_for_agent, release_key_for_agent, cleanup_stale_consumers
      - Return: return_key, expire_leases, get_leased_keys
      - Report: report_key
      - SSE: register_sse_listener, unregister_sse_listener
    """

    pass

# Global singleton (backward compat)
_pool_manager: Optional[PoolManager] = None

def get_pool_manager(pool_path: Optional[Path] = None) -> PoolManager:
    """Return the singleton PoolManager instance."""
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = PoolManager(pool_path=pool_path)
    return _pool_manager
