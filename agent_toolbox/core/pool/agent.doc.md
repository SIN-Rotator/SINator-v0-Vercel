# Pool Agent Mixin

V19.14 Soft-Ownership: multi-agent key distribution without blocking.

## Purpose
Each agent gets a sticky key assignment. If all keys assigned, least-shared key is shared. Never blocks, never waits.

## Fields
- `assigned_to`: str -- permanent owner agent_id
- `active_consumers`: list[str] -- agents currently using this key
- `shared_count`: int -- how many times this key was shared
- `last_heartbeat`: float -- for stale consumer cleanup (300s timeout)

## Methods
- `get_key_for_agent(agent_id, preferred_key_id)` -- 4-priority assignment:
  1. Agent's assigned key (sticky)
  2. Unassigned available key
  3. Least-shared assigned key
  4. Fallback (any available)
- `release_key_for_agent(agent_id, key_id)` -- remove from active_consumers
- `cleanup_stale_consumers(timeout)` -- heartbeat timeout cleanup

## Caveats
- `active_consumers` list is not atomic across processes -- JSON race condition
- Heartbeats must be sent every ~60s to keep consumer alive
