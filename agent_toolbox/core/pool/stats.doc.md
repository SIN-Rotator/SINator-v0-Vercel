# Pool Stats Mixin

Pool statistics and credit tracking.

## Purpose
Compute aggregate counts (total, available, used, suspended, assigned, shared) and track per-key credit usage.

## Methods
- `get_stats()` -- full stats dict with per-key status breakdown
- `update_credits(key_id, credits_remaining)` -- update billing tracker data

## Stats Formula
```
available = total - used - suspended - assigned
```
Note: `leased` keys are still counted in `available` (leased_until expiry returns them).

## Caveats
- Stats are computed on-demand from `self.keys` list -- may be stale if another process modified JSON
- Credit tracking is optional (Fireworks UI scraping)
