"""Vercel (Fireworks AI) onboarding form automation.

Completes the 2-page onboarding after signup/login:
Page 1: Account ID, First/Last Name, Terms checkbox → Continue
Page 2: Use case checkboxes → Submit

Docs: vercel_onboarding.doc.md
"""
import asyncio
import logging
import os

from sin_browser_tools.tools.interaction import (
    browser_type, browser_click_by_text, browser_click_checkbox_by_text,
)
from sin_browser_tools.tools.navigation import browser_get_url, browser_navigate, browser_press
from sin_browser_tools.tools.extraction import browser_console

logger = logging.getLogger(__name__)


async def _playwright_onboarding() -> None:
    """Complete the Fireworks onboarding form (2 pages).

    Page 1: Account ID (max 20 chars), First/Last Name, Terms checkbox → Continue
    Page 2: Use case checkboxes (Prototype, Flexible, Conversational, Search, Agentic) → Submit

    Strategy (V18.4 hybrid):
    1. Click "Reject All" on cookie banner (so it doesn't cover the form)
    2. Fill fields via browser_type (delay=30ms) — lets React pick up keystrokes
       naturally instead of bypassing with a raw value-setter that doesn't trigger
       React state updates reliably
    3. Use 4-strategy checkbox clicker (input[aria-label], [role=checkbox], label,
       :has-text) for Terms + use cases — Fireworks uses custom React checkboxes
    4. Continue / Submit via button click (force), fallback to form.requestSubmit()
       + Enter key
    5. Wait for redirect, fallback to force-navigate to /settings/users/api-keys
    """

    # ── Step 1: AGGRESSIVELY remove cookie banner ──────────────────────────
    # The banner has a "Customise" mode that shows hundreds of partner toggles
    # and completely covers the form. We must nuke it before doing anything.
    # First, scroll to top so all "Reject All" buttons are potentially visible.
    await browser_console("""(() => {
        // Scroll to top so the top Reject All button is in view
        window.scrollTo(0, 0);
    })()""")
    await asyncio.sleep(0.3)

    # Try clicking Reject All (top-of-page button, which is visible)
    try:
        await browser_click_by_text("Reject All", role="button")
        await asyncio.sleep(0.5)
        logger.info("Cookie banner rejected via 'Reject All' click")
    except Exception as e:
        logger.warning(f"Reject All click failed: {e}")

    # AGGRESSIVE: remove all cky-* elements via JS (catches anything that wasn't removed)
    await browser_console("""(() => {
        // Aggressive cky-* removal
        document.querySelectorAll('.cky-overlay,.cky-consent-container,.cky-modal,.cky-preference-center,[class*="cky-"]').forEach(e => e.remove());
        // Also remove any iframe-based cky banners
        document.querySelectorAll('iframe[src*="cky"]').forEach(e => e.remove());
        // Restore body scroll
        document.body.style.overflow = 'visible';
        document.documentElement.style.overflow = 'visible';
    })()""")
    await asyncio.sleep(0.5)

    # Verify cky-* elements are gone
    cky_count = (await browser_console("document.querySelectorAll('[class*=cky]').length") or {}).get("result", "0")
    logger.info(f"Cookie banner: {cky_count} cky elements remaining (should be 0)")

    # DIAG: screenshot after cookie banner removal
    try:
        from sin_browser_tools.core import manager
        os.makedirs("/tmp/onboarding-diag", exist_ok=True)
        await manager.page.screenshot(path="/tmp/onboarding-diag/after-cookie-cleanup.png")
    except Exception:
        pass

    # ── Step 2: Fill text fields via browser_type (delay=30ms triggers React) ─
    import secrets, string

    # Account ID — DO NOT TOUCH (Fireworks pre-fills it with a unique suggestion,
    # editing it triggers a "max 20 chars" validation error)
    has_aid = int((await browser_console("document.querySelectorAll('input[name=accountId]').length"))["result"])
    if has_aid > 0:
        # Just verify the pre-filled value is there; DO NOT overwrite
        current_aid = await browser_console("""(() => {
            var inp = document.querySelector('input[name="accountId"]');
            return inp ? (inp.value || '') : '';
        })()""")
        current_aid = (current_aid.get("result") or "").strip()
        if current_aid:
            logger.info(f"Account ID pre-filled by Fireworks: '{current_aid}' (using as-is, NOT overwriting)")
        else:
            # Field is empty — fill with a safe 11-char value
            aid = "sin" + "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
            try:
                await browser_type('input[name="accountId"]', aid)
            except Exception as e:
                logger.warning(f"browser_type accountId failed: {e}")
            await asyncio.sleep(0.3)
            logger.info(f"Account ID filled: {aid}")

    # First name
    has_fn = int((await browser_console("document.querySelectorAll('input[name=firstName]').length || document.querySelectorAll('input[name=first]').length"))["result"])
    if has_fn > 0:
        try:
            await browser_type('input[name="firstName"]', "Super")
        except Exception:
            try:
                await browser_type('input[name="first"]', "Super")
            except Exception as e:
                logger.warning(f"browser_type firstName failed: {e}")
        await asyncio.sleep(0.3)
        logger.info("First name filled")

    # Last name
    has_ln = int((await browser_console("document.querySelectorAll('input[name=lastName]').length || document.querySelectorAll('input[name=last]').length"))["result"])
    if has_ln > 0:
        try:
            await browser_type('input[name="lastName"]', "Cheetah")
        except Exception:
            try:
                await browser_type('input[name="last"]', "Cheetah")
            except Exception as e:
                logger.warning(f"browser_type lastName failed: {e}")
        await asyncio.sleep(0.3)
        logger.info("Last name filled")

    # ── Step 3: 4-strategy checkbox clicker (V18.4 fallback chain) ──────────
    # Terms checkbox — try multiple strategies
    # First, try the sin_browser_tools' browser_click_checkbox_by_text (uses sophisticated walker)
    terms_clicked = False
    try:
        from sin_browser_tools.tools.interaction import browser_click_checkbox_by_text as _sbt_click_cb
        r = await _sbt_click_cb("I agree to the Terms of Service and Privacy Policy")
        if r.get("success"):
            terms_clicked = True
            logger.info("Terms clicked via browser_click_checkbox_by_text")
    except Exception as e:
        logger.warning(f"browser_click_checkbox_by_text failed: {e}")

    if not terms_clicked:
        # Fallback: my own 4-strategy
        if not await _click_checkbox_any_strategy("agree"):
            await _click_checkbox_any_strategy("terms")
    await asyncio.sleep(0.5)

    # DIAG: check Terms checkbox state after click
    try:
        from sin_browser_tools.core import manager
        os.makedirs("/tmp/onboarding-diag", exist_ok=True)
        await manager.page.screenshot(path="/tmp/onboarding-diag/after-terms.png")
        cb_state = await browser_console("""(() => {
            // Find all input[type=checkbox] on the page
            var all = document.querySelectorAll('input[type="checkbox"]');
            var matches = [];
            for (var i=0; i<all.length; i++) {
                matches.push({
                    aria: all[i].getAttribute('aria-label') || '',
                    checked: all[i].checked,
                    disabled: all[i].disabled,
                    id: all[i].id || '',
                    name: all[i].name || '',
                    parent_text: (all[i].closest('label') || {}).textContent || ''
                });
            }
            return matches;
        })()""")
        logger.info(f"DIAG ALL checkboxes: {cb_state}")
    except Exception as e:
        logger.warning(f"DIAG Terms: {e}")

    # DIAG: check Terms checkbox state after click
    try:
        from sin_browser_tools.core import manager
        os.makedirs("/tmp/onboarding-diag", exist_ok=True)
        await manager.page.screenshot(path="/tmp/onboarding-diag/after-terms.png")
        cb_state = await browser_console("""(() => {
            // Find Terms checkbox and report its checked state
            var inputs = document.querySelectorAll('input[type="checkbox"]');
            var matches = [];
            for (var i=0; i<inputs.length; i++) {
                var lbl = (inputs[i].getAttribute('aria-label') || '').toLowerCase();
                if (lbl.indexOf('agree') !== -1 || lbl.indexOf('terms') !== -1) {
                    matches.push({
                        aria: lbl,
                        checked: inputs[i].checked,
                        disabled: inputs[i].disabled
                    });
                }
            }
            // Also check role=checkboxes
            var roles = document.querySelectorAll('[role="checkbox"]');
            for (var j=0; j<roles.length; j++) {
                var al = (roles[j].getAttribute('aria-label') || '').toLowerCase();
                if (al.indexOf('agree') !== -1 || al.indexOf('terms') !== -1) {
                    matches.push({
                        role_aria: al,
                        checked: roles[j].getAttribute('aria-checked'),
                        cls: (roles[j].className || '').slice(0, 50)
                    });
                }
            }
            return matches;
        })()""")
        logger.info(f"DIAG Terms checkbox state: {cb_state}")
    except Exception as e:
        logger.warning(f"DIAG Terms: {e}")

    # DIAG: screenshot before Continue
    try:
        from sin_browser_tools.core import manager
        os.makedirs("/tmp/onboarding-diag", exist_ok=True)
        await manager.page.screenshot(path="/tmp/onboarding-diag/before-continue.png")
        # Log Continue button state — ONLY match "Continue", NEVER "Next"
        btn_state = await browser_console("""(() => {
            var b = document.querySelectorAll('button');
            var all_btns = [];
            for (var i=0; i<b.length; i++) {
                all_btns.push({
                    text: (b[i].textContent || '').trim(),
                    disabled: b[i].disabled || b[i].getAttribute('aria-disabled') === 'true',
                    type: b[i].type,
                    cls: (b[i].className || '').slice(0, 40)
                });
            }
            return all_btns;
        })()""")
        logger.info(f"DIAG all buttons: {btn_state}")
    except Exception as e:
        logger.warning(f"DIAG: {e}")

    # ── Step 4: Continue (Page 1 → Page 2) ─────────────────────────────────
    # CRITICAL: only match "Continue" exactly, NOT "Next" — there's a carousel
    # "Next slide" button that appears first in the DOM and would steal the click.
    cur_url = (await browser_get_url())["url"]
    cur_text = (await browser_console("document.body.innerText") or {}).get("result", "")[:300]
    logger.info(f"Before Continue: url={cur_url}, body text starts: {cur_text[:200]!r}")

    clicked_continue = False
    try:
        r = await browser_click_by_text("Continue", role="button")
        if r.get("status") == "clicked":
            clicked_continue = True
            logger.info("Continue clicked via browser_click_by_text")
    except Exception as e:
        logger.warning(f"browser_click_by_text('Continue') failed: {e}")

    if not clicked_continue:
        # Fallback: dispatchEvent on button with EXACTLY text "Continue" (no Next)
        logger.info("Trying JS dispatchEvent on Continue button (exact match, no Next)")
        r2 = await browser_console("""(() => {
            var b = document.querySelectorAll('button');
            for (var i=0; i<b.length; i++) {
                var t = (b[i].textContent || '').trim();
                // Only match buttons whose text is EXACTLY "Continue" or contains
                // the word "Continue" — NEVER match "Next slide" / "Next page"
                if (t === 'Continue' || t.indexOf('Continue') !== -1) {
                    b[i].dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                    return t;
                }
            }
            return 'no_continue_button';
        })()""")
        logger.info(f"JS dispatchEvent result: {r2}")
    await asyncio.sleep(3)

    # Verify we left page 1
    after_url = (await browser_get_url())["url"]
    logger.info(f"After Continue: url={after_url}")
    try:
        from sin_browser_tools.core import manager
        os.makedirs("/tmp/onboarding-diag", exist_ok=True)
        await manager.page.screenshot(path="/tmp/onboarding-diag/after-continue.png")
    except Exception:
        pass

    # ── Step 5: Use-case checkboxes (Page 2) ─────────────────────────────────
    for uc in [
        "Prototype with open models",
        "Flexible capacity for experimentation",
        "Conversational AI",
        "Search",
        "Agentic AI",
    ]:
        if not await _click_checkbox_any_strategy(uc):
            logger.warning(f"Use-case '{uc}' not found")
        await asyncio.sleep(0.2)

    # ── Step 6: Submit (Page 2 → home/settings) ─────────────────────────────
    try:
        await browser_click_by_text("Submit", role="button")
    except Exception:
        for txt in ("Get $5", "Finish", "Continue"):
            try:
                await browser_click_by_text(txt, role="button")
                break
            except Exception:
                continue
    await asyncio.sleep(2)

    # Fallback: still on /onboarding → form.requestSubmit() + Enter
    url = (await browser_get_url())["url"]
    if 'onboarding' in url:
        await browser_console("""(() => {
            var forms = document.forms;
            for (var i=0; i<forms.length; i++) {
                forms[i].requestSubmit();
                return 'submitted';
            }
            return 'no_form';
        })()""")
        logger.info("Form submitted via requestSubmit()")
        await asyncio.sleep(5)
        url = (await browser_get_url())["url"]
        if 'onboarding' in url:
            await browser_press("Enter")
            logger.info("Enter key sent as Submit fallback (disabled bypass)")
            await asyncio.sleep(5)

    for _ in range(45):  # 45s wait — server-side processing can be slow
        await asyncio.sleep(1)
        url = (await browser_get_url())["url"]
        if any(x in url for x in ['home', 'account', 'settings', 'api-keys', 'models']):
            logger.info(f"Onboarding redirect: {url[:60]}")
            return
    else:
        logger.warning("Playwright onboarding — kein Redirect nach 45s, force navigate")
        try:
            await browser_navigate("https://app.fireworks.ai/settings/users/api-keys")
            # Wait a bit longer for the force-navigate to take effect
            for _ in range(15):
                await asyncio.sleep(1)
                url = (await browser_get_url())["url"]
                if any(x in url for x in ['home', 'account', 'settings', 'api-keys', 'models']):
                    logger.info(f"Force-nav redirect: {url[:60]}")
                    return
        except Exception:
            pass


# ── Vercel Alias (clear naming, backward compat) ──────────────────────
vercel_onboarding = _playwright_onboarding


async def _click_checkbox_any_strategy(match_text: str) -> bool:
    """Try multiple strategies to click a custom-React checkbox. Returns True on success."""
    mt = match_text.lower()
    # 1. input[type="checkbox"] with aria-label containing match
    r = await browser_console(f"""(() => {{
        var inputs = document.querySelectorAll('input[type="checkbox"]');
        for (var i=0; i<inputs.length; i++) {{
            var lbl = (inputs[i].getAttribute('aria-label') || '').toLowerCase();
            if (lbl.indexOf({mt!r}) !== -1) {{ inputs[i].click(); return 'input'; }}
        }}
        // 2. [role="checkbox"] with aria-label
        var els = document.querySelectorAll('[role="checkbox"]');
        for (var j=0; j<els.length; j++) {{
            var l = (els[j].getAttribute('aria-label') || '').toLowerCase();
            if (l.indexOf({mt!r}) !== -1) {{ els[j].click(); return 'role'; }}
        }}
        // 3. Label text containing match
        var labels = document.querySelectorAll('label');
        for (var k=0; k<labels.length; k++) {{
            if (labels[k].textContent.toLowerCase().indexOf({mt!r}) !== -1) {{
                var cb = labels[k].querySelector('input[type="checkbox"], [role="checkbox"]') || labels[k];
                cb.click(); return 'label';
            }}
        }}
        return 'not_found';
    }})()""")
    result = r.get("result", "not_found")
    if result != "not_found":
        logger.info(f"Checkbox '{match_text}' clicked via {result}")
        return True
    # 4. Last resort: SIN-browser-tool browser_click_checkbox_by_text
    try:
        r2 = await browser_click_checkbox_by_text(match_text)
        if r2.get("success"):
            logger.info(f"Checkbox '{match_text}' clicked via browser_click_checkbox_by_text")
            return True
    except Exception:
        pass
    logger.warning(f"Checkbox '{match_text}' NOT clicked")
    return False
