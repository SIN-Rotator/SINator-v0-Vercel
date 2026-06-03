# Pool Manager (Facade)

Composed pool manager combining all mixins.

## Purpose
`PoolManager` class inherits from all 8 mixins via multiple inheritance.
Provides backward-compatible API after the monolith split (v0.29).

## Mixins
- `PoolManagerStateMixin` -- loading, persistence, keychain recovery
- `PoolManagerCrudMixin` -- add, suspend, delete keys
- `PoolManagerStatsMixin` -- statistics, credit tracking
- `PoolManagerLeaseMixin` -- legacy TTL leasing
- `PoolManagerAgentMixin` -- V19.14 soft-ownership
- `PoolManagerLeaseReturnMixin` -- return leased keys, expire
- `PoolManagerReportMixin` -- atomic report-and-swap
- `PoolManagerSseMixin` -- SSE event streaming

## Singleton
```python
from agent_toolbox.core.pool_manager import get_pool_manager
mgr = get_pool_manager()  # singleton instance
```

## Caveats
- MRO (Method Resolution Order) follows Python C3 linearization
- All mixins call `self.save()` -- potential write amplification
