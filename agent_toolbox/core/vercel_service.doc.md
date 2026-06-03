# vercel_service.py

Docs: vercel_service.doc.md

## What
Vercel/v0.dev signup automation using exclusively sin-browser-tools. Completes the full flow from referral link to API token extraction.

## Dependencies
- `sin_browser_tools.core.manager.BrowserManager`
- `sin_browser_tools.tools.navigation` / `interaction` / `vision` / `extraction` / `diagnostics`

## Key Methods
- `signup(alias_email, otp_code, smspool_service, password)` — main orchestrator
- `_handle_cookie_banner()` — clicks Deny/Accept all with JS fallback
- `_fill_otp()` — fills 6-digit OTP with multiple selector fallbacks
- `_handle_password()` — detects and fills password fields
- `_handle_phone_verification()` — integrates SMSPool UK number + OTP poll
- `_generate_api_token()` — navigates to tokens page, creates, extracts token

## React Input Handling
Uses `browser_fill_react()` for all form inputs to bypass React controlled-value issues.

## Token Extraction Strategy
1. HTML regex search for 24+ char alphanumeric strings
2. JS querySelector fallback targeting `[data-testid="token-value"]`, `code`, `pre`, etc.
3. Body innerText scan filtering out common HTML/JS words

## Referral Link
`https://v0.app/ref/6IMSRI`

## Known Issues
- Token extraction relies on heuristics — may need adjustment if Vercel changes UI
- Phone verification only works if SMSPool API key is configured
