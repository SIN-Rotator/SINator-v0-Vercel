# Fireworks Service (Facade)

Re-exports all Vercel/Fireworks automation symbols for backward compatibility.

## Purpose
All `from agent_toolbox.core.fireworks_service import X` imports continue to work after the monolith split (v0.28).

## Modules Re-exported
- `browser_handle.py` -- `_BrowserHandle`
- `browser_launch.py` -- `launch()`, `cleanup_bot()`
- `vercel_account.py` -- `signup_fireworks/login_fireworks/verify_account` (legacy) + `signup_vercel/login_vercel/verify_vercel` (clear)
- `vercel_onboarding.py` -- `_playwright_onboarding` (legacy) + `vercel_onboarding` (clear)
- `vercel_apikey.py` -- `create_api_key` (legacy) + `create_vercel_api_key` (clear)

## Usage
```python
# Legacy (still works)
from agent_toolbox.core.fireworks_service import signup_fireworks, create_api_key

# Preferred (clear naming)
from agent_toolbox.core.fireworks_service import signup_vercel, create_vercel_api_key
```

## Migration Path
Future v1.0 may deprecate `*_fireworks` names. No timeline set.
