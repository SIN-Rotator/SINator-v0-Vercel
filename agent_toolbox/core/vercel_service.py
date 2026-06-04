"""
SINator v0+Vercel — Vercel Signup Service (sin-browser-tools)
Docs: vercel_service.doc.md

Vercel/v0.dev Account-Erstellung via Referral-Link mit sin-browser-tools.
Flow:
  1. Referral-Link öffnen (v0.app/ref/6IMSRI)
  2. Cookie-Banner handhaben
  3. Email-Alias eingeben → "Continue with Email"
  4. GMX-OTP (6-stellig numerisch) abfragen und eingeben
  5. Passwort setzen
  6. Telefon-Verifizierung via SMSPool (UK-Nummer)
  7. Dashboard → API-Token generieren und extrahieren

Uses sin-browser-tools for ALL browser interactions.
"""
import time
import secrets
import logging
import asyncio
import re
from typing import Optional, Dict, Any

from sin_browser_tools.core.manager import BrowserManager
from sin_browser_tools.tools.navigation import manager as nav_mgr, browser_navigate, browser_new_tab, browser_get_url, browser_wait_for_text, browser_wait_for_load, browser_wait_for_spa_transition, browser_press
from sin_browser_tools.tools.interaction import browser_fill_react, browser_click_by_text, browser_click_checkbox_by_text, browser_type, browser_click_cdp
from sin_browser_tools.tools.vision import browser_screenshot
from sin_browser_tools.tools.extraction import browser_get_html, browser_console
from sin_browser_tools.tools.diagnostics import browser_diag_action, browser_diag_snapshot_all

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setLevel(logging.DEBUG)
    _formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    _handler.setFormatter(_formatter)
    logger.addHandler(_handler)

REFERRAL_URL = "https://v0.app/ref/6IMSRI"
VERCEL_SIGNUP_URL = "https://vercel.com/signup"
VERCEL_TOKENS_URL = "https://vercel.com/account/tokens"


class VercelService:
    def __init__(self, manager: Optional[BrowserManager] = None):
        self.manager = manager
        if manager:
            nav_mgr._set_instance(manager)

    # ── Internal Helpers ─────────────────────────────────────────────────

    async def _screenshot(self, name: str) -> str:
        """Take a debug screenshot and save to /tmp."""
        try:
            ss = await browser_screenshot(full_page=True)
            if ss.get("image_data"):
                import pathlib
                p = pathlib.Path(f"/tmp/vercel_{name}_{int(time.time())}.png")
                p.write_bytes(ss["image_data"])
                return str(p)
        except Exception as e:
            logger.warning(f"Screenshot failed: {e}")
        return ""

    async def _diag(self) -> Dict[str, Any]:
        """Run diagnostics snapshot for debugging."""
        try:
            return await browser_diag_snapshot_all()
        except Exception as e:
            logger.warning(f"Diag failed: {e}")
            return {}

    async def _get_body_text(self) -> str:
        """Get current page body text via JS."""
        try:
            html = await browser_get_html()
            # Simple tag stripping for quick text extraction
            text = re.sub(r'<[^>]+>', ' ', str(html))
            return text
        except Exception as e:
            logger.warning(f"get_body_text failed: {e}")
            return ""

    async def _eval(self, js: str) -> Any:
        """Execute JS via browser_console — extracts actual value from CDP Runtime.evaluate result."""
        try:
            result = await browser_console(js)
            # browser_console returns CDP Runtime.evaluate dict: {"result": value, "type": ...}
            if isinstance(result, dict) and "result" in result:
                return result["result"]
            return result
        except Exception as e:
            logger.warning(f"JS eval failed: {e}")
            return None

    # ── Cookie Banner ────────────────────────────────────────────────────

    async def _handle_cookie_banner(self) -> bool:
        """Handle Vercel cookie consent banner: click Deny or Accept all.

        Tries text-based click first (with and without role filter), then
        aggressive JS removal to ensure the banner never blocks form fields.
        """
        logger.info("[CookieBanner] Checking for cookie banner...")
        clicked = False
        # Phase 1: try clicking known labels (with role="button" first)
        for role in ["button", None]:
            for text in ["Deny", "Decline", "Ablehnen", "Reject all", "Only necessary",
                         "Accept all", "Alle akzeptieren", "Accept", "Zustimmen"]:
                try:
                    kwargs = {"exact": False}
                    if role:
                        kwargs["role"] = role
                    await browser_click_by_text(text, **kwargs)
                    logger.info(f"[CookieBanner] Clicked '{text}' (role={role})")
                    clicked = True
                    break
                except Exception:
                    continue
            if clicked:
                break

        # Phase 2: aggressive JS removal (always run, removes banners + restores scroll)
        removal_js = """(() => {
            const selectors = [
                '.cky-overlay', '.cky-consent-container', '.cky-modal', '.cky-preference-center',
                '[data-testid*="cookie"]', '[class*="cookie"]', '[id*="cookie"]',
                '[class*="consent"]', '[id*="consent"]', '[class*="CookieYes"]',
                '.osano-cm-window', '#onetrust-banner-sdk', '.cookie-modal'
            ];
            selectors.forEach(sel => document.querySelectorAll(sel).forEach(el => el.remove()));
            document.body.style.overflow = 'visible';
            document.body.style.position = 'static';
        })()"""
        try:
            await browser_console(removal_js)
            logger.info("[CookieBanner] Aggressive JS removal executed")
        except Exception as e:
            logger.warning(f"[CookieBanner] JS removal failed: {e}")

        await asyncio.sleep(0.5)
        return True

    # ── Signup Flow ──────────────────────────────────────────────────────

    async def signup(self, alias_email: str, otp_code: str, smspool_service=None, password: Optional[str] = None) -> Dict[str, Any]:
        """Complete Vercel signup flow from referral link to API key extraction.

        Args:
            alias_email: GMX alias email (e.g. "swift-lynx-612@gmx.de")
            otp_code: 6-digit Vercel OTP from GMX
            smspool_service: SMSPoolService instance for phone verification
            password: Optional password to set (generated if not provided)

        Returns:
            Dict with keys: status, api_key, account_email, execution_time, screenshots
        """
        start_time = time.time()
        steps = []
        screenshots = []

        if not password:
            password = self._generate_password()

        try:
            # Step 1: Open referral link
            logger.info("[Signup] Step 1: Navigate to referral link")
            await browser_navigate(REFERRAL_URL)
            await asyncio.sleep(5)
            steps.append("navigated_referral")
            screenshots.append(await self._screenshot("01_referral"))

            # Handle cookie banner
            await self._handle_cookie_banner()
            await asyncio.sleep(1)

            # Step 2: Fill email
            logger.info(f"[Signup] Step 2: Fill email {alias_email}")
            # Vercel signup page may redirect; wait for email field
            await self._wait_for_email_field(timeout=15)

            fill_result = await browser_fill_react('input[type="email"]', alias_email)
            if not fill_result.get("success"):
                logger.warning(f"[Signup] browser_fill_react failed: {fill_result.get('error')} — falling back to browser_type")
                await browser_type('input[type="email"]', alias_email, delay_ms=30)
            await asyncio.sleep(0.5)

            # Verify field contains the alias (React sometimes reverts)
            email_val = await self._eval("document.querySelector('input[type=email], input[name=email]')?.value")
            if not email_val or alias_email not in str(email_val):
                logger.error(f"[Signup] Email field empty after fill! value='{email_val}' — retrying with browser_type")
                await browser_type('input[type="email"]', alias_email, delay_ms=30)
                await asyncio.sleep(0.5)

            steps.append("filled_email")
            screenshots.append(await self._screenshot("02_email"))

            # Step 3: Click "Continue with Email"
            logger.info("[Signup] Step 3: Click Continue with Email")
            try:
                await asyncio.wait_for(browser_click_by_text("Continue with Email", role="button", exact=False), timeout=15)
            except Exception as e:
                logger.warning(f"[Signup] 'Continue with Email' click failed: {e}")
                # Fallback: generic Continue or Enter
                try:
                    await asyncio.wait_for(browser_click_by_text("Continue", role="button", exact=False), timeout=10)
                except Exception:
                    await browser_press("Enter")
            await asyncio.sleep(3)
            steps.append("clicked_continue_email")

            # Step 4: Enter OTP
            logger.info(f"[Signup] Step 4: Enter OTP {otp_code}")
            otp_filled = await self._fill_otp(otp_code, timeout=15)
            if not otp_filled:
                logger.error("[Signup] OTP field not found")
                return {"status": "failed", "error": "OTP field not found", "steps": steps, "screenshots": screenshots,
                        "execution_time": f"{time.time()-start_time:.2f}s"}
            steps.append("filled_otp")

            # Click Continue after OTP
            try:
                await asyncio.wait_for(browser_click_by_text("Continue", role="button", exact=False), timeout=15)
            except Exception:
                await browser_press("Enter")
            await asyncio.sleep(3)

            # Step 5: Handle password creation (if prompted)
            logger.info("[Signup] Step 5: Check for password field")
            pwd_result = await self._handle_password(password, timeout=15)
            if pwd_result:
                steps.append("set_password")

            # Step 6: Handle phone verification via SMSPool (if prompted)
            logger.info("[Signup] Step 6: Check for phone verification")
            if smspool_service:
                phone_result = await self._handle_phone_verification(smspool_service, timeout=60)
                if phone_result:
                    steps.append("phone_verified")
            else:
                logger.info("[Signup] No SMSPool service provided, skipping phone verification")

            # Step 7: Wait for dashboard / home
            logger.info("[Signup] Step 7: Wait for dashboard")
            dashboard_ok = await self._wait_for_dashboard(timeout=30)
            if not dashboard_ok:
                logger.warning("[Signup] Dashboard not detected, continuing anyway")
            steps.append("dashboard")

            # Step 8: Generate API token
            logger.info("[Signup] Step 8: Generate API token")
            api_key = await self._generate_api_token(alias_email=alias_email, password=password or "")
            if api_key:
                steps.append("api_key_generated")
                screenshots.append(await self._screenshot("08_api_key"))
                return {
                    "status": "success",
                    "api_key": api_key,
                    "account_email": alias_email,
                    "password": password,
                    "steps": steps,
                    "screenshots": screenshots,
                    "execution_time": f"{time.time()-start_time:.2f}s"
                }
            else:
                steps.append("api_key_failed")
                return {
                    "status": "partial",
                    "error": "API key generation failed",
                    "account_email": alias_email,
                    "password": password,
                    "steps": steps,
                    "screenshots": screenshots,
                    "execution_time": f"{time.time()-start_time:.2f}s"
                }

        except Exception as e:
            logger.error(f"[Signup] Fatal error: {e}")
            import traceback
            traceback.print_exc()
            screenshots.append(await self._screenshot("99_error"))
            return {"status": "failed", "error": str(e), "steps": steps, "screenshots": screenshots,
                    "execution_time": f"{time.time()-start_time:.2f}s"}

    # ── Step Helpers ───────────────────────────────────────────────────────

    async def _wait_for_email_field(self, timeout: float = 15) -> bool:
        """Wait for email input field to appear."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                html = await browser_get_html()
                if 'type="email"' in str(html).lower() or 'name="email"' in str(html).lower():
                    return True
            except Exception:
                pass
            await asyncio.sleep(1)
        return False

    async def _fill_otp(self, otp_code: str, timeout: float = 15) -> bool:
        """Find and fill OTP field (6-digit code)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                # Try various OTP input selectors
                selectors = [
                    'input[data-testid="otp-input"]',
                    'input[name="code"]',
                    'input[name="otp"]',
                    'input[type="text"][maxlength="6"]',
                    'input[inputmode="numeric"]',
                    'input[autocomplete="one-time-code"]',
                ]
                for sel in selectors:
                    try:
                        await browser_fill_react(sel, otp_code)
                        logger.info(f"[OTP] Filled OTP via selector: {sel}")
                        return True
                    except Exception:
                        continue
                # Fallback: type into focused element or first text input
                try:
                    await browser_type('input[type="text"]', otp_code)
                    return True
                except Exception:
                    pass
            except Exception:
                pass
            await asyncio.sleep(1)
        return False

    async def _handle_password(self, password: str, timeout: float = 15) -> bool:
        """Check for and fill password fields if present."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                html = await browser_get_html()
                html_str = str(html).lower()
                has_password = 'type="password"' in html_str or 'password' in html_str
                if not has_password:
                    await asyncio.sleep(1)
                    continue
                # Fill password
                await browser_fill_react('input[type="password"]', password)
                await asyncio.sleep(0.5)
                # Look for confirm password
                try:
                    pwd_inputs = await browser_console("() => document.querySelectorAll('input[type=\"password\"]').length")
                    if pwd_inputs and int(pwd_inputs) >= 2:
                        # Fill second password field (confirm)
                        await browser_console(f"""(() => {{
                            var inps = document.querySelectorAll('input[type="password"]');
                            if (inps.length >= 2) {{
                                var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                                setter.call(inps[1], '{password}');
                                inps[1].dispatchEvent(new Event('input', {{bubbles: true}}));
                                inps[1].dispatchEvent(new Event('change', {{bubbles: true}}));
                            }}
                        }})()""")
                except Exception:
                    pass
                # Submit
                try:
                    await browser_click_by_text("Continue", role="button", exact=False)
                except Exception:
                    await browser_press("Enter")
                await asyncio.sleep(5)
                return True
            except Exception:
                pass
            await asyncio.sleep(1)
        return False

    async def _handle_phone_verification(self, smspool_service, timeout: float = 60) -> bool:
        """Handle phone verification using SMSPool UK number."""
        deadline = time.time() + timeout
        phone_order = None
        while time.time() < deadline:
            try:
                html = await browser_get_html()
                html_str = str(html).lower()
                has_phone = (
                    'type="tel"' in html_str or
                    'phone' in html_str or
                    'mobile' in html_str or
                    'number' in html_str
                )
                if not has_phone:
                    # Also check for text mentioning phone
                    body = await self._get_body_text()
                    if 'phone' not in body.lower() and 'mobile' not in body.lower() and 'number' not in body.lower():
                        await asyncio.sleep(1)
                        continue

                # Get UK number from SMSPool
                if phone_order is None:
                    logger.info("[Phone] Ordering UK number from SMSPool...")
                    phone_order = await smspool_service.order_uk_number()
                    if not phone_order:
                        logger.error("[Phone] Failed to order UK number")
                        return False
                    phone_number = phone_order.get("number")
                    order_id = phone_order.get("order_id")
                    logger.info(f"[Phone] Got UK number: {phone_number}, order_id: {order_id}")

                # Fill phone number
                try:
                    await browser_fill_react('input[type="tel"]', phone_number)
                except Exception:
                    try:
                        await browser_type('input[type="tel"]', phone_number)
                    except Exception:
                        await browser_console(f"""(() => {{
                            var inp = document.querySelector('input[type="tel"], input[name="phone"], input[name="mobile"]');
                            if (inp) {{
                                var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                                setter.call(inp, '{phone_number}');
                                inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                            }}
                        }})()""")
                await asyncio.sleep(1)

                # Click send/verify to trigger SMS
                try:
                    await browser_click_by_text("Send", role="button", exact=False)
                except Exception:
                    try:
                        await browser_click_by_text("Verify", role="button", exact=False)
                    except Exception:
                        await browser_press("Enter")
                await asyncio.sleep(2)

                # Poll SMSPool for OTP
                logger.info("[Phone] Polling SMSPool for OTP...")
                otp = await smspool_service.poll_otp(order_id, timeout=120)
                if not otp:
                    logger.error("[Phone] SMSPool OTP timeout")
                    return False
                logger.info(f"[Phone] Got OTP: {otp}")

                # Fill OTP
                await browser_fill_react('input[name="code"]', otp)
                await asyncio.sleep(0.5)
                try:
                    await browser_click_by_text("Continue", role="button", exact=False)
                except Exception:
                    await browser_press("Enter")
                await asyncio.sleep(5)
                return True

            except Exception as e:
                logger.warning(f"[Phone] Error: {e}")
            await asyncio.sleep(1)
        return False

    async def _wait_for_dashboard(self, timeout: float = 30) -> bool:
        """Wait for dashboard/home page after signup."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                url = await browser_get_url()
                if "vercel.com" in url and ("/dashboard" in url or "/home" in url or "/v0" in url or "/projects" in url):
                    logger.info(f"[Dashboard] Detected: {url}")
                    return True
                body = await self._get_body_text()
                if any(k in body.lower() for k in ["dashboard", "projects", "deploy", "get started", "welcome"]):
                    return True
            except Exception:
                pass
            await asyncio.sleep(2)
        return False

    async def _generate_api_token(self, alias_email: str = "", password: str = "") -> Optional[str]:
        """Navigate to API tokens page, create token, and extract it.
        
        Handles login redirect if session expired."""
        try:
            # Navigate to tokens page
            await browser_navigate(VERCEL_TOKENS_URL)
            await asyncio.sleep(8)
            url_info = await browser_get_url()
            logger.info(f"[API] On tokens page, URL: {url_info}")
            
            # Check if redirected to login page
            url_str = str(url_info)
            if "/login" in url_str and alias_email and password:
                logger.info("[API] Redirected to login, logging in first")
                try:
                    await browser_fill_react('input[type="email"]', alias_email)
                    await asyncio.sleep(0.5)
                    await browser_fill_react('input[type="password"]', password)
                    await asyncio.sleep(0.5)
                    await browser_press("Enter")
                    await asyncio.sleep(8)
                    # Re-navigate to tokens page after login
                    await browser_navigate(VERCEL_TOKENS_URL)
                    await asyncio.sleep(5)
                    logger.info(f"[API] After login, URL: {await browser_get_url()}")
                except Exception as e:
                    logger.warning(f"[API] Login attempt failed: {e}")

            # Click "Create" or "Generate Token"
            created = False
            for text in ["Create Token", "Create", "Generate Token", "New Token", "Add Token"]:
                try:
                    await browser_click_by_text(text, role="button", exact=False)
                    created = True
                    logger.info(f"[API] Clicked '{text}'")
                    break
                except Exception:
                    continue
            if not created:
                # Fallback JS click on any button containing "Create" or has svg/plus icon
                click_result = await browser_console("""(() => {
                    var btns = document.querySelectorAll('button');
                    for (var i=0; i<btns.length; i++) {
                        var t = btns[i].textContent.toLowerCase();
                        if (t.includes('create') || t.includes('generate') || t.includes('add')) {
                            btns[i].click();
                            return {clicked: true, text: btns[i].textContent.trim()};
                        }
                    }
                    // Try first button with aria-label containing "create"
                    var all = document.querySelectorAll('[aria-label*="create" i], [aria-label*="add" i]');
                    if (all.length > 0) {
                        all[0].click();
                        return {clicked: true, text: all[0].getAttribute('aria-label')};
                    }
                    return {clicked: false, buttons: Array.from(btns).slice(0,5).map(b => b.textContent.trim())};
                })()""")
                logger.info(f"[API] Fallback click result: {click_result}")
                await asyncio.sleep(3)

            # Fill token name
            token_name = f"sinator-{secrets.randbelow(9000) + 1000}"
            logger.info(f"[API] Filling token name: {token_name}")
            try:
                await browser_fill_react('input[name="name"]', token_name)
            except Exception:
                try:
                    await browser_type('input[type="text"]', token_name)
                except Exception:
                    await browser_console(f"""(() => {{
                        var inp = document.querySelector('input[name="name"], input[placeholder*="name" i], input[type="text"], input[placeholder*="token" i]');
                        if (inp) {{
                            var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                            setter.call(inp, '{token_name}');
                            inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                        }}
                    }})()""")
            await asyncio.sleep(2)

            # Submit / create
            submitted = False
            for text in ["Create Token", "Create", "Generate", "Submit"]:
                try:
                    await browser_click_by_text(text, role="button", exact=False)
                    logger.info(f"[API] Clicked submit: '{text}'")
                    submitted = True
                    break
                except Exception:
                    continue
            if not submitted:
                await browser_press("Enter")
                logger.info("[API] Submitted via Enter key")
            await asyncio.sleep(8)

            # Debug: log page text
            debug_text = await browser_console("""(() => {
                return {url: window.location.href, bodyText: document.body.innerText.slice(0,500), title: document.title};
            })()""")
            logger.info(f"[API] Page debug: {debug_text}")

            # Extract token from page — shown only once
            # Strategy 1: look for code/copyable text element
            html = await browser_get_html()
            html_str = str(html)
            # Vercel tokens are typically 24+ chars alphanumeric
            token_match = re.search(r'[A-Za-z0-9_\-]{24,}', html_str)
            if token_match:
                candidate = token_match.group(0)
                # Heuristic: must look like a token (no common words)
                if len(candidate) >= 24 and not any(w in candidate.lower() for w in ["script", "function", "class", "div", "span", "button"]):
                    logger.info(f"[API] Extracted token from HTML: {candidate[:12]}...")
                    return candidate

            # Strategy 2: JS extract from specific data-testid or class
            token_result = await browser_console("""(() => {
                // Look for token display elements
                var selectors = ['[data-testid="token-value"]', '[class*="token"]', 'code', 'pre', '[class*="key"]', '[class*="secret"]', 'input[readonly]'];
                for (var sel of selectors) {
                    var el = document.querySelector(sel);
                    if (el && el.textContent && el.textContent.length >= 24) {
                        return el.textContent.trim();
                    }
                    if (el && el.value && el.value.length >= 24) {
                        return el.value.trim();
                    }
                }
                // Fallback: look for any long alphanumeric text
                var allText = document.body.innerText;
                var matches = allText.match(/[A-Za-z0-9_\\-]{32,}/g);
                if (matches) {
                    for (var m of matches) {
                        if (!/^(function|class|div|span|script|style|https|www|vercel)/i.test(m)) {
                            return m;
                        }
                    }
                }
                return null;
            })()""")
            # browser_console returns dict with CDP Runtime.evaluate result: {"result": value, "type": ...}
            token_val = token_result.get("result") if isinstance(token_result, dict) else token_result
            if token_val and len(str(token_val)) >= 24:
                logger.info(f"[API] Extracted token via JS: {str(token_val)[:12]}...")
                return str(token_val).strip()

            logger.warning("[API] Could not extract token from page")
            return None

        except Exception as e:
            logger.error(f"[API] Token generation error: {e}")
            return None

    def _generate_password(self) -> str:
        """Generate a secure random password."""
        import secrets, string
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(chars) for _ in range(16))
