# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.26.x  | :white_check_mark: |
| < 0.25  | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability in SINator, please report it **privately**:

1. **Email:** `security@delqhi.com` (PGP key available on request)
2. **Do NOT open a public issue** — vulnerabilities are handled confidentially
3. Include:
   - Description of the vulnerability
   - Steps to reproduce (if safe to share)
   - Affected version(s)
   - Severity estimate (CVSS score if possible)

## Response Timeline

| Phase | Timeline |
|-------|----------|
| Acknowledgment | Within 48 hours |
| Initial assessment | Within 7 days |
| Fix released | Within 30 days (critical: 7 days) |
| Public disclosure | After fix is deployed + 30 days embargo |

## Security Best Practices for Users

1. **Never commit credentials** — Use environment variables or `.env` files (gitignored)
2. **Rotate GMX password** — After any suspected breach
3. **Use `SINATOR_AUTH_TOKEN`** — Protect pool API endpoints (v0.26+)
4. **Pin dependencies** — `requirements.txt` uses exact versions (v0.26+)
5. **Review logs** — API keys should never appear in log output

## Known Security Considerations

| Issue | Status | Mitigation |
|-------|--------|------------|
| Hardcoded creds in README (placeholder) | :white_check_mark: Fixed | Only placeholders, never real credentials |
| `random` module for ID generation | :white_check_mark: Fixed v0.26 | Replaced with `secrets` |
| API key partial logging | :white_check_mark: Fixed v0.25 | Log `key_id` only |
| Unpinned dependencies | :white_check_mark: Fixed v0.26 | All pinned to exact versions |
| Missing auth on pool endpoints | :white_check_mark: Fixed v0.26 | Bearer token required |
| JSON pool file (no ACID) | :warning: Open | Use file locking; migrate to SQLite for production |
| Chrome subprocess (AppleScript) | :warning: Accepted | Requires local access; not exposed remotely |

## CVE Policy

We do not currently request CVEs for vulnerabilities. If a third party assigns a CVE, we will update this document with the identifier and remediation status.

---

*Last updated: 2026-06-03*
