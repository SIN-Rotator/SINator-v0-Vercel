"""
SINator v0+Vercel — Full Rotation Orchestrator
Docs: rotate.doc.md

End-to-End Flow:
  1. Isolierten Chrome starten (temp-Profil, NIE User-Chrome)
  2. GMX Alias rotieren (löschen + erstellen)
  3. Vercel Signup mit Referral-Link (v0.app/ref/6IMSRI)
  4. GMX OTP (6-stellig numerisch) abrufen
  5. SMSPool UK-Nummer für Telefon-Verifizierung
  6. API-Token generieren und extrahieren
  7. In Pool speichern

Usage:
  python tools/rotate.py
"""
import asyncio
import json
import time
import logging
import uuid
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from sin_browser_tools.core.manager import BrowserManager
from sin_browser_tools.tools.navigation import manager as nav_mgr
from sin_browser_tools.tools.extraction import browser_console

# Import our services
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))  # repo root for agent_toolbox imports
sys.path.insert(0, str(Path(__file__).parent.parent / "agent_toolbox" / "core"))
from gmx_service import GmxService, get_gmx_service
from vercel_service import VercelService
from smspool_service import SMSPoolService

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setLevel(logging.DEBUG)
    _formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)

# ── Configuration ───────────────────────────────────────────────────────

POOL_FILE = Path(__file__).parent.parent / "data" / "vercel-pool.json"
SMSPOOL_API_KEY = "nKw7Vo0JVNqPGkLSRYkn66KVockWfcoa"  # Set via env var SMSPOOL_API_KEY
GMX_EMAIL = os.environ.get("GMX_EMAIL", "delqhi@gmx.de")
GMX_PASSWORD = os.environ.get("GMX_PASSWORD", "")


# ── Pool Storage ────────────────────────────────────────────────────────

def load_pool() -> list:
    if POOL_FILE.exists():
        try:
            with open(POOL_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Pool load error: {e}, starting fresh")
    return []


def save_pool(pool: list):
    POOL_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(POOL_FILE, "w") as f:
        json.dump(pool, f, indent=2, default=str)
    logger.info(f"Pool saved: {len(pool)} entries")


def add_to_pool(entry: Dict[str, Any]):
    pool = load_pool()
    entry["id"] = str(uuid.uuid4())
    entry["created_at"] = datetime.now(timezone.utc).isoformat()
    pool.append(entry)
    save_pool(pool)
    api_key = entry.get('api_key')
    key_id = entry.get('id', 'NONE')
    logger.info(f"Added to pool: {entry.get('email')} -> key_id={key_id}")


# ── Main Rotation ───────────────────────────────────────────────────────

async def run_rotation() -> Dict[str, Any]:
    start_time = time.time()
    steps = []

    # Load credentials from env
    smspool_key = os.environ.get("SMSPOOL_API_KEY", SMSPOOL_API_KEY)
    gmx_password = os.environ.get("GMX_PASSWORD", GMX_PASSWORD)

    if not gmx_password:
        logger.error("GMX_PASSWORD not set — cannot login to GMX")
        return {"status": "failed", "error": "GMX_PASSWORD missing", "steps": steps}

    # Step 0: Start isolated Chrome (temp profile — NEVER touches user Chrome)
    # CRITICAL: Must use channel="chrome" (system Chrome) — Playwright's bundled
    # Chromium (Chrome/120) is detected by Vercel bot protection and REJECTED
    # with "Please try again or try a different sign up method".
    # System Chrome (Chrome/148) passes Vercel's bot detection.
    logger.info("=== STEP 0: Start isolated Chrome ===")
    import tempfile
    from playwright.async_api import async_playwright
    _user_data_dir = tempfile.mkdtemp(prefix="sinator-automation-")
    _pw = await async_playwright().start()
    _pw_ctx = await _pw.chromium.launch_persistent_context(
        _user_data_dir,
        channel="chrome",
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--window-size=1200,800",
            "--no-first-run",
        ],
        accept_downloads=True,
        bypass_csp=True,
        ignore_https_errors=True,
        viewport={"width": 1200, "height": 800},
    )
    mgr = BrowserManager(headless=False)
    mgr._playwright = _pw
    mgr._context = _pw_ctx
    mgr._page = _pw_ctx.pages[0] if _pw_ctx.pages else await _pw_ctx.new_page()
    mgr._browser = None  # persistent context mode — no separate browser object
    nav_mgr._set_instance(mgr)
    logger.info(f"System Chrome started (channel=chrome, UA=Chrome/148, temp={_user_data_dir[:30]}...)")
    steps.append("chrome_started")

    # Step 1: Initialize GMX Service
    logger.info("=== STEP 1: Initialize GMX Service ===")
    gmx = get_gmx_service()
    gmx._password = gmx_password

    # Initialize multi-tab architecture — use _context for persistent context mode
    await gmx.initialize_architecture(mgr._browser or mgr._context)

    # Login to GMX (handles fresh session for Bot Chrome)
    logger.info("[GMX] Logging into GMX...")
    login_ok = await gmx._login(
        page=gmx.work_tab,
        email=GMX_EMAIL,
        password=gmx_password
    )
    if not login_ok:
        logger.error("GMX login failed")
        await mgr.cleanup()
        return {"status": "failed", "error": "GMX login failed", "steps": steps}

    # Navigate inbox_tab to GMX mail
    await gmx.navigate_inbox()
    steps.append("gmx_initialized")

    # Step 2: Rotate GMX Alias
    logger.info("=== STEP 2: Rotate GMX Alias ===")
    alias_result = await gmx.rotate_alias(page=gmx.work_tab)
    if alias_result.get("status") != "success":
        logger.error(f"Alias rotation failed: {alias_result}")
        await mgr.cleanup()
        return {"status": "failed", "error": f"Alias rotation: {alias_result}", "steps": steps}
    alias_email = alias_result["created_alias"]
    logger.info(f"Alias created: {alias_email}")
    steps.append("alias_rotated")

    # Step 3: Initialize Vercel Service and start signup
    logger.info("=== STEP 3: Vercel Signup ===")
    # Switch active page to a new tab for Vercel
    vercel_tab = await mgr.new_page()
    mgr.set_active_page(vercel_tab)
    vercel = VercelService(manager=mgr)

    # Open referral link and fill email (without OTP yet)
    logger.info("Navigating to referral link and filling email...")
    from sin_browser_tools.tools.navigation import browser_navigate, browser_press
    from sin_browser_tools.tools.interaction import browser_fill_react, browser_click_by_text
    from sin_browser_tools.tools.extraction import browser_get_html
    from sin_browser_tools.tools.navigation import browser_get_url

    await browser_navigate("https://v0.app/ref/6IMSRI")
    await asyncio.sleep(5)
    await vercel._handle_cookie_banner()
    await asyncio.sleep(1)

    # Wait for email field and fill
    for i in range(15):
        try:
            html = await browser_get_html()
            html_str = str(html).lower()
            if 'type="email"' in html_str or 'name="email"' in html_str:
                logger.info(f"Email field found after {i+1}s")
                break
        except Exception as e:
            logger.warning(f"Email field check #{i} failed: {e}")
        await asyncio.sleep(1)
    else:
        logger.error("Email field not found after 15s — Vercel page may not have loaded correctly")
        url_result = await browser_get_url()
        logger.error(f"Current URL: {url_result}")
        await mgr.cleanup()
        return {"status": "failed", "error": "vercel_email_field_not_found", "steps": steps}

    # Aggressive cookie banner removal before fill (ensure input is clickable)
    await browser_console("""(() => {
        const labels = ['Deny', 'Reject all', 'Only necessary'];
        for (const label of labels) {
            const btns = document.querySelectorAll('button, [role="button"]');
            for (const btn of btns) { if (btn.textContent.trim().includes(label)) { btn.click(); break; } }
        }
        document.querySelectorAll('.cky-overlay, .cky-consent-container, .cky-modal, .cky-preference-center, [class*=cookie], [id*=cookie], [class*=consent], [id*=consent]').forEach(el => el.remove());
        document.body.style.overflow = 'visible';
    })()""")
    await asyncio.sleep(0.5)

    # Fill email — React native value setter (Playwright .fill() doesn't update React state)
    fill_result = await browser_fill_react('input[type="email"]', alias_email)
    if not fill_result.get("success"):
        logger.warning(f"browser_fill_react failed: {fill_result.get('error')} — falling back to browser_type")
        from sin_browser_tools.tools.interaction import browser_type
        await browser_type('input[type="email"]', alias_email, delay_ms=30)
    await asyncio.sleep(0.5)

    # Verify field actually contains the alias
    email_val = (await browser_console("document.querySelector('input[type=email], input[name=email]')?.value")).get("result", "")
    if not email_val or alias_email not in str(email_val):
        logger.error(f"Email field empty after fill! value='{email_val}'")
        await browser_type('input[type="email"]', alias_email, delay_ms=30)
        await asyncio.sleep(0.5)

    # Submit email — Enter key is the ONLY reliable way (button clicks don't trigger React form submit)
    await browser_press("Enter")
    logger.info("Pressed Enter in email field")
    await asyncio.sleep(8)

    # Verify Vercel accepted the email and is now showing OTP input
    otp_page_state = await browser_console("""(() => {
        const digitsInput = document.querySelector('input[name="digits"]');
        const errorText = document.body.innerText.includes('Please try again');
        return {
            url: window.location.href,
            hasDigitsInput: !!digitsInput,
            digitsVisible: digitsInput ? digitsInput.offsetParent !== null : false,
            errorText: errorText,
            bodySnippet: document.body.innerText.substring(0, 400)
        };
    })()""")
    logger.info(f"[Step3] After Enter, OTP page state: {otp_page_state}")
    
    if otp_page_state.get("result", {}).get("errorText"):
        logger.error("Vercel rejected signup — bot detection or rate limit. Check Chrome channel=chrome.")
        await mgr.cleanup()
        return {"status": "failed", "error": "vercel_signup_rejected", "steps": steps}
    steps.append("vercel_email_submitted")

    # Step 3.5: Refresh GMX session — session expires during alias rotation + Vercel signup (~4-5min)
    logger.info("=== STEP 3.5: Refresh GMX Session ===")
    # Close old GMX tabs to avoid _otp_connect() finding stale targets
    for old_tab in [gmx.inbox_tab, gmx.work_tab]:
        try:
            await old_tab.close()
            logger.info("Closed old GMX tab")
        except Exception:
            pass
    # Create fresh tab and re-login for OTP reading
    fresh_tab = await mgr.new_page()
    login_ok = await gmx._login(
        page=fresh_tab,
        email=GMX_EMAIL,
        password=gmx_password
    )
    if not login_ok:
        logger.error("GMX re-login failed — session expired and cannot refresh")
        await mgr.cleanup()
        return {"status": "failed", "error": "GMX re-login failed", "steps": steps}
    gmx.inbox_tab = fresh_tab
    nav_ok = await gmx.navigate_inbox()
    if not nav_ok:
        logger.error("inbox_tab navigation failed after re-login")
        await mgr.cleanup()
        return {"status": "failed", "error": "inbox navigation failed", "steps": steps}
    logger.info(f"GMX re-login + inbox nav OK (SID={gmx.sid[:20] if gmx.sid else 'None'}...)")
    steps.append("gmx_relogged")

    # Step 4: Read OTP from GMX
    logger.info("=== STEP 4: Read OTP from GMX ===")
    # read_otp_main_frame_only uses Playwright native (no CDP needed).
    # Works with isolated Chrome which has no fixed CDP port.
    # Fallback: read_otp_cdp_axtree on fresh_tab if main-frame scan fails.
    otp_result = await gmx.read_otp_main_frame_only(sender_keyword="vercel", timeout=120)
    if otp_result.get("status") != "success":
        logger.info("Main-frame OTP failed. Fallback: CDP AXTree...")
        otp_result = await gmx.read_otp_cdp_axtree(sender_keyword="vercel", timeout=180, page=fresh_tab)
    if otp_result.get("status") != "success":
        logger.error("OTP read failed completely")
        await mgr.cleanup()
        return {"status": "failed", "error": f"OTP: {otp_result}", "steps": steps}
    # Handle both return formats: otp_code (6-digit) or otp_url (verification link)
    otp_code = otp_result.get("otp_code", "")
    otp_url = otp_result.get("otp_url", "")
    logger.info(f"OTP received: code={otp_code}, url={otp_url[:80] if otp_url else 'none'}")
    steps.append("otp_received")

    # Step 5: Enter OTP code on Vercel signup page + complete signup
    logger.info("=== STEP 5: Complete Vercel Signup ===")
    # Switch back to Vercel tab (where OTP input is shown)
    mgr.set_active_page(vercel_tab)
    
    # Generate password for account
    password = vercel._generate_password()

    # 5a: Fill OTP code in digits input
    logger.info(f"[Step5] Entering OTP code: {otp_code}")
    otp_filled = await vercel._fill_otp(otp_code, timeout=15)
    if not otp_filled:
        logger.error("OTP digits input not found on Vercel page")
        await mgr.cleanup()
        return {"status": "failed", "error": "OTP digits input not found", "steps": steps}
    steps.append("filled_otp")
    
    # 5b: Submit OTP (Enter key or Continue button)
    try:
        await browser_click_by_text("Continue", role="button", exact=False)
        logger.info("[Step5] Clicked Continue after OTP")
    except Exception:
        await browser_press("Enter")
        logger.info("[Step5] Pressed Enter after OTP")
    await asyncio.sleep(5)
    
    # 5c: Handle password creation if prompted
    pwd_result = await vercel._handle_password(password, timeout=15)
    if pwd_result:
        steps.append("set_password")
        logger.info("[Step5] Password set")
    
    # 5d: Wait for dashboard
    dashboard_ok = await vercel._wait_for_dashboard(timeout=30)
    if not dashboard_ok:
        logger.warning("[Step5] Dashboard not detected, continuing anyway")
    steps.append("dashboard")
    
    # 5e: Generate API token
    api_key = await vercel._generate_api_token(alias_email=alias_email, password=password)
    if api_key:
        steps.append("api_key_generated")
        logger.info(f"[Step5] API key generated: {api_key[:12]}...")
        signup_result = {
            "status": "success",
            "api_key": api_key,
            "account_email": alias_email,
            "password": password,
        }
    else:
        steps.append("api_key_failed")
        logger.error("[Step5] API key generation failed")
        signup_result = {
            "status": "partial",
            "error": "API key generation failed",
            "account_email": alias_email,
            "password": password,
        }

    if signup_result.get("status") == "success":
        api_key = signup_result["api_key"]
        password = signup_result.get("password", "")
        logger.info(f"Signup successful! api_key={api_key[:12]}...")
        steps.append("signup_success")

        # Step 6: Save to pool
        logger.info("=== STEP 6: Save to Pool ===")
        add_to_pool({
            "email": alias_email,
            "api_key": api_key,
            "password": password,
            "otp_result": otp_result,
            "signup_result": {k: v for k, v in signup_result.items() if k != "screenshots"},
        })
        steps.append("saved_to_pool")
    else:
        logger.error(f"Signup failed: {signup_result.get('error')}")
        # Still save partial result for debugging
        add_to_pool({
            "email": alias_email,
            "api_key": signup_result.get("api_key"),
            "password": signup_result.get("password", ""),
            "status": signup_result.get("status"),
            "error": signup_result.get("error"),
            "steps": steps,
        })

    elapsed = time.time() - start_time
    logger.info(f"Rotation completed in {elapsed:.1f}s")

    await mgr.cleanup()
    # Clean up temp profile directory
    try:
        import shutil
        if _user_data_dir and os.path.exists(_user_data_dir):
            shutil.rmtree(_user_data_dir, ignore_errors=True)
            logger.info(f"Cleaned up temp profile: {_user_data_dir[:30]}...")
    except Exception as e:
        logger.warning(f"Temp profile cleanup failed (non-critical): {e}")
    return {
        "status": signup_result.get("status"),
        "alias_email": alias_email,
        "api_key": signup_result.get("api_key"),
        "password": signup_result.get("password"),
        "steps": steps,
        "execution_time": f"{elapsed:.1f}s",
    }


if __name__ == "__main__":
    result = asyncio.run(run_rotation())
    print(json.dumps(result, indent=2, default=str))
