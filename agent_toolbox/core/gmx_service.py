"""
SINator v0+Vercel — GMX Service (Playwright-native, adapted for Vercel OTP)
Docs: gmx_service.doc.md

Streamlined GMX service copied from sinator-fireworksai agent_toolbox/core/gmx_service.py
with OTP patterns adapted for Vercel 6-digit numeric codes instead of Fireworks confirm URLs.

Kernfunktionen:
  - GMX Alias-Rotation (Löschen + Erstellen)
  - OTP-Extraktion für Vercel (6-stellig numerisch, Subject: "XXXXXX is your Vercel sign up code")
  - Multi-Tab Architektur (work_tab + inbox_tab)

Playwright-native für Alias-Rotation.
OTP via Shadow-DOM Traversal (read_otp_main_frame_only) + CDP AXTree Fallback.
"""
import time
import random
import logging
import re
import asyncio
import json
import html as html_module
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

from playwright.async_api import async_playwright, Browser, Page, BrowserContext, Frame

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setLevel(logging.DEBUG)
    _formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)

GMX_HOME_URL = "https://www.gmx.net/"


class GmxService:
    def __init__(self, browser: Optional[Browser] = None, context: Optional[BrowserContext] = None, password: Optional[str] = None):
        self.browser = browser
        self.context = context
        self.password = password
        self.inbox_tab: Optional[Page] = None
        self.work_tab: Optional[Page] = None
        self.adjectives = [
            "elron", "dark", "swift", "iron", "silver", "golden", "crystal", "shadow",
            "storm", "frost", "blaze", "thunder", "cosmic", "neon", "cyber", "quantum",
            "alpha", "beta", "delta", "omega", "zenith", "nexus", "vortex", "pulse",
            "echo", "phantom", "spectra", "turbo", "hyper", "ultra", "mega", "super",
        ]
        self.nouns = [
            "vader", "runner", "hawk", "wolf", "fox", "tiger", "eagle", "shark",
            "dragon", "phoenix", "falcon", "panther", "cobra", "lynx", "raven", "jaguar",
            "bear", "lion", "whale", "dolphin", "puma", "cheetah", "otter", "badger",
            "wolverine", "raptor", "condor", "viper", "scorpion", "spider", "mantis", "beetle",
        ]

    def generate_alias_name(self) -> str:
        adj = random.choice(self.adjectives)
        noun = random.choice(self.nouns)
        num = random.randint(100, 999)
        return f"{adj}-{noun}-{num}"

    # ── Multi-Tab Architecture ───────────────────────────────────────────

    async def initialize_architecture(self, browser: Browser):
        """Erstelle isolierte Tabs: work_tab (Alias/FW) + inbox_tab (OTP, bleibt IMMER im Posteingang).
        inbox_tab wird ERST navigiert nach erfolgreichem Login (via navigate_inbox()).
        """
        logger.info("Initialisiere Multi-Tab Architektur...")
        self.browser = browser
        self.work_tab = await browser.new_page()
        self.inbox_tab = await browser.new_page()
        logger.info("Tabs erstellt. inbox_tab wird nach Login navigiert.")

    async def navigate_inbox(self):
        """Navigiert inbox_tab zum Posteingang (NUR nach Login aufrufen!)."""
        if self.inbox_tab is None:
            logger.error("inbox_tab nicht initialisiert")
            return False
        logger.info("Navigiere inbox_tab zum Posteingang...")
        await self.inbox_tab.goto("https://navigator.gmx.net/mail", wait_until="domcontentloaded")
        await asyncio.sleep(5)
        body = await self.inbox_tab.evaluate("() => document.body.innerText")
        if "Nicht eingeloggt" in body or ("anmelden" in body.lower()[:200] and "E-Mail" not in body):
            logger.error("inbox_tab Session ungültig — Login vorher ausführen!")
            return False
        logger.info("inbox_tab im Posteingang (session-verifiziert)")
        return True

    # ── Playwright CDP Connect ───────────────────────────────────────────

    async def _pw_connect(self, cdp_port: int = 9222, page: Optional[Page] = None) -> Page:
        """Connect to existing Chrome via CDP and return a Playwright Page."""
        if page is not None:
            logger.info("[_pw_connect] Using provided page")
            return page
        logger.info(f"[_pw_connect] Connecting to Chrome on CDP port {cdp_port}")
        p = await async_playwright().start()
        browser = await p.chromium.connect_over_cdp(f"http://localhost:{cdp_port}")
        page = None
        for ctx in browser.contexts:
            for pg in ctx.pages:
                url = pg.url or ""
                if "allEmailAddresses" in url and "settings" in url and "iac/restart" not in url:
                    page = pg
                    logger.info(f"[_pw_connect] Found allEmailAddresses page: {url[:60]}...")
                    return page
        for ctx in browser.contexts:
            for pg in ctx.pages:
                url = pg.url or ""
                if "gmx.net" in url and "iac/restart" not in url and "session-expired" not in url and "logoutlounge" not in url:
                    page = pg
                    logger.info(f"[_pw_connect] Found GMX page: {url[:60]}...")
                    return page
        for ctx in browser.contexts:
            for pg in ctx.pages:
                url = pg.url or ""
                if "iac/restart" not in url and "session-expired" not in url and "logoutlounge" not in url:
                    page = pg
                    logger.info(f"[_pw_connect] Using fallback page: {url[:60]}...")
                    return page
        if browser.contexts and browser.contexts[0].pages:
            page = browser.contexts[0].pages[0]
            logger.info(f"[_pw_connect] Using first page: {page.url[:60]}...")
        else:
            page = await browser.contexts[0].new_page() if browser.contexts else await browser.new_page()
            logger.info("[_pw_connect] Created new page")
        return page

    # ── Login ────────────────────────────────────────────────────────────

    async def _login(self, page: Page, email: str = "delqhi@gmx.de") -> bool:
        """Login to GMX via Playwright. Two-step flow: Email → Weiter → Password → Login."""
        logger.info(f"[_login] Logging in to GMX as {email}")
        try:
            await page.goto("https://www.gmx.net/", wait_until="domcontentloaded")
            await asyncio.sleep(5)
            url = page.url
            if "consent" in url:
                logger.info("Cookie consent page detected, accepting")
                for selector in ['button:has-text("Alle akzeptieren")', 'button:has-text("Zustimmen")', 
                                'button:has-text("Akzeptieren")', 'button:has-text("OK")',
                                'button[data-testid="uc-accept-all-button"]']:
                    btn = page.locator(selector).first
                    if await btn.is_visible(timeout=2000):
                        await btn.click()
                        logger.info(f"Clicked consent: {selector}")
                        await asyncio.sleep(3)
                        break
                url = page.url
                if "consent" in url:
                    await page.goto("https://www.gmx.net/", wait_until="domcontentloaded")
                    await asyncio.sleep(3)
                    url = page.url
            text = await page.evaluate("() => document.body.innerText")
            if "Sie sind eingeloggt" in text or "Zum Postfach" in text:
                logger.info("Detected logged-in state on homepage, clicking Zum Postfach")
                try:
                    postfach_link = page.locator('text=Zum Postfach').first
                    if await postfach_link.is_visible(timeout=3000):
                        await postfach_link.click()
                        await asyncio.sleep(5)
                        if "navigator.gmx.net/mail?sid=" in page.url:
                            return True
                        if "navigator.gmx.net" in page.url:
                            return True
                except Exception as e:
                    logger.warning(f"Zum Postfach click failed: {e}")
            email_input = page.locator('input[type="email"], input[name="username"], input[id="login-email"]').first
            if await email_input.is_visible(timeout=5000):
                await email_input.fill(email)
                await asyncio.sleep(0.5)
                weiter_btn = page.locator('button:has-text("Weiter")').first
                if await weiter_btn.is_visible(timeout=3000):
                    await weiter_btn.click()
                    await asyncio.sleep(3)
                else:
                    await email_input.press("Enter")
                    await asyncio.sleep(3)
            password_input = page.locator('input[type="password"]').first
            if await password_input.is_visible(timeout=8000):
                pw = self.password or ""
                await password_input.fill(pw)
                await asyncio.sleep(0.5)
                login_btn = page.locator('button:has-text("Login")').first
                if await login_btn.is_visible(timeout=3000):
                    await login_btn.click()
                else:
                    await password_input.press("Enter")
                await asyncio.sleep(5)
            current_url = page.url
            if "navigator.gmx.net/mail" in current_url or "bap.navigator.gmx.net/mail" in current_url:
                logger.info("Login successful")
                return True
            logger.error("Login failed — unexpected URL")
            return False
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False

    # ── Navigation to allEmailAddresses ────────────────────────────────────

    async def _navigate_to_all_email_addresses(self, page: Page) -> bool:
        """Navigate to GMX allEmailAddresses via direct 3c.gmx.net jump (v3 approach)."""
        url = page.url
        if "allEmailAddresses" in url and "settings" in url:
            logger.info("Already on allEmailAddresses (top frame)")
            return True
        sid = None
        sid_match = re.search(r'[?&]sid=([a-f0-9]{50,})', url)
        if sid_match:
            sid = sid_match.group(1)
        if not sid:
            for ctx in page.context.browser.contexts:
                for pg in ctx.pages:
                    m = re.search(r'[?&]sid=([a-f0-9]{50,})', pg.url)
                    if m and "gmx.net" in pg.url:
                        sid = m.group(1)
                        logger.info(f"Got SID from other tab: {pg.url[:60]}")
                        break
                if sid:
                    break
        if not sid:
            logger.info("No SID found, logging in")
            if not await self._login(page):
                return False
            sid_match = re.search(r'[?&]sid=([a-f0-9]{50,})', page.url)
            sid = sid_match.group(1) if sid_match else None
        if not sid:
            logger.error("Could not establish GMX session")
            return False
        logger.info(f"Got SID: {sid[:20]}...")
        jump_url = f"https://navigator.gmx.net/navigator/jump/to/mail_settings?sid={sid}"
        logger.info("STEP 1: Navigating to jump URL")
        await page.goto(jump_url, wait_until="domcontentloaded")
        await asyncio.sleep(6)
        url = page.url
        logger.info(f"After jump: {url[:100]}")
        if "allEmailAddresses" in url:
            logger.info("Redirected directly to allEmailAddresses (top frame)")
            return True
        if "settings" in url and "3c.gmx.net" in url:
            logger.info("STEP 2: On 3c.gmx.net settings — clicking E-Mail-Adressen via JS")
            try:
                result = await page.evaluate("""(function() {
                    var allEls = document.querySelectorAll('a, span, li, div, p');
                    for (var i = 0; i < allEls.length; i++) {
                        var el = allEls[i];
                        if (el.children.length === 0 && el.textContent.trim() === 'E-Mail-Adressen') {
                            var rect = el.getBoundingClientRect();
                            var cx = rect.x + rect.width / 2;
                            var cy = rect.y + rect.height / 2;
                            ['mousedown', 'mouseup', 'click'].forEach(function(evtType) {
                                el.dispatchEvent(new MouseEvent(evtType, {
                                    bubbles: true, cancelable: true, view: window,
                                    clientX: cx, clientY: cy
                                }));
                            });
                            return {clicked: true};
                        }
                    }
                    return {clicked: false};
                })()""")
                if result.get("clicked"):
                    logger.info("E-Mail-Adressen clicked via JS dispatchEvent")
                    await asyncio.sleep(4)
                else:
                    logger.warning("E-Mail-Adressen element not found on settings page")
            except Exception as e:
                logger.warning(f"E-Mail-Adressen JS click failed: {e}")
        url = page.url
        logger.info(f"Final URL: {url[:100]}")
        if "allEmailAddresses" in url and "settings" in url:
            logger.info("Successfully navigated to allEmailAddresses (top frame)")
            return True
        logger.info("STEP 3: Polling for allEmailAddresses")
        for poll in range(15):
            if "allEmailAddresses" in page.url and "settings" in page.url:
                return True
            await asyncio.sleep(1)
        logger.error("allEmailAddresses not found")
        return False

    # ── Alias Helpers ──────────────────────────────────────────────────────

    async def _get_all_email_frame(self, page: Page) -> Optional[Frame]:
        """Find the allEmailAddresses iframe, or return main_frame if in top frame."""
        if "allEmailAddresses" in page.url and "settings" in page.url:
            return page.main_frame
        for frame in page.frames:
            if "allEmailAddresses" in frame.url and "settings" in frame.url and "iac/restart" not in frame.url:
                return frame
        return None

    async def _find_alias_row(self, page: Page) -> Optional[str]:
        """Find a non-opensin alias email in the allEmailAddresses iframe."""
        logger.info("[_find_alias_row] Searching for alias")
        try:
            frame = await self._get_all_email_frame(page)
            if not frame:
                logger.warning("allEmailAddresses iframe not found")
                return None
            text = await frame.evaluate("() => document.body.innerText")
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if '@gmx.' in line and 'delqhi@gmx.de' not in line and 'opensin@gmx.de' not in line:
                    parts = line.split()
                    for part in parts:
                        if '@gmx.' in part and part != 'delqhi@gmx.de' and part != 'opensin@gmx.de':
                            logger.info(f"Found alias: {part}")
                            return part
            logger.info("No alias found")
            return None
        except Exception as e:
            logger.error(f"Error finding alias row: {e}")
            return None

    async def _fill_alias_input(self, page: Page, alias_name: str) -> bool:
        """Fill the alias input field in the allEmailAddresses iframe."""
        logger.info(f"[_fill_alias_input] Filling with {alias_name}")
        try:
            frame = await self._get_all_email_frame(page)
            if not frame:
                logger.warning("allEmailAddresses iframe not found")
                return False
            inp = frame.locator('input[name*="localPart"]').first
            if not await inp.is_visible(timeout=3000):
                inp = frame.locator('input[type="text"]').first
            if await inp.is_visible(timeout=3000):
                await inp.fill(alias_name)
                await inp.evaluate("el => el.dispatchEvent(new Event('input', {bubbles: true, composed: true}))")
                await inp.evaluate("el => el.dispatchEvent(new Event('change', {bubbles: true}))")
                value = await inp.input_value()
                if value == alias_name:
                    logger.info("Alias input filled successfully")
                    return True
            logger.warning("Alias input not found")
            return False
        except Exception as e:
            logger.error(f"Error filling alias input: {e}")
            return False

    async def _click_add_button(self, page: Page) -> bool:
        """Click the add alias button via CDP native events (Wicket-kompatibel)."""
        logger.info("[_click_add_button] Looking for add button")
        try:
            frame = await self._get_all_email_frame(page)
            if not frame:
                logger.warning("allEmailAddresses iframe not found")
                return False
            btn = frame.locator('button:has-text("Hinzufügen")').first
            bb = await btn.bounding_box()
            if bb:
                cx = bb['x'] + bb['width'] / 2
                cy = bb['y'] + bb['height'] / 2
                cdp = await page.context.new_cdp_session(page)
                await cdp.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": cx, "y": cy})
                await asyncio.sleep(0.1)
                await cdp.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": cx, "y": cy, "button": "left", "clickCount": 1})
                await asyncio.sleep(0.1)
                await cdp.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": cx, "y": cy, "button": "left", "clickCount": 1})
                await asyncio.sleep(2)
                logger.info("Hinzufügen button clicked via CDP")
                try: await cdp.detach()
                except: pass
                return True
            result = await frame.evaluate("""(function() {
                var btns = document.querySelectorAll('button');
                for (var i = 0; i < btns.length; i++) {
                    if (btns[i].textContent.indexOf('Hinzuf') >= 0) {
                        btns[i].click();
                        return true;
                    }
                }
                return false;
            })()""")
            if result:
                logger.info("Hinzufügen button clicked via JS")
                await asyncio.sleep(2)
                return True
            logger.warning("Add button not found")
            return False
        except Exception as e:
            logger.error(f"Error clicking add button: {e}")
            return False

    async def _verify_alias(self, page: Page, alias_email: str, present: bool = True, max_wait: float = 12.0) -> bool:
        """Verify alias is present/absent."""
        logger.info(f"[_verify_alias] Checking {alias_email} expect_present={present}")
        try:
            deadline = time.time() + max_wait
            while time.time() < deadline:
                frame = await self._get_all_email_frame(page)
                if frame:
                    text = await frame.evaluate("() => document.body.innerText")
                    found = alias_email in text
                    if present and found:
                        logger.info(f"[_verify_alias] FOUND {alias_email} as expected")
                        return True
                    if not present and not found:
                        logger.info(f"[_verify_alias] {alias_email} gone as expected")
                        return True
                else:
                    for f in page.frames:
                        if "allEmailAddresses" in f.url and "settings" in f.url:
                            text = await f.evaluate("() => document.body.innerText")
                            found = alias_email in text
                            if present and found:
                                return True
                            if not present and not found:
                                return True
                            break
                await asyncio.sleep(1)
            logger.warning(f"[_verify_alias] TIMEOUT expect_present={present}")
            return False
        except Exception as e:
            logger.error(f"Error verifying alias: {e}")
            return False

    async def _delete_alias(self, page: Page, alias_email: str) -> bool:
        """Delete an alias via CDP Input.dispatchMouseEvent (Wicket-kompatibel)."""
        logger.info(f"[_delete_alias] Deleting {alias_email}")
        try:
            frame = await self._get_all_email_frame(page)
            if not frame:
                logger.warning("allEmailAddresses iframe not found for delete")
                return False
            row_data = await frame.evaluate(f"""() => {{
                var rows = document.querySelectorAll('tr, li, .row, [class*="row"]');
                for (var i=0; i<rows.length; i++) {{
                    if (rows[i].textContent.includes('{alias_email}')) {{
                        var r = rows[i].getBoundingClientRect();
                        if (r.width > 20 && r.height > 5) {{
                            return {{
                                cx: Math.round(r.x + r.width/2),
                                cy: Math.round(r.y + r.height/2)
                            }};
                        }}
                    }}
                }}
                return null;
            }}""")
            if not row_data:
                logger.warning(f"Alias row not found: {alias_email}")
                return False
            cdp = await page.context.new_cdp_session(page)
            logger.info(f"Hover row via CDP at ({row_data['cx']}, {row_data['cy']})")
            await cdp.send('Input.dispatchMouseEvent', {
                'type': 'mouseMoved', 'x': row_data['cx'], 'y': row_data['cy']
            })
            await asyncio.sleep(1.5)
            delete_pos = await frame.evaluate("""() => {
                var delLinks = document.querySelectorAll('a.table-hover_icon[title*="löschen"], a.table-hover_icon[title*="Löschen"]');
                for (var i = 0; i < delLinks.length; i++) {
                    var el = delLinks[i];
                    var r = el.getBoundingClientRect();
                    if (r.width > 5 && r.height > 5) {
                        return {
                            x: Math.round(r.x + r.width/2),
                            y: Math.round(r.y + r.height/2),
                            title: el.getAttribute('title') || ''
                        };
                    }
                }
                return null;
            }""")
            if not delete_pos:
                logger.warning("Delete icon not found via .table-hover_icon selector — retrying with broader search")
                delete_pos = await frame.evaluate("""() => {
                    var allLinks = document.querySelectorAll('a');
                    for (var i = 0; i < allLinks.length; i++) {
                        var el = allLinks[i];
                        var title = (el.getAttribute('title') || '').toLowerCase();
                        var aria = (el.getAttribute('aria-label') || '').toLowerCase();
                        if (title.indexOf('lösch') !== -1 || aria.indexOf('lösch') !== -1) {
                            var r = el.getBoundingClientRect();
                            if (r.width > 5 && r.height > 5) {
                                return {
                                    x: Math.round(r.x + r.width/2),
                                    y: Math.round(r.y + r.height/2),
                                    title: el.getAttribute('title') || ''
                                };
                            }
                        }
                    }
                    return null;
                }""")
                if not delete_pos:
                    logger.warning("Delete icon not found globally either")
                    return False
            logger.info(f"Delete '{delete_pos.get('title', '')}' at ({delete_pos['x']}, {delete_pos['y']})")
            await cdp.send('Input.dispatchMouseEvent', {
                'type': 'mousePressed', 'x': delete_pos['x'], 'y': delete_pos['y'],
                'button': 'left', 'clickCount': 1
            })
            await asyncio.sleep(0.05)
            await cdp.send('Input.dispatchMouseEvent', {
                'type': 'mouseReleased', 'x': delete_pos['x'], 'y': delete_pos['y'],
                'button': 'left', 'clickCount': 1
            })
            await asyncio.sleep(3)
            ok_pos = None
            for try_frame in [frame] + [f for f in page.frames if f is not frame]:
                try:
                    ok_pos = await try_frame.evaluate("""() => {
                        var allEls = document.querySelectorAll('button, a, span, div[role="button"], div[role="link"]');
                        var classEls = document.querySelectorAll('.btn-primary, .confirm-button, [data-testid*="confirm"]');
                        var all = Array.from(allEls).concat(Array.from(classEls));
                        for (var i = 0; i < all.length; i++) {
                            var el = all[i];
                            if (!el) continue;
                            var txt = (el.textContent || '').trim();
                            if (txt === 'OK' || txt === 'Ok' || txt === 'ok' ||
                                (txt.length > 0 && txt.length < 20 && txt.toLowerCase() === 'ok')) {
                                var r = el.getBoundingClientRect();
                                if (r.width > 5 && r.height > 5) {
                                    return {
                                        x: Math.round(r.x + r.width/2),
                                        y: Math.round(r.y + r.height/2),
                                        text: txt,
                                        frame: window === window.top ? 'top' : 'iframe'
                                    };
                                }
                            }
                        }
                        return null;
                    }""")
                    if ok_pos:
                        logger.info(f"OK confirm at ({ok_pos['x']}, {ok_pos['y']}) in {ok_pos.get('frame','?')}, text='{ok_pos.get('text','')}'")
                        break
                except Exception as e:
                    logger.debug(f"OK button search in frame failed: {e}")
                    continue
            if ok_pos:
                await cdp.send('Input.dispatchMouseEvent', {
                    'type': 'mousePressed', 'x': ok_pos['x'], 'y': ok_pos['y'],
                    'button': 'left', 'clickCount': 1
                })
                await asyncio.sleep(0.05)
                await cdp.send('Input.dispatchMouseEvent', {
                    'type': 'mouseReleased', 'x': ok_pos['x'], 'y': ok_pos['y'],
                    'button': 'left', 'clickCount': 1
                })
                await asyncio.sleep(2)
            else:
                logger.warning("OK confirm button NOT FOUND")
            for _ in range(10):
                text = await frame.evaluate("() => document.body.innerText")
                if alias_email not in text:
                    logger.info("Alias deleted successfully")
                    return True
                await asyncio.sleep(1)
            logger.warning("Alias still present after delete attempt")
            return False
        except Exception as e:
            logger.error(f"Error deleting alias: {e}")
            import traceback
            traceback.print_exc()
            return False

    # ── Alias Rotation ────────────────────────────────────────────────────

    async def rotate_alias(self, new_alias_name: Optional[str] = None, cdp_port: int = 9222, page: Optional[Page] = None) -> Dict[str, Any]:
        start_time = time.time()
        steps = []
        deleted_alias = None
        created_alias = None
        try:
            page = await self._pw_connect(cdp_port, page=page)
            if not await self._navigate_to_all_email_addresses(page):
                return {"status": "failed", "deleted_alias": None, "created_alias": None,
                        "error": "Navigation fehlgeschlagen", "execution_time": f"{time.time()-start_time:.2f}s"}
            steps.append("navigated")
            alias_email = await self._find_alias_row(page)
            if alias_email:
                logger.info(f"Found alias to delete: {alias_email}")
                if await self._delete_alias(page, alias_email):
                    deleted_alias = alias_email
                    steps.append("deleted")
                    await asyncio.sleep(3)
                else:
                    logger.warning("Failed to delete alias, continuing")
            else:
                steps.append("no_alias_to_delete")
            if not new_alias_name:
                new_alias_name = self.generate_alias_name()
            for attempt in range(3):
                current_alias = new_alias_name if attempt == 0 else self.generate_alias_name()
                alias_email = f"{current_alias}@gmx.de"
                logger.info(f"Creating alias (attempt {attempt+1}/3): {alias_email}")
                if await self._fill_alias_input(page, current_alias):
                    await asyncio.sleep(1)
                    if await self._click_add_button(page):
                        await asyncio.sleep(3)
                        if await self._verify_alias(page, alias_email, present=True):
                            created_alias = alias_email
                            steps.append("created")
                            break
                await asyncio.sleep(1)
            if created_alias:
                return {"status": "success", "deleted_alias": deleted_alias, "created_alias": created_alias,
                        "steps": steps, "execution_time": f"{time.time()-start_time:.2f}s"}
            return {"status": "failed", "deleted_alias": deleted_alias, "created_alias": None,
                    "error": "Erstellung fehlgeschlagen", "steps": steps, "execution_time": f"{time.time()-start_time:.2f}s"}
        except Exception as e:
            logger.error(f"Rotation fehlgeschlagen: {e}")
            return {"status": "failed", "error": str(e), "steps": steps, "execution_time": f"{time.time()-start_time:.2f}s"}

    # ── OTP / Vercel Code ─────────────────────────────────────────────────
    # Adapted from read_otp_main_frame_only and read_otp_cdp_axtree for Vercel 6-digit numeric codes

    async def read_otp_main_frame_only(self, sender_keyword: str = "vercel", timeout: int = 120) -> Dict[str, Any]:
        """OTP-Suche mit Shadow DOM Traversal (nur main + mail frame) für Vercel.
        Sucht 6-stellige numerische Codes in Vercel-Emails.
        """
        if self.inbox_tab is None:
            logger.error("inbox_tab nicht initialisiert")
            return {"status": "error", "otp_url": None, "error": "inbox_tab missing"}

        logger.info(f"[Main-Frame-OTP] Start (Keyword: {sender_keyword}, timeout: {timeout}s)")
        # Vercel OTP pattern: 6-digit numeric code
        pattern_otp = re.compile(r"\b\d{6}\b")
        # Vercel subject pattern: "965786 is your Vercel sign up code"
        pattern_subject = re.compile(r"(\d{6}) is your Vercel sign up code", re.IGNORECASE)

        scan_js = r"""
        (SENDER) => {
            let out = [];
            function walk(root) {
                let nodes;
                try { nodes = root.querySelectorAll('*'); } catch (e) { return; }
                for (const el of nodes) {
                    const tag = (el.tagName || '').toLowerCase();
                    if (tag === 'list-mail-item') {
                        const txt = (el.innerText || el.textContent || '');
                        if (txt.toLowerCase().includes(SENDER.toLowerCase())) {
                            out.push({text: txt.trim().slice(0, 400)});
                        }
                    }
                    if (el.shadowRoot) walk(el.shadowRoot);
                }
            }
            if (document.body) walk(document.body);
            return out;
        }
        """

        start_time = time.time()
        deadline = start_time + timeout

        while time.time() < deadline:
            try:
                frames_to_scan = [self.inbox_tab.main_frame]
                for f in self.inbox_tab.frames:
                    if f.name == "mail":
                        frames_to_scan.append(f)
                        break

                for frame in frames_to_scan:
                    try:
                        items = await frame.evaluate(scan_js, sender_keyword.lower())
                        logger.debug(f"[Main-Frame-OTP] Frame scan: {frame.name or '?'} -> {len(items)} items")
                        if items:
                            # Check if any list item already has the OTP code in preview text
                            for item in items:
                                text = item.get('text', '')
                                subject_match = pattern_subject.search(text)
                                if subject_match:
                                    otp = subject_match.group(1)
                                    elapsed = time.time() - start_time
                                    logger.info(f"[Main-Frame-OTP] OTP found in preview after {elapsed:.1f}s: {otp}")
                                    return {"status": "success", "otp_url": None, "otp_code": otp,
                                            "execution_time": f"{elapsed:.2f}s"}
                                # Fallback: any 6-digit code near Vercel
                                otp_match = pattern_otp.search(text)
                                if otp_match:
                                    elapsed = time.time() - start_time
                                    logger.info(f"[Main-Frame-OTP] OTP found in preview (fallback) after {elapsed:.1f}s: {otp_match.group(0)}")
                                    return {"status": "success", "otp_url": None, "otp_code": otp_match.group(0),
                                            "execution_time": f"{elapsed:.2f}s"}
                            # OTP not in list — click first matching email to open it
                            logger.info(f"[Main-Frame-OTP] Clicking first matching email ({len(items)} items)")
                            clicked = await frame.evaluate("(nth) => { function walk(r) { let n=0; try { var els=r.querySelectorAll('*'); } catch(e){return false; } for(var e of els){ if((e.tagName||'').toLowerCase()==='list-mail-item') { if(n++===nth) { e.click(); return true; } } if(e.shadowRoot && walk(e.shadowRoot)) return true; } return false; } return walk(document.body); }", 0)
                            if clicked:
                                await asyncio.sleep(3)
                                # Scan ALL frames for the OTP in the opened email body
                                for sf in self.inbox_tab.frames:
                                    try:
                                        body_text = await sf.evaluate("() => document.body ? document.body.innerText.substring(0,10000) : ''")
                                        subject_match = pattern_subject.search(body_text)
                                        if subject_match:
                                            otp = subject_match.group(1)
                                            elapsed = time.time() - start_time
                                            logger.info(f"[Main-Frame-OTP] OTP found in frame '{sf.name}' after {elapsed:.1f}s: {otp}")
                                            return {"status": "success", "otp_url": None, "otp_code": otp,
                                                    "execution_time": f"{elapsed:.2f}s"}
                                        otp_match = pattern_otp.findall(body_text)
                                        # Filter to 6-digit sequences that look like OTP (not dates, etc.)
                                        for code in otp_match:
                                            if len(code) == 6 and code.isdigit():
                                                elapsed = time.time() - start_time
                                                logger.info(f"[Main-Frame-OTP] OTP found in frame '{sf.name}' (fallback) after {elapsed:.1f}s: {code}")
                                                return {"status": "success", "otp_url": None, "otp_code": code,
                                                        "execution_time": f"{elapsed:.2f}s"}
                                    except Exception:
                                        continue
                    except Exception:
                        continue

                elapsed = time.time() - start_time
                remaining = deadline - time.time()
                sleep_t = min(5, remaining) if remaining > 0 else 0
                if sleep_t > 0:
                    logger.info(f"[Main-Frame-OTP] No mail yet. Waiting {sleep_t:.0f}s... (elapsed: {elapsed:.0f}s)")
                    await asyncio.sleep(sleep_t)
            except Exception as e:
                logger.warning(f"[Main-Frame-OTP] Poll error: {e}")
                await asyncio.sleep(3)

        logger.warning("[Main-Frame-OTP] Timeout")
        return {"status": "not_found", "otp_url": None, "otp_code": None, "error": "Timeout"}

    async def read_otp_cdp_axtree(self, sender_keyword: str = "vercel", timeout: int = 180) -> Dict[str, Any]:
        """BULLETPROOF OTP via CDP Accessibility Tree für Vercel.
        Sucht 6-stellige numerische Codes in Vercel-Emails.
        """
        if self.inbox_tab is None:
            logger.error("inbox_tab nicht initialisiert")
            return {"status": "error", "otp_url": None, "error": "inbox_tab missing"}

        logger.info(f"[CDP-AXTree] Starte OTP-Suche (Keyword: {sender_keyword}, timeout: {timeout}s)")
        pattern_otp = re.compile(r"\b\d{6}\b")
        pattern_subject = re.compile(r"(\d{6}) is your Vercel sign up code", re.IGNORECASE)

        cdp = None
        start_time = time.time()
        try:
            cdp = await self.inbox_tab.context.new_cdp_session(self.inbox_tab)
            await cdp.send("Accessibility.enable")
            logger.info("[CDP-AXTree] CDP session erstellt")

            deadline = start_time + timeout
            while time.time() < deadline:
                try:
                    tree_result = await cdp.send("Accessibility.getFullAXTree", {"pierce": True})
                    nodes = tree_result.get("nodes", [])
                    logger.debug(f"[CDP-AXTree] {len(nodes)} AXTree nodes gescannt, URL: {self.inbox_tab.url[:60]}")

                    current_url = self.inbox_tab.url or ""
                    is_on_inbox = "navigator.gmx.net/mail" in current_url or "bap.navigator.gmx.net/mail" in current_url

                    if len(nodes) < 20 or not is_on_inbox or "logoutlounge" in current_url:
                        session_keywords = ["sitzung", "wiederhergestellt", "cookies", "loading", "bitte warten", "wird geladen"]
                        sample_text = " ".join(
                            f"{(n.get('name') or {}).get('value', '')} {(n.get('description') or {}).get('value', '')}"
                            for n in nodes[:15]
                        ).lower()
                        has_session_msg = any(kw in sample_text for kw in session_keywords)
                        if has_session_msg or len(nodes) < 20 or "logoutlounge" in current_url:
                            logger.warning(f"[CDP-AXTree] GMX Session/Loading-Seite erkannt (nodes={len(nodes)}, inbox={is_on_inbox}, url={current_url[:60]}) — lade neu...")
                            try:
                                await self.inbox_tab.reload(wait_until="domcontentloaded", timeout=15000)
                                await asyncio.sleep(5)
                                logger.info("[CDP-AXTree] Page reloaded, continue polling")
                                continue
                            except Exception as reload_err:
                                logger.warning(f"[CDP-AXTree] Reload failed: {reload_err}")
                                try:
                                    await self.inbox_tab.goto(current_url, wait_until="domcontentloaded", timeout=15000)
                                    await asyncio.sleep(5)
                                except Exception:
                                    pass
                                continue

                    full_text = ""
                    vercel_found = False

                    for node in nodes:
                        name_val = (node.get("name") or {}).get("value", "")
                        desc_val = (node.get("description") or {}).get("value", "")
                        val_val = (node.get("value") or {}).get("value", "")
                        node_text = f"{name_val} {desc_val} {val_val}"
                        node_lower = node_text.lower()

                        if sender_keyword.lower() in node_lower:
                            vercel_found = True
                            full_text += " " + node_text

                            subject_match = pattern_subject.search(node_text)
                            if subject_match:
                                elapsed = time.time() - start_time
                                logger.info(f"[CDP-AXTree] OTP gefunden nach {elapsed:.1f}s: {subject_match.group(1)}")
                                return {
                                    "status": "success",
                                    "otp_url": None,
                                    "otp_code": subject_match.group(1),
                                    "execution_time": f"{elapsed:.2f}s",
                                }

                    if vercel_found:
                        otp_match = pattern_otp.search(full_text)
                        if otp_match:
                            elapsed = time.time() - start_time
                            logger.info(f"[CDP-AXTree] OTP (fallback) gefunden nach {elapsed:.1f}s: {otp_match.group(0)}")
                            return {
                                "status": "success",
                                "otp_url": None,
                                "otp_code": otp_match.group(0),
                                "execution_time": f"{elapsed:.2f}s",
                            }

                    elapsed = time.time() - start_time
                    remaining = deadline - time.time()
                    sleep_t = min(8, remaining) if remaining > 0 else 0
                    if sleep_t > 0:
                        logger.info(f"[CDP-AXTree] Mail nicht da. Warte {sleep_t:.0f}s... (elapsed: {elapsed:.0f}s)")
                        await asyncio.sleep(sleep_t)

                except Exception as e:
                    logger.warning(f"[CDP-AXTree] Scan error: {e}")
                    await asyncio.sleep(5)

            logger.warning("[CDP-AXTree] Timeout")
            return {"status": "not_found", "otp_url": None, "otp_code": None, "error": "Timeout"}
        except Exception as e:
            logger.error(f"[CDP-AXTree] CDP session error: {e}")
            return {"status": "error", "otp_url": None, "error": str(e)}
        finally:
            if cdp:
                try:
                    await cdp.detach()
                except Exception:
                    pass

    async def read_otp(self, sender_filter: str = "vercel", max_retries: int = 12, retry_delay: int = 5, cdp_port: int = 9222) -> Dict[str, Any]:
        """High-level OTP reader — tries main_frame first, falls back to CDP AXTree."""
        start_time = time.time()
        result = await self.read_otp_main_frame_only(sender_keyword=sender_filter, timeout=80)
        if result.get("status") == "success":
            return result
        logger.info("Main frame OTP failed, trying CDP AXTree fallback...")
        result = await self.read_otp_cdp_axtree(sender_keyword=sender_filter, timeout=100)
        return result


_gmx_service: Optional[GmxService] = None


def get_gmx_service(browser: Optional[Browser] = None, context: Optional[BrowserContext] = None, password: Optional[str] = None) -> GmxService:
    global _gmx_service
    if _gmx_service is None:
        _gmx_service = GmxService(browser=browser, context=context, password=password)
    return _gmx_service
