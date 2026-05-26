#!/usr/bin/env python3
"""Batch generate N keys via rotation API, sequential (safe)."""
import asyncio, json, time, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TARGET = 100
POOL_FILE = Path(__file__).resolve().parent.parent / "data" / "fireworksai-pool.json"
LOG_FILE = Path(__file__).resolve().parent.parent / "data" / "batch-rotate.log"

log_lines = []

def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    log_lines.append(line)
    print(line, flush=True)
    LOG_FILE.write_text("\n".join(log_lines))

async def count_available():
    import http.client
    conn = http.client.HTTPConnection("localhost", 8000, timeout=5)
    conn.request("GET", "/api/v1/pool/stats")
    resp = conn.getresponse()
    data = json.loads(resp.read())
    conn.close()
    return data.get("available", 0), data.get("total", 0)

async def rotate_one():
    import http.client
    conn = http.client.HTTPConnection("localhost", 8000, timeout=600)
    body = json.dumps({"new_alias_name": None, "save_to_pool": True})
    conn.request("POST", "/api/v1/rotation/full", body=body.encode(), headers={"Content-Type": "application/json"})
    resp = conn.getresponse()
    data = json.loads(resp.read())
    conn.close()
    return data

async def main():
    avail, total_start = await count_available()
    log(f"Start: {avail} available / {total_start} total — Ziel: {TARGET} neue Keys")

    created = 0
    successes = 0
    failures = 0
    t0 = time.time()

    while successes < TARGET:
        log(f"\n--- Rotation #{successes + 1} (attempt) ---")
        try:
            result = await rotate_one()
            status = result.get("status", "error")
            api_key = result.get("api_key", "")
            alias = result.get("gmx_alias", "")
            elapsed = result.get("execution_time", "?")

            if status == "success" and api_key:
                successes += 1
                log(f"✅ #{successes}/{TARGET} — {alias} → {api_key} ({elapsed}s)")
            else:
                failures += 1
                failed_steps = result.get("steps_failed", [])
                log(f"❌ #{successes + 1} FAILED: {status} | steps_failed={failed_steps} | err={result.get('error','')}")
                if failures >= 10:
                    log("⚠️  10 consecutive failures — aborting")
                    break
                log("🕐  waiting 30s before retry...")
                await asyncio.sleep(30)
                continue
        except Exception as e:
            failures += 1
            log(f"💥 Exception: {e}")
            if failures >= 10:
                log("⚠️  10 consecutive failures — aborting")
                break
            await asyncio.sleep(30)
            continue

        failures = 0  # reset after success
        if successes % 5 == 0:
            avail, total = await count_available()
            log(f"📊 Checkpoint: {avail} available / {total} total")

    avail, total_end = await count_available()
    t = time.time() - t0
    log(f"\n{'='*50}")
    log(f"FERTIG: {successes} keys in {t/60:.1f}min ({t/successes:.0f}s avg)")
    log(f"Pool: {avail} available / {total_end} total")

if __name__ == "__main__":
    asyncio.run(main())
