#!/usr/bin/env python3
"""CLI to import Vercel API keys into the pool SQLite database.

Docs: add_keys.doc.md
"""
import sqlite3
import sys
from datetime import datetime
from pool_manager import init_db

def add_keys_from_file(file_path: str):
    init_db()
    conn = sqlite3.connect("vercel_pool.db")
    cursor = conn.cursor()
    added = 0
    skipped = 0
    
    with open(file_path, 'r') as f:
        for line in f:
            key = line.strip()
            if key and not key.startswith("#"):
                cursor.execute("SELECT 1 FROM api_keys WHERE key = ?", (key,))
                if cursor.fetchone():
                    skipped += 1
                else:
                    cursor.execute(
                        "INSERT INTO api_keys (key, status, last_used) VALUES (?, 'active', ?)", 
                        (key, datetime.now().isoformat())
                    )
                    added += 1
    
    conn.commit()
    conn.close()
    print(f"✅ {added} neue Keys hinzugefügt, {skipped} bereits vorhanden.")

def add_single_key(key: str):
    init_db()
    conn = sqlite3.connect("vercel_pool.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM api_keys WHERE key = ?", (key,))
    
    if cursor.fetchone():
        print(f"⚠️ Key bereits im Pool vorhanden.")
    else:
        cursor.execute(
            "INSERT INTO api_keys (key, status, last_used) VALUES (?, 'active', ?)", 
            (key, datetime.now().isoformat())
        )
        conn.commit()
        print(f"✅ Key {key[:8]}... erfolgreich hinzugefügt.")
    
    conn.close()

def show_status():
    init_db()
    conn = sqlite3.connect("vercel_pool.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM api_keys WHERE status = 'active'")
    active = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM api_keys WHERE status = 'cooldown'")
    cooldown = cursor.fetchone()[0]
    
    print(f"\n📊 Pool Status:")
    print(f"   🟢 Aktive Keys: {active}")
    print(f"   🔴 Im Cooldown: {cooldown}")
    print(f"   📦 Gesamt: {active + cooldown}\n")
    
    if cooldown > 0:
        cursor.execute("SELECT key, cooldown_until FROM api_keys WHERE status = 'cooldown' ORDER BY cooldown_until ASC LIMIT 5")
        print("   Nächste Keys aus Cooldown:")
        for row in cursor.fetchall():
            print(f"      {row[0][:8]}... → {row[1][:10]}")
    
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python add_keys.py <keys.txt>     - Keys aus Datei importieren")
        print("  python add_keys.py --key <KEY>    - Einzelnen Key hinzufügen")
        print("  python add_keys.py --status       - Pool-Status anzeigen")
        sys.exit(1)
    
    if sys.argv[1] == "--status":
        show_status()
    elif sys.argv[1] == "--key" and len(sys.argv) > 2:
        add_single_key(sys.argv[2])
    else:
        add_keys_from_file(sys.argv[1])
