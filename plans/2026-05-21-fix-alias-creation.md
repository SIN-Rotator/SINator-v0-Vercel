# Fix GMX Alias Creation — Plan

## Problem
Raw CDP kann Cross-Origin-Iframes (`3c.gmx.net`) nicht handlen.
Alle DOM.getBoxModel Calls returnen stale NodeIDs (0).

## Lösung: Playwright für Iframe-Interaktion
CUA bleibt für Navigation (E-Mail → Einstellungen).
Playwright übernimmt die Alias-Formular-Interaktion innerhalb des Iframes.

## Tasks

### ✅ Done
- [x] CUA Navigation fix (E-Mail Link → Einstellungen → E-Mail-Adressen)
- [x] Session detection (app_name filter)
- [x] Element regex fix (both `] - [N]` and `- [N]` formats)

### 🔧 Phase 1: Playwright Integration
- [ ] `pip install playwright && playwright install chromium`
- [ ] Playwright connect zu laufendem Chrome (CDP Port 9222)
- [ ] Iframe finden (`page.frames` filter by URL `3c.gmx.net`)
- [ ] Input-Feld im Iframe via `frame.fill('[name*="localPart"]', alias_name)`
- [ ] Button via `frame.click('button:has-text("Hinzufügen")')`
- [ ] Verification: `frame.text_content()` check auf alias email

### 🔧 Phase 2: Integration in gmx_service.py
- [ ] Neue Methode `_create_alias_via_playwright(alias_name, cdp_port)`
- [ ] Replace `_find_alias_input_coords` + `_fill_alias_input_via_cdp` + `_click_button_via_cdp`
- [ ] Keep CUA navigation unchanged
- [ ] Test standalone create + rotate

### 🔧 Phase 3: End-to-End Test
- [ ] Full rotation: delete existing → create new alias
- [ ] Verify alias exists on GMX page
- [ ] Push to GitHub

## Alternativen (nicht gewählt)
- **mlx-use / Vision**: Overkill für diesen Use-Case, stealth-runner dependency zu schwer
- **HTTP API**: Reverse-Engineering nötig, Wicket Forms komplex
- **Raw CDP + OOPIF Sessions**: Zu fragil, NodeIDs stale
