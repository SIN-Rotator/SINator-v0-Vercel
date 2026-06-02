# SINator v0+Vercel — API Key Rotator

Automated Vercel/v0.dev account creation via referral link, GMX alias OTP,
SMSPool UK phone verification, and API key extraction.

## Architecture

- `agent_toolbox/core/gmx_service.py` — GMX alias rotation + OTP reading (Playwright-native, proven from sinator-fireworksai)
- `agent_toolbox/core/vercel_service.py` — Vercel signup flow (sin-browser-tools)
- `agent_toolbox/core/smspool_service.py` — SMSPool UK number + OTP polling
- `tools/rotate.py` — Full E2E rotation orchestrator

## Quick Start

```bash
# 1. Set credentials
export GMX_PASSWORD="..."
export SMSPOOL_API_KEY="..."  # optional, for phone verification

# 2. Ensure Chrome is running on CDP port 9222 with Profile 73
#    (see AGENTS.md for exact start command)

# 3. Run rotation
python tools/rotate.py
```

## Flow

1. Connect to Chrome via CDP (Port 9222)
2. Rotate GMX alias (delete old → create new)
3. Open `https://v0.app/ref/6IMSRI` in new tab
4. Fill alias email → "Continue with Email"
5. Read 6-digit Vercel OTP from GMX inbox
6. Fill OTP → set password
7. (Optional) SMSPool UK phone verification
8. Navigate to API tokens → generate → extract key
9. Save to `data/vercel-pool.json`

## Pool Format

```json
[
  {
    "id": "uuid",
    "email": "swift-lynx-612@gmx.de",
    "api_key": "vercel_token_...",
    "password": "...",
    "created_at": "2026-06-02T...",
    "status": "active"
  }
]
```
