"""Vercel (Fireworks AI) account lifecycle: signup, verify, login.

Uses 100% SIN-Browser-Tools (zero raw page.evaluate calls).

Docs: vercel_account.doc.md
"""
import asyncio
import logging
from typing import Dict, Any

from agent_toolbox.core.vercel_onboarding import _playwright_onboarding

logger = logging.getLogger(__name__)


async def signup_fireworks(email: str, password: str, **kwargs) -> Dict[str, Any]:
    """Create a new Fireworks account with the given email and password.

    Flow: navigate → remove CookieYes → fill email → Next → fill passwords → Create Account.
    Detects CAPTCHA and missing password fields as errors.

    Args:
        email: GMX alias email (e.g., pulse-runner-931@gmx.de)
        password: Fireworks account password

    Returns:
        Dict with 'status' ('signup_done'|'error') and 'steps_completed' list.
    """
    from sin_browser_tools.tools.navigation import browser_navigate, browser_get_url
    from sin_browser_tools.tools.interaction import browser_click_by_text, browser_fill
    from sin_browser_tools.tools.extraction import browser_console
    from sin_browser_tools.tools.vision import browser_get_text

    steps = []

    await browser_navigate("https://app.fireworks.ai/signup")
    await asyncio.sleep(3)
    logger.info(f"Signup page loaded")

    await browser_console("""document.querySelectorAll('.cky-overlay, .cky-consent-container, .cky-modal, .cky-preference-center').forEach(el => el.remove()); document.body.style.overflow = 'visible';""")
    await asyncio.sleep(1)

    r = await browser_fill('input[name="email"]', email)
    if r.get("status") != "typed":
        logger.error("Email fill failed")
        return {"status": "error", "error": "email_fill_failed", "steps_completed": steps}
    steps.append("email_filled")
    await asyncio.sleep(1)

    # Enter key — avoids carousel "Next slide" button conflict
    from sin_browser_tools.tools.navigation import browser_press
    await browser_press("Enter")
    logger.info("Email submitted via Enter key")

    for _ in range(12):
        await asyncio.sleep(1)
        pw_count = int((await browser_console("document.querySelectorAll('input[type=password]').length"))["result"])
        if pw_count >= 2:
            break
        body = (await browser_get_text("body")).get("text", "")
        if 'captcha' in body.lower() or 'verify you are human' in body.lower():
            logger.error("CAPTCHA detected")
            return {"status": "error", "error": "captcha", "steps_completed": steps}
    else:
        body = (await browser_get_text("body")).get("text", "")
        logger.error(f"Password fields not found. Page text: {body[:300]}")
        return {"status": "error", "error": "no_password_fields", "steps_completed": steps}
    steps.append("next_clicked")

    await browser_fill('input[name="password"]', password)
    await browser_fill('input[name="confirmPassword"]', password)
    steps.append("passwords_filled")

    await browser_click_by_text("Create Account", role="button")
    logger.info("Create Account clicked via browser_click_by_text")

    for _ in range(25):
        await asyncio.sleep(1)
        url = (await browser_get_url())["url"]
        if 'verify' in url.lower() or 'confirm' in url.lower():
            logger.info(f"Verify page detected: {url[:60]}")
            break
        body = (await browser_get_text("body")).get("text", "")
        if 'verify' in body.lower() or 'check your email' in body.lower():
            logger.info("Verify text detected")
            break
    else:
        logger.warning(f"No verify detected after signup")
    steps.append("create_clicked")

    return {"status": "signup_done", "steps_completed": steps}


async def verify_account(verify_url: str, **kwargs) -> bool:
    """Open the Fireworks verification URL to confirm the email address.

    Navigates to the URL (which contains the OTP token) and waits for
    redirect to onboarding/home. The URL is typically extracted from
    the GMX inbox by rotate.py.

    Args:
        verify_url: Full verification URL from Fireworks email

    Returns:
        True if verification succeeded (redirect detected or page loaded).
    """
    from sin_browser_tools.tools.navigation import browser_navigate, browser_get_url

    try:
        await browser_navigate(verify_url)
        await asyncio.sleep(2)
        url = (await browser_get_url())["url"]
        logger.info(f"Verify URL opened: {url[:80]}")
        # DIAG: screenshot after verify URL load
        try:
            import os
            os.makedirs("/tmp/onboarding-diag", exist_ok=True)
            from sin_browser_tools.core import manager
            await manager.page.screenshot(path="/tmp/onboarding-diag/verify-loaded.png")
        except Exception as e:
            logger.warning(f"DIAG verify shot failed: {e}")
        for _ in range(10):
            await asyncio.sleep(1)
            url = (await browser_get_url())["url"]
            if 'onboarding' in url.lower() or 'home' in url.lower() or 'account' in url.lower():
                # DIAG: screenshot when redirect detected
                try:
                    import os
                    from sin_browser_tools.core import manager
                    os.makedirs("/tmp/onboarding-diag", exist_ok=True)
                    await manager.page.screenshot(path=f"/tmp/onboarding-diag/verify-redirected-{url.replace('/','_')[:40]}.png")
                except Exception:
                    pass
                return True
        return True
    except Exception as e:
        logger.error(f"Verify error: {e}")
        return False


async def login_fireworks(email: str, password: str, **kwargs) -> Dict[str, Any]:
    """Log in to Fireworks AI and handle onboarding if redirected.

    Two-step login:
    1. Fill email → click Next (triggers email validation)
    2. Fill password → Enter key (submits form)

    After login, detects redirect:
    - /onboarding → runs _playwright_onboarding() then waits for home redirect
    - /home|/account|/settings → login success

    Uses Enter key instead of browser_click_by_text("Next") for password submit
    to avoid matching the carousel "Next slide" button (disabled, causes timeout).

    Args:
        email: GMX alias email
        password: Fireworks account password

    Returns:
        Dict with 'status' ('success'|'error') and 'steps_completed' list.
    """
    from sin_browser_tools.tools.navigation import browser_navigate, browser_get_url
    from sin_browser_tools.tools.interaction import browser_click_by_text, browser_fill
    from sin_browser_tools.tools.extraction import browser_console
    from sin_browser_tools.tools.vision import browser_get_text

    steps = []

    await browser_navigate("https://app.fireworks.ai/login")
    await asyncio.sleep(2)

    await browser_console("""document.querySelectorAll('.cky-overlay,.cky-consent-container,.cky-modal,[class*="cky-"]').forEach(e => e.remove()); document.body.style.overflow = 'visible';""")
    await asyncio.sleep(1)

    for attempt in range(3):
        try:
            r = await browser_click_by_text("Email Login", role="link")
            if r.get("status") == "clicked":
                break
        except Exception:
            pass
        try:
            await browser_navigate("https://app.fireworks.ai/login?useEmail=true")
        except Exception:
            pass
        await asyncio.sleep(2)
        email_count = int((await browser_console("document.querySelectorAll('input[name=email]').length"))["result"])
        if email_count > 0:
            break
    steps.append("login_page")

    await browser_fill('input[name="email"]', email)
    steps.append("email_filled")

    from sin_browser_tools.tools.navigation import browser_press
    await browser_press("Enter")
    logger.info("Login email submitted via Enter key")
    await asyncio.sleep(2)

    pw_count = int((await browser_console("document.querySelectorAll('input[type=password]').length"))["result"])
    if pw_count > 0:
        await browser_fill('input[type="password"]', password)
        steps.append("password_filled")
    else:
        await browser_fill('input[name="password"]', password)
        steps.append("password_filled")

    from sin_browser_tools.tools.navigation import browser_press
    await browser_press("Enter")
    await asyncio.sleep(2)
    steps.append("form_submitted")

    for _ in range(15):
        await asyncio.sleep(2)
        url = (await browser_get_url())["url"]
        if 'login' not in url.lower():
            if 'onboarding' in url:
                logger.info("Onboarding detected, running workflow")
                await _playwright_onboarding()
                steps.append("onboarding_complete")
                await asyncio.sleep(3)
                break
            if any(x in url for x in ['home', 'account', 'settings', 'api-keys', 'models']):
                logger.info(f"Login redirect detected: {url[:60]}")
                steps.append("login_success")
                return {"status": "success", "steps_completed": steps}

    for _ in range(10):
        await asyncio.sleep(2)
        url = (await browser_get_url())["url"]
        if 'login' not in url.lower():
            if any(x in url for x in ['home', 'account', 'settings', 'api-keys', 'models']):
                logger.info(f"Final redirect: {url[:60]}")
                steps.append("login_success")
                return {"status": "success", "steps_completed": steps}

    for u in [
        "https://app.fireworks.ai/settings/users/api-keys",
        "https://app.fireworks.ai/",
    ]:
        try:
            await browser_navigate(u)
            await asyncio.sleep(2)
            url = (await browser_get_url())["url"]
            if 'login' not in url.lower():
                steps.append("login_success")
                return {"status": "success", "steps_completed": steps}
        except Exception:
            pass

    return {"status": "error", "steps_completed": steps, "error": "could not reach home/settings"}


# ── Vercel Aliases (clear naming, backward compat) ──────────────────────
signup_vercel = signup_fireworks
verify_vercel = verify_account
login_vercel = login_fireworks
