# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- Pinned all Python dependencies to exact versions (supply-chain hardening).
- Replaced `random` with `secrets` for all security-critical generation (alias names, account IDs, token names) — CWE-338.
- Added Bearer token authentication (`SINATOR_AUTH_TOKEN`) on all mutating pool endpoints — ASVS V3.5.
- Removed API key partial logging from `rotate.py` — no key material in logs (CWE-532).

### Fixed
- Fixed `await _time.sleep(5)` typo in `billing_tracker.py` — now `await asyncio.sleep(5)`.

## [0.25] - 2026-06-03

### Security
- Removed API key prefix logging from `tools/rotate.py` — logs `key_id` only.

## [0.24] - 2026-06-03

### Changed
- Disabled SMSPool (UK numbers not receiving Vercel OTPs).
- Vercel signup works without phone verification (proven E2E).

### Fixed
- Re-Login before OTP reading: GMX session expires during alias rotation + signup (~4-5 min).

## [0.23] - 2026-06-03

### Fixed
- Login-Redirect handling on `/account/tokens` → auto-login before API key extraction.
- JS syntax error in `_generate_api_token`: `(() => { ... })()` instead of `() => { ... }()`.
- Playwright hang after GMX login — added timeouts to `browser_click_by_text`.

## [0.22] - 2026-06-03

### Added
- E2E ALMOST SUCCESS: Alias `neon-viper-815@gmx.de`, OTP `645102`, Dashboard reached.

### Fixed
- Subdomain-aware SID extraction: `navigator.gmx.net` vs `bap.navigator.gmx.net`.

## [0.21] - 2026-06-03

### Changed
- `read_otp()` navigates directly to mail iframe (`webmailer.gmx.net`) for AXTree visibility.

### Fixed
- JSESSIONID false blocker removed — continues even if cookie missing.

## [0.20] - 2026-06-03

### Fixed
- Vercel timeouts: `asyncio.wait_for(..., timeout=15)` wrapper around `browser_click_by_text`.

## [0.19] - 2026-06-03

### Added
- Fallback `read_otp_cdp_axtree()` on `fresh_tab` when iframe navigation fails.
- OTP `243054` found via CDP AXTree fallback.

### Fixed
- Subdomain-SID fix: `mail_url` uses same domain as source URL.

## [0.18] - 2026-06-03

### Added
- `read_otp()` fixed: recognizes both "E-Mail" and "Zum Postfach" texts.
- Subdomain-dynamik for `mail_url`.

## [0.17] - 2026-06-03

### Fixed
- `read_otp()` bug: JSESSIONID check was false blocker → Warning + continue.

## [0.16] - 2026-06-03

### Fixed
- JSESSIONID false blocker: removed hard check, now warns and continues.

## [0.15] - 2026-06-03

### Added
- Consent-Handling in CDP AXTree: detects consent page → JS click → navigates to inbox.

## [0.14] - 2026-06-03

### Fixed
- Pool crash: `add_to_pool` crashed when `api_key=None`.
- API Key extraction: `browser_console()` returns CDP Dict → `.get("result")` unwrap.

## [0.13] - 2026-06-03

### Fixed
- API key extraction: CDP Dict unwrap fixed (`result.get("result")`).

## [0.12] - 2026-06-03

### Added
- First E2E success: Alias `neon-shark-462@gmx.de`, OTP `295518`.

### Fixed
- Vercel signup without phone verification works (SMSPool not needed).

## [0.11] - 2026-06-03

### Added
- OTP regexes for Vercel: URL- and code-patterns for `vercel.com` + `v0.app`.

## [0.10] - 2026-06-03

### Added
- Bot Chrome start script (`scripts/start_bot_chrome.sh`) on port 9230.

## [0.9] - 2026-06-03

### Added
- GMX Login flow via `_login()` for fresh Bot Chrome sessions.

## [0.8] - 2026-06-03

### Added
- Vercel OTP return handling: supports both `otp_code` (6-digit) and `otp_url` formats.

## [0.1] - 2026-06-03

### Added
- Initial release: SINator-v0+Vercel — Vercel API key rotation via GMX aliases.
- GMX alias rotation, Vercel signup, OTP reading, pool management.

---

*Tags: v0.1 … v0.26-p1-security*
