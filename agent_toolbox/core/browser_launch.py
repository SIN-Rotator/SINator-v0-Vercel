"""Bot Chrome launch and cleanup for Fireworks/Vercel automation.

Creates an ephemeral Chromium instance with anti-detection patches and
registers it with SIN-Browser-Tools manager.

Docs: browser_launch.doc.md
"""
import asyncio
import logging
from typing import Dict, Any

from agent_toolbox.core.browser_handle import _BrowserHandle

logger = logging.getLogger(__name__)


async def launch() -> Dict[str, Any]:
    """Launch Bot Chrome with stealth patches and register with SIN-Browser-Tools.

    Creates an ephemeral Chromium instance with:
    - Window size 1200x800 (not maximized — avoids layout detection)
    - German locale/timezone (matches GMX account region)
    - Anti-detection: webdriver, plugins, languages, chrome.runtime

    Returns:
        Dict with 'browser_manager' (_BrowserHandle) for caller to cleanup.
    """
    from playwright.async_api import async_playwright
    from sin_browser_tools.core.manager import manager

    pw = await async_playwright().start()
    # Window size 1200x800 — NOT --start-maximized (which BrowserManager hardcodes)
    browser = await pw.chromium.launch(
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-size=1200,800",
        ],
    )
    context = await browser.new_context(
        viewport={"width": 1200, "height": 800},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        locale="de-DE",
        timezone_id="Europe/Berlin",
        accept_downloads=True,
        bypass_csp=True,
        ignore_https_errors=True,
    )
    page = await context.new_page()

    # Stealth patches via add_init_script
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['de-DE', 'de', 'en-US', 'en'] });
        window.chrome = { runtime: {} };
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters);
    """)

    handle = _BrowserHandle(page, context, browser, pw)
    manager._set_instance(handle)
    logger.info("Bot Chrome launched (stays open until API key success)")
    return {"status": "launched", "browser_manager": handle}


async def cleanup_bot(browser_manager=None) -> None:
    """Close Bot Chrome and deregister from SIN-Browser-Tools.

    Called after API key is generated (success) or on rotation failure.
    Safe to call multiple times — all close() calls are idempotent.
    """
    if browser_manager:
        try:
            from sin_browser_tools.core import manager
            await browser_manager.cleanup()
            manager._set_instance(None)
            logger.info("Bot Chrome cleaned up")
        except Exception as e:
            logger.warning(f"Bot Chrome cleanup error: {e}")
