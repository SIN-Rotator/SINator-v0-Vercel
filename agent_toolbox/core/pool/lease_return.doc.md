# Pool Lease Return Mixin

Return leased keys and expire stale leases.

## Purpose
Make keys available again after consumer is done or lease expires.

## Methods
- `return_key(key_id, lease_id)` -- validate lease_id, clear lease fields
- `expire_leases()` -- batch-clear all expired `leased_until` entries
- `get_leased_keys()` -- list all currently leased keys

## Return Protocol
1. Validate `lease_id` matches (prevents accidental returns)
2. Clear `leased_until`, `leased_to`, `lease_id`, `leased_at`
3. Save pool

## Caveats
- V19.10: background lease cleanup runs every 60s via FastAPI lifespan
- `return_key` without `lease_id` skips validation (backward compat)
