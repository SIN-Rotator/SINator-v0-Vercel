# Vercel Onboarding

Completes the 2-page Fireworks onboarding form after signup/login.

## Purpose
Page 1: Account ID, First/Last Name, Terms checkbox -> Continue
Page 2: Use case checkboxes -> Submit

## Dependencies
- Used by: `vercel_account.py`
- Uses: `sin_browser_tools` (browser_type, browser_click_by_text, browser_console)

## Strategy
1. Aggressive cookie banner removal (Reject All + JS strip all `cky-*` elements)
2. Account ID: verify pre-filled value, DO NOT overwrite (triggers "max 20 chars" validation)
3. Terms checkbox: 4-strategy clicker (input[aria-label], [role=checkbox], label text, SIN-Browser walker)
4. Continue/Submit: exact match only -- carousel "Next slide" would steal clicks
5. Wait 45s for server-side processing, force-navigate fallback

## Caveats
- React controlled inputs -- `browser_type` with 30ms delay triggers React state updates
- Disabled buttons: JS `dispatchEvent` + Enter key as fallback bypass
