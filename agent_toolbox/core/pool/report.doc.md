# Pool Report Mixin

Atomic report-and-swap for dead/suspended keys.

## Purpose
When a proxy detects a dead key (401/403/429/412), report it to get a replacement atomically.

## Methods
- `report_key(api_key, key_id, reason, leased_to, ttl_seconds)` -- mark old key as used, lease new key

## Report Reasons
- `suspended` -- Fireworks blocked the account
- `rate_limited` -- temporary 429
- `unauthorized` -- 401/403
- `credits_exhausted` -- 402 (spending limit)

## Atomic Guarantee
Old key marked `used` + new key leased in single `_load()` -> modify -> `save()` cycle.
Prevents double-lease race in multi-proxy setups.

## Caveats
- If no replacement key available, returns `{"swapped": false}`
- Caller must handle empty `new_key` response
