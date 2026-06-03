# Vercel API Key

Extracts Fireworks API key (`fw_...`) from the web UI after successful login.

## Purpose
Navigates to `/settings/users/api-keys`, creates new key, polls page text for `fw_` pattern.

## Dependencies
- Used by: `rotate.py`, `fireworks_service.py` (Facade)
- Uses: `sin_browser_tools` (browser_navigate, browser_click_by_text, browser_get_text)

## Flow
1. Navigate to API Keys page
2. Handle login redirect (re-login if session expired)
3. Click "Create API Key" -> "API Key" menuitem
4. Fill key name, click Generate
5. Poll page text for `fw_[a-zA-Z0-9]{20,}` regex (15 attempts x 1s)

## Security
- Returns raw `fw_...` key to caller -- caller must store in pool immediately
- No key material logged

## Caveats
- Missing Name error -> close dialog, retry with incremented suffix
- Dialog may not appear -> retry navigation up to 3 times
