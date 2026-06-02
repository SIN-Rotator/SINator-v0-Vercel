# add_keys.py — Key Import CLI

## Was diese Datei tut

CLI-Tool zum Importieren von Vercel API Keys in den SQLite Pool. Unterstützt Bulk-Import aus Datei (ein Key pro Zeile) und Einzel-Key via `--key`. Idempotent — bereits vorhandene Keys werden übersprungen.

## Dependency Map

| Importiert von | Was |
|---|---|
| `pool_manager.init_db()` | DB-Schema-Migration vor Insert |
| Python stdlib | `sqlite3`, `sys`, `datetime` |

## Usage

```bash
# Bulk-Import aus Datei (ein Key pro Zeile, # = Kommentar)
python add_keys.py keys.txt

# Einzelner Key
python add_keys.py --key vck_xxx...

# Status anzeigen
python add_keys.py --status
```

`keys.txt` Format:
```
vck_1abc...
vck_2def...
# Kommentar-Zeilen werden ignoriert
vck_3ghi...
```

## Design-Entscheidungen

### Idempotente Inserts
- `SELECT 1 FROM api_keys WHERE key = ?` vor INSERT
- Duplikate werden gezählt (`skipped`) und übersprungen, nicht überschrieben
- Sicher gegen Re-Runs

### `last_used` auf NOW beim Insert
- Damit LRU neu hinzugefügte Keys nicht sofort bevorzugt werden
- Reihenfolge bleibt stabil: neue Keys werden als letztes gepullt

### CLI-Args (sys.argv) statt argparse
- Bewusst minimal — 3 Modi (Datei, `--key`, `--status`)
- Argparse wäre Overkill für dieses simple Tool

## Footguns

- **Dateipfad relativ zu CWD:** `python add_keys.py ./keys.txt` — nicht im falschen Verzeichnis ausführen.
- **Keine Key-Format-Validierung:** Akzeptiert jeden String. Vercel Keys starten mit `vck_`, aber das Tool prüft das nicht.
- **Commit-Schutz:** `keys.txt` ist in `.gitignore` — niemals committen!
