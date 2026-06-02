---
name: sinator-vercel-add-model
description: Add new Vercel AI Gateway models (e.g. alibaba/qwen3.7-plus) to the SINator-Vercel key pool AND opencode config. Covers API-key import, opencode provider entry, validation, and E2E test through the local pool.
license: MIT
---

# SINator-Vercel: Add New Model

> Use this skill whenever an agent needs to expose a new Vercel AI Gateway model (e.g. `alibaba/qwen3.7-plus`, `anthropic/claude-sonnet-5`, `google/gemini-4-ultra`) through the SINator-Vercel pool + opencode.

## Architecture Refresher

```
opencode (vercel-pool/minimax-m3)
   ↓ HTTP POST with dummy apiKey
SINator-Vercel Pool (localhost:8001, FastAPI)
   ↓ LRU lookup → active vck_xxx key
https://ai-gateway.vercel.sh/v1/chat/completions
   ↓ (61+ keys in rotation, 31d long / 2min short cooldown)
Upstream provider (e.g. alibaba, anthropic, google)
```

The pool is the **single source of truth** for keys. opencode never sees real `vck_*` keys — it always sends `"apiKey": "dummy"`.

---

## 4-Step Recipe

### Step 1: Add API Key(s) to Pool

```bash
cd /Users/jeremy/dev/SINator-Vercel
source .venv/bin/activate

# Single key
python add_keys.py --key "vck_xxx..."

# Bulk from file (one key per line, # = comment)
python add_keys.py keys_new.txt

# Verify
python add_keys.py --status
# → 🟢 Aktive Keys: N | 🔴 Im Cooldown: M | 📦 Gesamt: N+M
```

**Required format:** `vck_[a-zA-Z0-9]{40,}` (Vercel API key prefix).

**Footgun:** `keys_new.txt` is `.gitignore`'d — never commit it. Delete after import.

### Step 2: Verify Model Exists on Vercel

```bash
rtk curl -s https://ai-gateway.vercel.sh/v1/models \
  -H "Authorization: Bearer vck_xxx..." | python3 -c "
import json, sys
d = json.load(sys.stdin)
for m in d['data']:
    if 'qwen3.7' in m['id'].lower() or 'qwen' in m['id'].lower():
        print(f\"  {m['id']} — {m.get('name','')}\")"
```

Expected: `alibaba/qwen3.7-plus` (or similar) in the list. If not, the model is not yet available on the gateway.

### Step 3: Add Model to opencode Config

Edit `~/.config/opencode/opencode.json` under `provider.vercel-pool.models`:

```json
"vercel-pool": {
  "npm": "@ai-sdk/openai-compatible",
  "name": "Vercel Pool (SIN)",
  "options": {
    "baseURL": "http://localhost:8001/v1",
    "apiKey": "dummy"
  },
  "models": {
    "minimax-m3": { ... existing ... },
    "qwen3p7-plus": {
      "id": "alibaba/qwen3.7-plus",
      "name": "Qwen 3.7 Plus (SIN)",
      "limit": {
        "context": 131072,
        "output": 32768
      },
      "modalities": {
        "input": ["text", "image"],
        "output": ["text"]
      }
    }
  }
}
```

**Critical:**
- `id` MUST match the exact Vercel model ID (case-sensitive)
- Model name key (e.g. `qwen3p7-plus`) is your local alias — keep it short, no special chars
- `limit.context` / `limit.output` — get these from the Vercel `/v1/models` response
- `modalities` — only include modalities the model actually supports

### Step 4: Validate Config + E2E Test

```bash
# Config validation (MUST pass)
rtk opencode debug config 2>&1 | grep -E "(Error|invalid)" || echo "✅ Config valid"

# E2E test through pool
rtk curl -s -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "alibaba/qwen3.7-plus",
    "messages": [{"role": "user", "content": "Say hi"}],
    "max_tokens": 30
  }' | python3 -m json.tool

# Streaming test (SSE)
rtk curl -s -N -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "alibaba/qwen3.7-plus", "messages": [{"role": "user", "content": "Hi"}], "max_tokens": 20, "stream": true}' | head -5
```

Expected: JSON with `choices[0].message.content` populated (or `delta.content` for stream).

---

## Pool Status Check

```bash
rtk curl -s http://localhost:8001/pool/status | python3 -m json.tool
```

```json
{
  "active": 28,
  "cooldown": 37,
  "cooldown_rate_limited": 0,
  "cooldown_credits_exhausted": 37,
  "total": 65
}
```

- **`active < 5`:** pool is dying, add more keys ASAP
- **`cooldown_credits_exhausted > 0`:** these keys are gone for 31 days, plan rotation
- **`cooldown_rate_limited > 0`:** transient, will recover in 2 minutes

---

## Restarting the Pool (after config changes)

The pool itself does NOT need restart for model additions — only for `main.py` changes (TARGET_BASE_URL, streaming fixes).

```bash
# Check if pool is running
lsof -i :8001 -sTCP:LISTEN

# Restart if needed
kill $(lsof -i :8001 -sTCP:LISTEN -t) 2>/dev/null
cd /Users/jeremy/dev/SINator-Vercel && source .venv/bin/activate
nohup uvicorn main:app --host 0.0.0.0 --port 8001 > /tmp/sinator-vercel.log 2>&1 &
```

---

## Common Pitfalls

| Pitfall | Fix |
|---|---|
| `ConfigInvalidError: Unrecognized key: mcpServers` | Use `mcp` (lowercase), never `mcpServers` |
| `type: "stdio"` for MCP | Use `type: "local"` + `command: [array]` + `enabled: true` |
| Empty `choices[0].message.content` | Model has reasoning mode — content goes to `reasoning` field for short prompts. Test with longer prompt. |
| `DEPLOYMENT_NOT_FOUND` | Wrong TARGET_BASE_URL — must be `https://ai-gateway.vercel.sh` NOT `https://api.vercel.ai` |
| Binary gzip response | `aiter_raw()` instead of `aiter_bytes()` in `main.py:stream_body()` |
| `503 No active keys` | All keys in cooldown — wait 2 min (rate limit) or 31d (credits) |
| Model not in `/v1/models` | Model not yet on Vercel AI Gateway — check models.dev or wait |

---

## File Reference

| File | Purpose |
|---|---|
| `main.py` | FastAPI proxy + streaming + error classification |
| `pool_manager.py` | SQLite LRU + 2-tier cooldown |
| `add_keys.py` | CLI for key import (single + bulk) |
| `vercel_pool.db` | SQLite DB (auto-created, `.gitignore`'d) |
| `~/.config/opencode/opencode.json` | Provider config (under `provider.vercel-pool.models`) |
| `~/.config/opencode/auth.json` | Dummy key for `vercel-pool` provider |

---

## End-to-End Example: Adding `alibaba/qwen3.7-plus`

```bash
# 1. Add a fresh key
cd /Users/jeremy/dev/SINator-Vercel && source .venv/bin/activate
python add_keys.py --key "vck_NEW_KEY_HERE"

# 2. Verify model exists
rtk curl -s https://ai-gateway.vercel.sh/v1/models \
  -H "Authorization: Bearer vck_NEW_KEY_HERE" | \
  python3 -c "import json,sys;[print(m['id'],m.get('context_window'),m.get('max_tokens')) for m in json.load(sys.stdin)['data'] if 'qwen3.7' in m['id']]"
# → alibaba/qwen3.7-plus 131072 32768

# 3. Edit opencode.json — add under provider.vercel-pool.models:
#    "qwen3p7-plus": {
#      "id": "alibaba/qwen3.7-plus",
#      "name": "Qwen 3.7 Plus (SIN)",
#      "limit": { "context": 131072, "output": 32768 }
#    }

# 4. Validate
rtk opencode debug config 2>&1 | grep -i error || echo "✅"

# 5. E2E test
rtk curl -s -X POST http://localhost:8001/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"alibaba/qwen3.7-plus","messages":[{"role":"user","content":"Say hi"}],"max_tokens":20}' | python3 -m json.tool
# → Should return JSON with content populated
```

Now `qwen3p7-plus` (or whatever alias you picked) appears in `/models` in the opencode TUI.
