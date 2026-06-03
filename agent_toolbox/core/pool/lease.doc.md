# Pool Lease Mixin

Legacy TTL-based key leasing (superseded by Soft-Ownership in V19.14).

## Purpose
Reserve a key for a specific consumer for a time-limited period (default 1800s).

## Methods
- `lease_key(ttl_seconds, leased_to)` -- atomically reserve available key
- `get_available_key()` -- return first non-used, non-suspended, non-leased key

## Lease Fields
- `leased_until`: float (timestamp)
- `leased_to`: str (consumer identifier)
- `lease_id`: str (UUID for validation)

## Caveats
- Legacy leases do NOT prevent multiple proxies from using the same key
- V19.14 Soft-Ownership (`agent-key` endpoint) preferred for multi-agent setups
- `expire_leases()` must be called periodically to free expired leases
