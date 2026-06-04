"""
SINATOR AGENT-TOOLBOX — GMX OTP CDP Mixin
Docs: otp_cdp.doc.md

OTP extraction via CDP Accessibility Tree.
Penetrates OOPIFs and Shadow-DOM using Chromium's cross-process AXTree.
"""
import time
import logging
import re
import asyncio
import html as html_module
from typing import Optional, Dict, Any

from playwright.async_api import Page

logger = logging.getLogger(__name__)


class GmxServiceOtpCdpMixin:
    """Mixin providing OTP extraction via CDP Accessibility Tree."""

    async def read_otp_cdp_axtree(
        self, sender_keyword: str = "fireworks", timeout: int = 180,
        page: Optional[Page] = None
    ) -> Dict[str, Any]:
        """BULLETPROOF OTP via CDP Accessibility Tree.
        Umgeht das '62 Ad-Frames' Problem komplett.
        Nutzt Chromium's prozessübergreifende AXTree (durchdringt OOPIFs + Shadow-DOM).

        Args:
            page: Page to use. Defaults to self.inbox_tab (backward compat).
        """
        page = page or self.inbox_tab
        if page is None:
            logger.error("No page available for OTP")
            return {"status": "error", "otp_url": None, "error": "no page"}

        logger.info(f"[CDP-AXTree] Starte OTP-Suche (Keyword: {sender_keyword}, timeout: {timeout}s)")
        pattern_url = re.compile(
            r"(?:https://app\.fireworks\.ai/(?:signup/(?:confirm|verify)|confirm|verify|accounts/confirm)|"
            r"https://vercel\.com/(?:signup|confirm|verify|welcome|accounts/confirm)|"
            r"https://v0\.app/(?:signup|confirm|verify|welcome))\S+"
        )
        pattern_otp = re.compile(r"\b[A-Z0-9]{6}\b")

        cdp = None
        start_time = time.time()
        try:
            cdp = await page.context.new_cdp_session(page)
            await cdp.send("Accessibility.enable")
            logger.info("[CDP-AXTree] CDP session erstellt")

            deadline = start_time + timeout
            while time.time() < deadline:
                try:
                    tree_result = await cdp.send("Accessibility.getFullAXTree", {"pierce": True})
                    nodes = tree_result.get("nodes", [])
                    logger.debug(f"[CDP-AXTree] {len(nodes)} AXTree nodes gescannt, URL: {page.url[:60]}")

                    # Session Restore / Consent / Loading page detection
                    current_url = page.url or ""
                    is_on_inbox = "navigator.gmx.net/mail" in current_url or "bap.navigator.gmx.net/mail" in current_url

                    if len(nodes) < 20 or not is_on_inbox or "logoutlounge" in current_url:
                        # Check for session restore interstitial
                        session_keywords = ["sitzung", "wiederhergestellt", "cookies", "loading", "bitte warten", "wird geladen"]
                        sample_text = " ".join(
                            f"{(n.get('name') or {}).get('value', '')} {(n.get('description') or {}).get('value', '')}"
                            for n in nodes[:15]
                        ).lower()
                        has_session_msg = any(kw in sample_text for kw in session_keywords)

                        if has_session_msg or len(nodes) < 20 or "logoutlounge" in current_url:
                            logger.warning(f"[CDP-AXTree] GMX Session/Loading-Seite erkannt (nodes={len(nodes)}, inbox={is_on_inbox}, url={current_url[:60]}) — lade neu...")
                            # Consent page detection: accept and navigate to inbox
                            if "consent" in current_url:
                                logger.info("[CDP-AXTree] Consent-Seite erkannt — akzeptiere via JS...")
                                try:
                                    result = await cdp.send("Runtime.evaluate", {
                                        "expression": """
                                            (() => {
                                                const btns = document.querySelectorAll('button');
                                                for (const b of btns) {
                                                    const t = b.textContent.toLowerCase();
                                                    if (t.includes('alle') || t.includes('zustimmen') ||
                                                        t.includes('akzeptieren') || t.includes('ok')) {
                                                        b.click();
                                                        return 'clicked: ' + b.textContent;
                                                    }
                                                }
                                                return 'no consent button found';
                                            })()
                                        """,
                                        "awaitPromise": True,
                                    })
                                    logger.info(f"[CDP-AXTree] Consent clicked: {result}")
                                    await asyncio.sleep(3)
                                    # After accepting consent, navigate directly to inbox
                                    await page.goto("https://bap.navigator.gmx.net/mail", wait_until="domcontentloaded", timeout=15000)
                                    await asyncio.sleep(5)
                                    continue
                                except Exception as ce:
                                    logger.warning(f"[CDP-AXTree] Consent handling failed: {ce}")
                            try:
                                await page.reload(wait_until="domcontentloaded", timeout=15000)
                                await asyncio.sleep(5)
                                logger.info("[CDP-AXTree] Page reloaded, continue polling")
                                continue
                            except Exception as reload_err:
                                logger.warning(f"[CDP-AXTree] Reload failed: {reload_err}")
                                try:
                                    await page.goto("https://bap.navigator.gmx.net/mail", wait_until="domcontentloaded", timeout=15000)
                                    await asyncio.sleep(5)
                                except Exception:
                                    pass
                                continue

                    full_text = ""
                    fireworks_found = False

                    for node in nodes:
                        name_val = (node.get("name") or {}).get("value", "")
                        desc_val = (node.get("description") or {}).get("value", "")
                        val_val = (node.get("value") or {}).get("value", "")
                        node_text = f"{name_val} {desc_val} {val_val}"
                        node_lower = node_text.lower()

                        if sender_keyword.lower() in node_lower:
                            fireworks_found = True
                            full_text += " " + node_text

                            url_match = pattern_url.search(node_text)
                            if url_match:
                                elapsed = time.time() - start_time
                                logger.info(f"[CDP-AXTree] ✅ URL gefunden nach {elapsed:.1f}s")
                                return {
                                    "status": "success",
                                    "otp_url": html_module.unescape(url_match.group(0)),
                                    "otp_code": None,
                                    "execution_time": f"{elapsed:.2f}s",
                                }

                    if fireworks_found:
                        otp_match = pattern_otp.search(full_text)
                        if otp_match:
                            elapsed = time.time() - start_time
                            logger.info(f"[CDP-AXTree] ✅ OTP-Code: {otp_match.group(0)}")
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
