"""Vercel (Fireworks AI) API key extraction.

Navigates to /settings/users/api-keys, creates a new key, and extracts
the fw_ token from page text.

Docs: vercel_apikey.doc.md
"""
import asyncio
import logging
import re
from typing import Dict, Any

from sin_browser_tools.tools.navigation import browser_navigate, browser_get_url
from sin_browser_tools.tools.interaction import browser_click_by_text, browser_fill
from sin_browser_tools.tools.extraction import browser_console
from sin_browser_tools.tools.vision import browser_get_text

logger = logging.getLogger(__name__)


async def create_api_key(key_name: str = "sinator-key", **kwargs) -> Dict[str, Any]:
    """Generate a Fireworks API key via the web UI.

    Navigates to /settings/users/api-keys, clicks "Create API Key" → "API Key"
    menuitem, fills the key name, clicks Generate, then polls for the fw_ key
    pattern in page text (up to 15s).

    Bot Chrome stays open — caller must call cleanup_bot() after this.

    Args:
        key_name: Name for the API key (e.g., alias prefix like "pulse")

    Returns:
        Dict with 'status' ('success'|'error') and 'api_key' (fw_...) on success.
    """
    await browser_navigate("https://app.fireworks.ai/settings/users/api-keys")
    await asyncio.sleep(3)

    for _ in range(3):
        url = (await browser_get_url())["url"]
        if 'login' in url.lower():
            logger.warning(f"Redirected to login — retrying ({url[:60]})")
            # Try to log in directly from this page (it has redirectURI)
            try:
                from sin_browser_tools.tools.navigation import browser_press
                await browser_press("Enter")  # might submit a pre-filled form
            except Exception:
                pass
            await asyncio.sleep(1)
            await browser_navigate("https://app.fireworks.ai/settings/users/api-keys")
            await asyncio.sleep(3)
        else:
            break

    url = (await browser_get_url())["url"]
    if 'login' in url.lower() or 'onboarding' in url.lower():
        logger.error(f"Cannot access API keys — still on {url[:60]}")
        return {"status": "error", "error": f"Not past login/onboarding: {url[:60]}"}

    logger.info(f"API Keys page loaded: {url[:80]}")

    await browser_console("""document.querySelectorAll('.cky-overlay,.cky-consent-container,.cky-modal,[class*="cky-"]').forEach(e => e.remove()); document.body.style.overflow = 'visible';""")
    await asyncio.sleep(1)

    for attempt_try in range(3):
        try:
            await browser_click_by_text("Create API Key", role="button")
            await asyncio.sleep(2)
        except Exception:
            if attempt_try < 2:
                logger.warning("Create API Key button not found — retry")
                await browser_navigate("https://app.fireworks.ai/settings/users/api-keys")
                await asyncio.sleep(3)
                continue

        try:
            await browser_click_by_text("API Key", role="menuitem")
            await asyncio.sleep(2)
        except Exception:
            pass

        inp_count = int((await browser_console("document.querySelectorAll('input[name=name]').length"))["result"])
        if inp_count > 0:
            break
    else:
        logger.error("API Key dialog never appeared")
        return {"status": "error", "error": "Dialog not found"}

    for retry in range(3):
        suffix = f"-{retry}" if retry > 0 else ""
        name = key_name + suffix

        await browser_fill('input[name="name"]', name)
        await asyncio.sleep(1)

        try:
            await browser_click_by_text("Generate", role="button")
        except Exception:
            for kw in ("Generate API Key", "Generate", "Create"):
                try:
                    await browser_click_by_text(kw, role="button")
                    break
                except Exception:
                    continue

        for _ in range(15):
            await asyncio.sleep(1)
            text = (await browser_get_text("body")).get("text", "")
            keys = re.findall(r'fw_[a-zA-Z0-9]{20,}', text)
            if keys:
                return {"status": "success", "api_key": keys[0]}

        text = (await browser_get_text("body")).get("text", "")
        if 'Missing' in text and 'Name' in text:
            for kw in ('Close', 'Cancel', 'OK'):
                try:
                    await browser_click_by_text(kw, role="button")
                    await asyncio.sleep(1)
                    break
                except Exception:
                    continue
            continue
        break

    return {"status": "error", "error": "API Key not found after retry"}


# ── Vercel Alias (clear naming, backward compat) ──────────────────────
create_vercel_api_key = create_api_key
