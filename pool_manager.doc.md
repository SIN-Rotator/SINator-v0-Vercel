# pool_manager.py — SQLite Key Pool Storage

## Was diese Datei tut

Persistiert Vercel API Keys in SQLite mit LRU-Strategie und Zwei-Modus-Cooldown (31 Tage für erschöpfte Credits, 2 Min für transientes Rate-Limit). Wird von `main.py` (Proxy) und `add_keys.py` (CLI) genutzt.

## Dependency Map

| Importiert von | Was |
|---|---|
| `main.py` | Key-Lookup (LRU), Cooldown-Markierung, Status |
| `add_keys.py` | `init_db()` für DB-Schema-Migration |

External: nur Python stdlib (`sqlite3`, `datetime`).

## DB-Schema (`vercel_pool.db`)

```sql
CREATE TABLE api_keys (
    key TEXT PRIMARY KEY,
    status TEXT DEFAULT 'active',         -- 'active' oder 'cooldown'
    cooldown_until TEXT,                   -- ISO Datum
    cooldown_reason TEXT,                  -- 'credits_exhausted' (31d) oder 'rate_limited' (kurz)
    last_used TEXT
);
```

## Wichtige Funktionen

| Funktion | Zweck |
|---|---|
| `init_db()` | Erstellt Schema + Migrationen (idempotent) |
| `get_active_key()` | LRU-Lookup: oldest `last_used` zuerst |
| `mark_key_long_cooldown(key)` | 31-Tage-Archiv (Credits exhausted) |
| `mark_key_short_cooldown(key, minutes)` | Kurze Pause (Rate-Limit) |
| `recover_expired_keys()` | Reaktiviert Keys mit `cooldown_until <= now` |
| `get_pool_status()` | Stats: active, cooldown (by reason) |

## Design-Entscheidungen

### LRU statt Round-Robin
- Keys die lange nicht genutzt wurden bekommen mehr Traffic
- Vermeidet "Hot Keys" die schneller in Cooldown gehen
- Realisiert via `ORDER BY last_used ASC LIMIT 1`

### Kein DELETE — nur Status-Wechsel
- Keys werden NIE gelöscht, nur zwischen `active` ↔ `cooldown` rotiert
- 31-Tage-Wartebank ermöglicht automatische Reaktivierung nach Credit-Reset

### `cooldown_until` als ISO String
- `datetime.now().isoformat()` für Vergleiche
- SQLite hat kein natives DateTime — String-Sortierung funktioniert für ISO-Format

## Footguns

- **DB-Pfad:** `vercel_pool.db` ist relativ zum CWD. Bei LaunchAgent oder systemd immer absoluten Pfad setzen.
- **Concurrent writes:** Kein Locking. Bei hoher Concurrency könnte LRU doppelt denselben Key liefern. Für unsere Last (LLM-Traffic) ausreichend.
- **`recover_expired_keys()` muss bei jedem Request aufgerufen werden** — sonst bleiben reaktivierte Keys "inaktiv" bis manuell getriggert.
