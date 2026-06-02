"""SQLite-backed Vercel API key pool with LRU and cooldown rotation.

Docs: pool_manager.doc.md
"""
import sqlite3
from datetime import datetime, timedelta

DB_PATH = "vercel_pool.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")  # WAL für bessere Concurrency
    conn.execute("PRAGMA busy_timeout=5000")  # 5s Wartezeit bei Lock
    conn.execute("""
    CREATE TABLE IF NOT EXISTS api_keys (
        key TEXT PRIMARY KEY,
        status TEXT DEFAULT 'active', -- 'active' oder 'cooldown'
        cooldown_until TEXT, -- ISO Format Datum
        cooldown_reason TEXT, -- 'credits_exhausted' (31d) oder 'rate_limited' (kurz)
        last_used TEXT
    )
    """)
    # Migration: Spalte nachrüsten, falls DB aus älterer Version stammt
    cols = [r[1] for r in conn.execute("PRAGMA table_info(api_keys)").fetchall()]
    if "cooldown_reason" not in cols:
        conn.execute("ALTER TABLE api_keys ADD COLUMN cooldown_reason TEXT")
    conn.commit()
    conn.close()

def get_active_key():
    """ATOMISCH: Holt UND markiert den am längsten nicht genutzten aktiven Key in EINEM Query.
    Verhindert Race Conditions bei parallelen Requests (mehrere Requests = gleicher Key).
    Nutzt UPDATE ... RETURNING (SQLite 3.35+) — garantiert dass JEDER Request einen
    verschiedenen Key bekommt.
    """
    conn = sqlite3.connect(DB_PATH, timeout=10)
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE api_keys
    SET last_used = ?
    WHERE rowid = (
        SELECT rowid FROM api_keys
        WHERE status = 'active'
        ORDER BY last_used ASC
        LIMIT 1
    )
    RETURNING key
    """, (datetime.now().isoformat(),))
    result = cursor.fetchone()
    conn.commit()
    conn.close()
    return result[0] if result else None

def mark_key_long_cooldown(key: str):
    """
    LANGER Cooldown (31 Tage): Wird genutzt, wenn die CREDITS AUFGEBRAUCHT sind
    (Billing/Quota/Spending-Limit). Der Key wird quasi 'archiviert' und kommt
    nach 31 Tagen automatisch zurück (z.B. neuer Abrechnungszeitraum).
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cooldown_date = (datetime.now() + timedelta(days=31)).isoformat()
    cursor.execute("""
        UPDATE api_keys 
        SET status = 'cooldown', cooldown_until = ?, cooldown_reason = 'credits_exhausted'
        WHERE key = ?
    """, (cooldown_date, key))
    conn.commit()
    conn.close()
    print(f"🔴 Key {key[:8]}... CREDITS AUFGEBRAUCHT → 31-Tage-Archiv bis {cooldown_date[:10]}")


def mark_key_short_cooldown(key: str, seconds: int = 5):
    """
    KURZER Cooldown (Standard 5s): Wird genutzt bei transientem RATE-LIMIT
    (Free-Tier 'rate-limited', 'retrying in Xs'). Credits sind NICHT aufgebraucht,
    man müsste nur warten. Wir warten NICHT, sondern swappen sofort den Key und
    holen diesen Key nach 5s wieder zurück in den aktiven Pool (Vercel resettet
    nach ~30s, 5s Puffer reicht).
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cooldown_date = (datetime.now() + timedelta(seconds=seconds)).isoformat()
    cursor.execute("""
    UPDATE api_keys
    SET status = 'cooldown', cooldown_until = ?, cooldown_reason = 'rate_limited'
    WHERE key = ?
    """, (cooldown_date, key))
    conn.commit()
    conn.close()
    print(f"🟡 Key {key[:8]}... RATE-LIMIT → {seconds}s Kurz-Pause bis {cooldown_date[11:19]}")

def recover_expired_keys():
    """Reaktiviert Keys, deren 31-Tage-Cooldown abgelaufen ist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        UPDATE api_keys 
        SET status = 'active', cooldown_until = NULL, cooldown_reason = NULL
        WHERE status = 'cooldown' AND cooldown_until <= ?
    """, (now,))
    recovered = cursor.rowcount
    conn.commit()
    conn.close()
    if recovered > 0:
        print(f"🟢 {recovered} Key(s) aus der Wartebank reaktiviert!")

def get_pool_status():
    """Gibt eine Übersicht über den aktuellen Pool-Status"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM api_keys WHERE status = 'active'")
    active = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM api_keys WHERE status = 'cooldown'")
    cooldown = cursor.fetchone()[0]
    # Aufschlüsselung nach Grund: kurz (rate_limited) vs. lang (credits_exhausted)
    cursor.execute("SELECT COUNT(*) FROM api_keys WHERE status = 'cooldown' AND cooldown_reason = 'rate_limited'")
    rate_limited = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM api_keys WHERE status = 'cooldown' AND cooldown_reason = 'credits_exhausted'")
    credits_exhausted = cursor.fetchone()[0]
    conn.close()
    return {
        "active": active,
        "cooldown": cooldown,
        "cooldown_rate_limited": rate_limited,      # kommen in Minuten zurück
        "cooldown_credits_exhausted": credits_exhausted,  # kommen nach 31 Tagen zurück
        "total": active + cooldown,
    }
