# otp_cdp.py

OTP extraction via CDP Accessibility Tree.

## What it does
Provides `read_otp_cdp_axtree()` which uses Chromium's CDP `Accessibility.getFullAXTree` to scan for OTP emails across OOPIFs and Shadow DOM. This avoids Playwright frame complexity by using the browser's internal accessibility tree.

## Dependencies
- `playwright.async_api.Page` — for CDP session creation
- `agent_toolbox.core.gmx_service.GmxService` — mixed into, uses `self.inbox_tab` fallback

## Usage
```python
from agent_toolbox.core.gmx_service import GmxService
gmx = GmxService()
result = await gmx.read_otp_cdp_axtree(page=my_page, sender_keyword="fireworks")
```

## Key config values
- `timeout=180` — default polling timeout in seconds
- `sender_keyword="fireworks"` — email sender to search for

## Caveats
- Requires an active CDP session on the page context
- Falls back to `self.inbox_tab` if no `page` argument provided
