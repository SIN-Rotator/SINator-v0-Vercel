import sqlite3
from datetime import datetime, timedelta

DB_PATH = "vercel_pool.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            key TEXT PRIMARY KEY,
            status TEXT DEFAULT 'active', -- 'active' oder 'cooldown'
            cooldown_until TEXT,          -- ISO Format Datum
            last_used TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_active_key():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Hole den am längsten nicht genutzten aktiven Key (Least Recently Used)
    cursor.execute("""
        SELECT key FROM api_keys 
        WHERE status = 'active' 
        ORDER BY last_used ASC 
        LIMIT 1
    """)
    result = cursor.fetchone()
    
    if result:
        # Update last_used timestamp
        cursor.execute("""
            UPDATE api_keys 
            SET last_used = ? 
            WHERE key = ?
        """, (datetime.now().isoformat(), result[0]))
        conn.commit()
    
    conn.close()
    return result[0] if result else None

def mark_key_cooldown(key: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Exakt 31 Tage Wartebank
    cooldown_date = (datetime.now() + timedelta(days=31)).isoformat()
    cursor.execute("""
        UPDATE api_keys 
        SET status = 'cooldown', cooldown_until = ? 
        WHERE key = ?
    """, (cooldown_date, key))
    conn.commit()
    conn.close()
    print(f"🔴 Key {key[:8]}... auf 31-Tage-Cooldown gesetzt bis {cooldown_date[:10]}")

def recover_expired_keys():
    """Reaktiviert Keys, deren 31-Tage-Cooldown abgelaufen ist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        UPDATE api_keys 
        SET status = 'active', cooldown_until = NULL 
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
    conn.close()
    return {"active": active, "cooldown": cooldown, "total": active + cooldown}
