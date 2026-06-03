# Browser Launch

Launch ephemeral Chromium with anti-detection patches for Vercel/Fireworks automation.

## Purpose
Creates a fresh browser instance that bypasses Fireworks bot detection via stealth init scripts.

## Dependencies
- Used by: `rotate.py`, `fireworks_service.py` (Facade)
- Uses: `browser_handle.py`, `sin_browser_tools.core.manager`

## Config
- `--window-size=1200,800` (avoids maximized detection)
- `--disable-blink-features=AutomationControlled`
- German locale (`de-DE`) + timezone (`Europe/Berlin`)

## Usage
```python
result = await launch()  # Returns {"browser_manager": _BrowserHandle}
```

## Caveats
- Bot Chrome stays open until caller calls `cleanup_bot()` -- prevents session loss during signup
- `headless=False` required -- Fireworks blocks headless Chromium
