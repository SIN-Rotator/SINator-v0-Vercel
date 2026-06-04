"""
SINATOR AGENT-TOOLBOX — GMX OTP Playwright Mixin
Docs: otp_playwright.doc.md

OTP extraction via Playwright frame traversal.
Scans all frames including OOPIFs and Shadow DOM for OTP emails.
"""
import time
import logging
import re
import asyncio
import html as html_module
from typing import Optional, Dict, Any

from playwright.async_api import Browser, Page

logger = logging.getLogger(__name__)


class GmxServiceOtpPlaywrightMixin:
    """Mixin providing OTP extraction via Playwright frame traversal."""

    async def read_otp_via_playwright(self, browser: Browser, sender_filter: str = "fireworks",
                                       max_retries: int = 15, retry_delay: int = 6,
                                       existing_page: Optional[Page] = None) -> Dict[str, Any]:
        """Read OTP via Playwright. Wenn existing_page übergeben, reuse (bleibt im logged-in Tab).
        Sonst frische Page pro Versuch (fallback).
        """
        start_time = time.time()
        pattern = re.compile(r'(?:https://app\.fireworks\.ai/(?:signup/(?:confirm|verify)|confirm|verify|accounts/confirm)|'
                            r'https://vercel\.com/(?:signup|confirm|verify|welcome))\S+')
        for attempt in range(max_retries):
            pw_page = None
            own_page = False
            try:
                if existing_page is not None and attempt == 0:
                    pw_page = existing_page
                else:
                    pw_page = await browser.new_page()
                    own_page = True
                await pw_page.goto("https://navigator.gmx.net/mail", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(5)

                body = await pw_page.evaluate("() => document.body.innerText")
                if "Nicht eingeloggt" in body or ("anmelden" in body.lower()[:300] and "E-Mail" not in body):
                    logger.warning(f"GMX session verloren (attempt {attempt+1})")
                    return {"status": "error", "otp_url": None, "error": "Nicht eingeloggt"}

                # Shadow-DOM + Multi-Frame Scan: Mail kann in OOPIF (z.B. bap.navigator.gmx.net) liegen,
                # nicht nur im Hauptframe. Wir scannen daher ALLE Frames der Page.
                scan_js = r"""
                (SENDER) => {
                    let out = [];
                    function walk(root) {
                        let nodes;
                        try { nodes = root.querySelectorAll('*'); } catch (e) { return; }
                        for (const el of nodes) {
                            if (el.tagName && el.tagName.toLowerCase() === 'list-mail-item') {
                                const txt = (el.innerText || el.textContent || '');
                                if (txt.toLowerCase().includes(SENDER.toLowerCase())) {
                                    const id = (el.getAttribute('id') || '').replace(/^id/, '') || null;
                                    out.push({mailId: id, text: txt.trim().slice(0, 400)});
                                }
                            }
                            if (el.shadowRoot) walk(el.shadowRoot);
                        }
                    }
                    if (document.body) walk(document.body);
                    return out;
                }
                """
                click_js = r"""
                (args) => {
                    const targetId = (args[0] || '');
                    const targetText = (args[1] || '');
                    function walk(root) {
                        let nodes;
                        try { nodes = root.querySelectorAll('*'); } catch (e) { return false; }
                        for (const el of nodes) {
                            if (el.tagName && el.tagName.toLowerCase() === 'list-mail-item') {
                                const eid = (el.getAttribute('id') || '').replace(/^id/, '');
                                const txt = (el.innerText || el.textContent || '').trim().slice(0, 400);
                                if ((targetId && eid === targetId) || (!targetId && txt === targetText)) {
                                    el.click(); return true;
                                }
                            }
                            if (el.shadowRoot && walk(el.shadowRoot)) return true;
                        }
                        return false;
                    }
                    return walk(document.body);
                }
                """
                items = []
                matched_frame = None
                frames = list(pw_page.frames)
                logger.debug(f"[otp] scanning {len(frames)} frame(s): {[f.url[:50] for f in frames]}")
                for frame in frames:
                    try:
                        found = await frame.evaluate(scan_js, sender_filter.lower())
                    except Exception:
                        found = []
                    if found:
                        items = found
                        matched_frame = frame
                        break

                if items and matched_frame is not None:
                    logger.info(f"Found {len(items)} email(s) matching '{sender_filter}' in {matched_frame.url[:60]}")
                    logger.debug(f"Items: {[i.get('text','')[:60] for i in items]}")

                    # Check mail list preview for URL
                    for item in items:
                        urls = pattern.findall(item.get('text', ''))
                        if urls:
                            elapsed = time.time() - start_time
                            return {"status": "success", "otp_url": html_module.unescape(urls[0]), "execution_time": f"{elapsed:.2f}s"}

                    # Click first matching email IN ITS FRAME (Playwright evaluate nimmt genau 1 Arg -> Liste)
                    clicked = await matched_frame.evaluate(click_js, [items[0].get('mailId'), items[0].get('text', '')])
                    if clicked:
                        logger.info("Clicked email — polling for OOPIF...")
                        # Poll OOPIF: 3 tries × 3s = 9s max wait
                        for oopif_wait in range(3):
                            await asyncio.sleep(3)
                            for frame in pw_page.frames:
                                try:
                                    text = await frame.evaluate("() => document.body.innerText", timeout=3000)
                                    urls = pattern.findall(text or '')
                                    if urls:
                                        elapsed = time.time() - start_time
                                        return {"status": "success", "otp_url": html_module.unescape(urls[0]), "execution_time": f"{elapsed:.2f}s"}
                                except Exception:
                                    pass
                        # Fallback: scan entire page HTML
                        html = await pw_page.content()
                        urls = pattern.findall(html)
                        if urls:
                            elapsed = time.time() - start_time
                            return {"status": "success", "otp_url": html_module.unescape(urls[0]), "execution_time": f"{elapsed:.2f}s"}
                        logger.warning("OOPIF not found after clicking email")
                else:
                    logger.info(f"No '{sender_filter}' email yet (attempt {attempt+1}/{max_retries})")
            except Exception as e:
                logger.warning(f"OTP attempt {attempt+1} fehlgeschlagen: {e}")
            finally:
                if pw_page and own_page:
                    try:
                        await pw_page.close()
                    except Exception:
                        pass

            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)

        return {"status": "not_found", "otp_url": None, "error": "Nicht gefunden"}
