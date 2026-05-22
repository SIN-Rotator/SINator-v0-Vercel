# BUILDING PLAN — SINator Fireworks AI V5 ✅ (2026-05-22)

## ✅ Status: COMPLETE FLOW V5 VERIFIED

```
GMX Rotation (19.8s) → Fireworks Signup → OTP → Login → Onboarding → API Key → Pool
Latest: crystal-beetle-676 → fw_MdM6tGucgWuuc7zQyJGeTK
```

| Flow | Name | Status | Tool |
|------|------|:---:|------|
| #0 | GMX Session | ✅ | Playwright "E-Mail" click → SID |
| #1 | GMX Alias Delete | ✅ | Playwright iframe hover+click + CUA OK |
| #1 | GMX Alias Create | ✅ | Playwright iframe fill+click, verify empty |
| #2 | Fireworks Signup | ✅ | Playwright + CUA: email→pw→Create→OTP→Verify |
| #3 | Fireworks Login | ✅ | Playwright form `a:has-text("Email Login")` + CUA onboarding |
| #4 | Onboarding | ✅ | CUA: "First"+"Last" type_text + Terms AXPress |
| #5 | Use-Case + $5 | ✅ | CUA dynamic scan text-based checkboxes |
| #6 | API Key | ✅ | PopUpButton force-click + menuitem + Generate |
| #7 | Pool | ✅ | Auto-save (4 keys total, 3 available) |

## ✅ Completed Milestones

| # | Task | Ergebnis |
|---|------|----------|
| 1 | Full-Flow Automation | `rotation.py` V5 — Playwright+CUA hybrid |
| 2 | API-Key Pool | 4 Keys (3 available), auto-save |
| 3 | fireworks_service.py | 3103→114 Zeilen (-96%), V5 Playwright+CUA |
| 4 | Cleanup | Obsolete files gelöscht (preflight.py, command_registry.json, etc.) |
| 5 | Single Command | `python tools/rotate.py` — E2E in einem Befehl |
| 6 | Dynamic CUA Scanning | Text-based `_find_element()` — keine Hardcoded-Indizes |
| 7 | Chrome Config | NON-accessibility mode: `--profile-directory="Profile 901"`, Port 9222 |

## 🔴 Critical Learnings for Future Work

| Learning | Warum wichtig |
|----------|--------------|
| `_re` import in JEDER Function | Function-scoped, propagiert nicht von global |
| CUA `"First"+"Last"` NOT `"Name"` | "Name" matcht "Company Name" zuerst |
| CUA element indices LABILE | React re-renders → immer text-based scan |
| Onboarding: ALLE Felder → Terms → Continue | Reihenfolge MUSS eingehalten werden |
| Continue → Login Redirect | Account confirmed → muss erneut einloggen |
| `/settings/users/api-keys` NOT `workspace` | 404 beim falschen Pfad |
| Fireworks Logout before Signup | Alte Session blockiert Signup-Form |
| Email input: `name="email"` NOT `type="email"` | Kein type-Attribut! |
| `pkill -9` KILLT USER CHROME | Nur SIGTERM via `kill` |

## 📂 Cleanup Done
- [x] `decrypt_cookies.py` → gelöscht
- [x] `preflight.py` → gelöscht
- [x] `verify_hashes.py` → gelöscht
- [x] `protection/gmx_hashes.json` → gelöscht
- [x] `command_registry.json` → gelöscht
- [x] 4 obsolete Fireworks Schemas → entfernt
- [x] `fireworks_service.py` → 3103→114 Zeilen (-96%)

## 📚 Documentation
- [x] AGENTS.md — V5 complete flow + critical patterns + archived CDP docs
- [x] README.md — Complete Flow + Code Snippets + API Key Pool
- [x] plans/knowledge-base.md — All Learnings + Tool Comparison
- [x] banned.md — Neue E2E Flow Patterns
- [x] plan.md — Diese Datei
- [x] sinrules.md — Updated Rules + Mandatory Patterns
- [x] gmx-alias-tool/README.md — Updated

## 🚀 Quick Start

```bash
# Chrome mit Profile 901 (OHNE accessibility!)
nohup "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --user-data-dir="/Users/jeremy/Library/Application Support/Google Chrome" \
  --profile-directory="Profile 901" \
  --remote-debugging-port=9222 \
  --no-first-run --no-default-browser-check \
  > /tmp/chrome_sinator.log 2>&1 &

# CUA Daemon
cua-driver serve &

# Full Rotation (Single Command)
python tools/rotate.py

# API Server
python agent_toolbox/start_toolbox.py
curl -X POST http://localhost:8000/rotation/full \
  -H 'Content-Type: application/json' \
  -d '{"fireworks_password": "ZOE.jerry2024!"}'
```
