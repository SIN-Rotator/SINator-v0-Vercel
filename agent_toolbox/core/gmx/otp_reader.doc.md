# otp_reader.py

OTP extraction via CDP iframe navigation.

## What it does
Provides `read_otp()` which navigates GMX mail via raw CDP websocket, enters the mail iframe, and scans for OTP/confirm URLs using Shadow-DOM traversal and accessibility tree clicking.

## Dependencies
- `agent_toolbox.core.cdp_client.CDPClient` — raw CDP websocket client
- `agent_toolbox.core.gmx_service.GmxService` — mixed into, uses `self._otp_connect()`

## Usage
```python
from agent_toolbox.core.gmx_service import GmxService
gmx = GmxService()
result = await gmx.read_otp(sender_filter="fireworks", cdp_port=9222)
```

## Key config values
- `max_retries=12` — number of polling attempts
- `retry_delay=5` — seconds between retries
- `cdp_port` — defaults to `$CDP_PORT` env var or 9230

## Caveats
- Depends on `_otp_connect()` being available on the mixed-in class
- Fragile to GMX DOM changes in the mail iframe
