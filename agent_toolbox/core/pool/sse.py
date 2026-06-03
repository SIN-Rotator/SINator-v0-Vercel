"""Pool Sse mixin.

Docs: sse.doc.md
"""
import json
import re
import time
import uuid
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class PoolManagerSseMixin:
    """Auto-generated mixin from pool_manager.py split."""

def _emit_event(event_type: str, data: Dict[str, Any]):
    """
    Emits an SSE event to all registered listeners.
    Thread-safe — safe to call from any PoolManager method.
    """
    import asyncio as _asyncio
    payload = {"event": event_type, "data": data}
    dead = []
    for q in _SSE_LISTENERS:
        try:
            q.put_nowait(payload)
        except Exception:
            dead.append(q)
    for q in dead:
        _SSE_LISTENERS.remove(q)


def register_sse_listener() -> "asyncio.Queue":
    """
    Register a new SSE listener queue. Returns an asyncio.Queue
    that will receive event payloads.
    """
    import asyncio as _asyncio
    q = _asyncio.Queue()
    _SSE_LISTENERS.append(q)
    return q


def unregister_sse_listener(q: "asyncio.Queue"):
    """Remove an SSE listener queue."""
    if q in _SSE_LISTENERS:
        _SSE_LISTENERS.remove(q)


_pool_manager: Optional[PoolManager] = None


