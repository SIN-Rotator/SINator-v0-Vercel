# Pool CRUD Mixin

Create, update, delete operations for pool keys.

## Purpose
Manage individual key entries: add, suspend, unsuspend, mark used, delete.

## Methods
- `add_key(api_key, alias_email, key_name)` -- append new key with UUID
- `mark_suspended(key_id, reason)` -- suspend + clear lease fields
- `unsuspend_key(key_id)` -- reverse suspension (e.g., after health check passes)
- `mark_used(key_id)` -- permanently mark as consumed
- `delete_key(key_id)` -- remove from pool + Keychain

## Security
- API keys stored in macOS Keychain (not pool JSON) after V19.8 migration
- Pool JSON contains `STORED_IN_KEYCHAIN` sentinel + metadata only

## Caveats
- `delete_key` removes from Keychain -- irrecoverable
- `mark_used` is permanent -- no undo
