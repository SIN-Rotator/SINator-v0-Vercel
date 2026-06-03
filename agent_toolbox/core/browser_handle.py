"""Browser handle duck-type for SIN-Browser-Tools compatibility.

Provides a minimal BrowserManager-compatible wrapper around a raw
Playwright launch, bypassing the full BrowserManager which hardcodes
--start-maximized (detectable by Fireworks anti-bot).

Docs: browser_handle.doc.md
"""
import asyncio
import logging
import weakref
from typing import Optional

logger = logging.getLogger(__name__)


class _BrowserHandle:
    """Duck-type wrapper satisfying SIN-Browser-Tools manager._set_instance().

    SIN-Browser-Tools expects a BrowserManager with _page, _context, _browser,
    _playwright attributes. This class provides those from a raw Playwright
    launch, bypassing BrowserManager which hardcodes --start-maximized.
    """

    def __init__(self, page, context, browser, pw):
        self._page = page
        self._context = context
        self._browser = browser
        self._playwright = pw
        self._started = True
        self._dialog_queue = asyncio.Queue()
        self._pending_dialog = None
        self._dialog_pages = weakref.WeakSet()
        self._registry_stub = None
        self._browser_pid = None

    @property
    def page(self):
        """Active Playwright page — used by SIN-Browser-Tools for all operations."""
        return self._page

    @property
    def context(self):
        """Browser context — holds cookies, storage, and page references."""
        return self._context

    async def cleanup(self):
        """Close context, browser, and Playwright instance. Idempotent."""
        try:
            await self._context.close()
        except Exception:
            pass
        try:
            await self._browser.close()
        except Exception:
            pass
        try:
            await self._playwright.stop()
        except Exception:
            pass

    def set_active_page(self, p):
        """Update active page reference (called by SIN-Browser-Tools on tab switch)."""
        self._page = p
        self._context = p.context

    async def new_page(self):
        """Create a new page in the browser context."""
        return await self._context.new_page()

    @property
    def active_page(self):
        """Alias for page — backward compatibility with BrowserManager API."""
        return self._page

    def clear_active_page(self):
        """Set active page to None (used during cleanup)."""
        self._page = None

    async def get_next_dialog(self, timeout=5.0, consume=True):
        """No-op — dialogs are not handled in Bot Chrome."""
        return None

    def _setup_dialog_handler(self):
        """No-op — dialog handler not needed for Fireworks flow."""
        pass
