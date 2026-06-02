# gmx_service.py

Docs: gmx_service.doc.md

## What
Streamlined GMX Service for SINator v0+Vercel. Handles alias rotation and OTP extraction specifically adapted for Vercel 6-digit numeric OTP codes.

## Dependencies
- `playwright.async_api`
- CDP (Chrome DevTools Protocol) for native mouse events in GMX Wicket UI

## Key Methods
- `rotate_alias()` — delete old alias + create new one via 3c.gmx.net top-frame navigation
- `read_otp()` — read Vercel OTP (6-digit numeric) from GMX inbox via Shadow-DOM traversal or CDP AXTree
- `_delete_alias()` — CDP-based hover + click for Wicket compatibility

## Adaptations from sinator-fireworksai
- OTP patterns changed from Fireworks confirm URLs to Vercel 6-digit numeric codes
- `pattern_subject = re.compile(r"(\d{6}) is your Vercel sign up code", re.IGNORECASE)`
- `sender_keyword` default changed from `"fireworks"` to `"vercel"`

## Session Requirements
- Chrome must be running with `--remote-debugging-port=9222`
- GMX session must be active (logged in) in Profile 73
- `GMX_PASSWORD` env var needed for login fallback

## Known Issues
- GMX FreeMail allows only ONE alias at a time
- Cookie consent / session restore interstitial may require reload
