# Pool State Mixin

Pool loading, persistence, and keychain auto-recovery.

## Purpose
Manages the `data/fireworksai-pool.json` file format (list of key dicts).
Auto-recovers from macOS Keychain if JSON is deleted (V19.8).

## Methods
- `_load()` -- load from JSON or auto-recover from Keychain
- `reload()` -- re-read JSON from disk
- `save()` -- atomic write to JSON (overwrite in-place)
- `_try_recover_from_keychain()` -- reconstruct pool from `security dump-keychain`
- `_hydrate_key()` -- resolve `STORED_IN_KEYCHAIN` sentinel to real API key

## Config
- `DEFAULT_POOL_PATH`: `data/fireworksai-pool.json`
- UUID regex validation for key IDs

## Caveats
- JSON write is NOT atomic (no tmp+rename) -- crash during write corrupts pool
- No file locking -- concurrent writes from multiple processes may lose data
