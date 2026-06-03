# Vercel Account

Fireworks AI (Vercel platform) account lifecycle: signup, verify, login.

## Purpose
Automates Vercel account creation via SIN-Browser-Tools (100% zero raw Playwright calls).

## Dependencies
- Used by: `rotate.py`, `fireworks_service.py` (Facade)
- Uses: `vercel_onboarding.py`, `sin_browser_tools` (navigation, interaction, extraction)

## Flow
1. `signup_vercel(email, password)` -- navigate -> cookie banner removal -> fill email -> Enter -> fill passwords -> Create Account
2. `verify_vercel(verify_url)` -- open verification URL from GMX email -> wait for redirect
3. `login_vercel(email, password)` -- two-step login -> handle onboarding redirect

## Security
- Uses `secrets` module for token generation (not `random` -- CWE-338 fix)
- No API key material logged (only `key_id`)

## Caveats
- CAPTCHA detection: returns error immediately if "verify you are human" found
- Cookie banner must be aggressively removed before form interaction
- "Next slide" carousel button conflicts with form "Next" -- Enter key used instead
