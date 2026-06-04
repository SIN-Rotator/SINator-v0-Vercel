# otp_playwright.py

OTP extraction via Playwright frame traversal.

## What it does
Provides `read_otp_via_playwright()` which uses Playwright to scan all frames (including OOPIFs) and Shadow DOM for OTP emails, then clicks the matching email and polls for the confirmation URL.

## Dependencies
- `playwright.async_api.Browser, Page` — for page/frame navigation
- `agent_toolbox.core.gmx_service.GmxService` — mixed into

## Usage
```python
from agent_toolbox.core.gmx_service import GmxService
gmx = GmxService()
result = await gmx.read_otp_via_playwright(browser=my_browser, sender_filter="fireworks")
```

## Key config values
- `max_retries=15` — number of polling attempts
- `retry_delay=6` — seconds between retries
- `existing_page` — reuse an existing logged-in page instead of creating a new one

## Caveats
- More reliable than CDP iframe approach but slower
- Reuses `existing_page` only on attempt 0; falls back to fresh pages on retries
