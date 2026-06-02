# rotate.py

Docs: rotate.doc.md

## What
End-to-end rotation orchestrator for SINator v0+Vercel. Connects to Chrome, rotates GMX alias, signs up for Vercel, extracts API token, and saves to pool.

## Usage
```bash
export GMX_PASSWORD="..."
export SMSPOOL_API_KEY="..."  # optional
python tools/rotate.py
```

## Flow
1. Connect Chrome via CDP (port 9222)
2. Initialize GMX service + multi-tab architecture
3. Rotate alias (`rotate_alias`)
4. Open Vercel referral in new tab
5. Fill email + submit (triggers Vercel OTP email)
6. Read 6-digit OTP from GMX inbox (`read_otp`)
7. Complete signup: OTP → password → phone (SMSPool) → API token
8. Save entry to `data/vercel-pool.json`

## Pool Format
`data/vercel-pool.json` — array of objects with:
- `id`, `email`, `api_key`, `password`, `created_at`, `status`

## Dependencies
- `gmx_service.py` — alias rotation + OTP
- `vercel_service.py` — signup flow
- `smspool_service.py` — phone verification
- `sin_browser_tools` — browser automation

## Session Recovery
If rotation fails mid-flow, the GMX alias and partial data are still saved to the pool with `status: "partial"` for debugging.

## Immortal Commit Protocol
All commits must follow conventional commit format:
- `feat(rotate): ...`
- `fix(gmx): ...`
- `docs(vercel): ...`
