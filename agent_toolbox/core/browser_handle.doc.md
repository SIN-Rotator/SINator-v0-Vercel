# Browser Handle

Duck-type wrapper providing SIN-Browser-Tools compatibility for raw Playwright instances.

## Purpose
Playwright-native browser automation without BrowserManager (which hardcodes `--start-maximized`, detectable by anti-bot systems).

## Dependencies
- Used by: `browser_launch.py`, `fireworks_service.py` (Facade)
- Uses: `playwright.async_api`, `asyncio`

## Config
- Window size: 1200x800 (NOT maximized)
- Stealth patches: webdriver undefined, plugins array, German locale

## Usage
```python
from agent_toolbox.core.browser_handle import _BrowserHandle
handle = _BrowserHandle(page, context, browser, pw)
```

## Caveats
- `_setup_dialog_handler()` and `get_next_dialog()` are no-ops (dialogs not handled in Bot Chrome)
- `cleanup()` is idempotent -- safe to call multiple times
