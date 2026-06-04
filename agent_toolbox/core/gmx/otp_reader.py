"""
SINATOR AGENT-TOOLBOX — GMX OTP Reader Mixin
Docs: otp_reader.doc.md

OTP extraction via CDP iframe navigation.
Uses CDP session to navigate GMX mail iframe and scan for OTP emails.
"""
import time
import logging
import re
import asyncio
import html as html_module
from typing import Optional, Dict, Any, Tuple

from agent_toolbox.core.cdp_client import CDPClient

logger = logging.getLogger(__name__)


class GmxServiceOtpReaderMixin:
    """Mixin providing OTP extraction via CDP iframe navigation."""

    async def read_otp(self, sender_filter: str = "fireworks", max_retries: int = 12, retry_delay: int = 5, cdp_port: Optional[int] = None) -> Dict[str, Any]:
        if cdp_port is None:
            import os
            cdp_port = int(os.environ.get("CDP_PORT", "9230"))
        start_time = time.time()
        client = None
        try:
            client, session_id = await self._otp_connect(cdp_port)
            url_result = await client.evaluate(session_id, "window.location.href")
            current_url = url_result.get("result", {}).get("value", "")
            sid = None
            domain = "bap.navigator.gmx.net"
            # Accept SID from any navigator.gmx.net subdomain
            if "navigator.gmx.net" in current_url and "sid=" in current_url:
                sid = re.search(r'[?&]sid=([^&]+)', current_url)
                sid = sid.group(1) if sid else None
                # Extract actual domain from URL for mail_url
                m = re.search(r'https://([^/]+)/', current_url)
                if m:
                    domain = m.group(1)
            if not sid:
                # Navigate to www.gmx.net and get fresh SID via Zum Postfach
                await client.navigate(session_id, "https://www.gmx.net/")
                await asyncio.sleep(4)
                body = await client.evaluate(session_id, "document.body.innerText")
                text = body.get("result", {}).get("value", "")
                if "Sie sind eingeloggt" not in text and "Zum Postfach" not in text:
                    return {"status": "error", "otp_url": None, "error": "Nicht eingeloggt"}
                await client.evaluate(session_id, """
                (function(){
                    var els = Array.from(document.querySelectorAll('a, button, [role=link], nav a'));
                    var el = els.find(e => {
                        var t = (e.textContent||'').trim();
                        return t === 'E-Mail' || t === 'Zum Postfach' || t.indexOf('E-Mail') !== -1 || t.indexOf('Postfach') !== -1;
                    });
                    if (el) { el.click(); return true; }
                    return false;
                })()
                """, return_by_value=True)
                await asyncio.sleep(5)
                url_result = await client.evaluate(session_id, "window.location.href")
                current_url = url_result.get("result", {}).get("value", "")
                sid = re.search(r'[?&]sid=([^&]+)', current_url)
                sid = sid.group(1) if sid else None
                m = re.search(r'https://([^/]+)/', current_url)
                if m:
                    domain = m.group(1)
            if not sid:
                return {"status": "error", "otp_url": None, "error": "Kein SID"}
            # Use same domain as the original URL for mail navigation
            mail_url = f"https://{domain}/mail?sid={sid}"
            await client.navigate(session_id, mail_url)
            await asyncio.sleep(6)
            iframe_result = await client.evaluate(session_id, """
            (function() {
                var iframe = document.querySelector('#thirdPartyFrame_mail');
                return iframe ? iframe.src : null;
            })()
            """, return_by_value=True)
            iframe_src = iframe_result.get("result", {}).get("value", "")
            if not iframe_src:
                # Fallback: try with bap.navigator.gmx.net (most reliable for iframe)
                logger.warning(f"[read_otp] iframe not found on {domain}, trying bap.navigator.gmx.net fallback")
                mail_url = f"https://bap.navigator.gmx.net/mail?sid={sid}"
                await client.navigate(session_id, mail_url)
                await asyncio.sleep(6)
                iframe_result = await client.evaluate(session_id, """
                (function() {
                    var iframe = document.querySelector('#thirdPartyFrame_mail');
                    return iframe ? iframe.src : null;
                })()
                """, return_by_value=True)
                iframe_src = iframe_result.get("result", {}).get("value", "")
                if not iframe_src:
                    return {"status": "error", "otp_url": None, "error": "Mail iframe nicht gefunden"}
            await client.navigate(session_id, iframe_src)
            await asyncio.sleep(5)
            cookies_res = await client.send_to_session(session_id, "Network.getAllCookies")
            jsessionid = None
            for c in cookies_res.get("cookies", []):
                if c.get("name") == "JSESSIONID":
                    jsessionid = c.get("value", "")
                    break
            if not jsessionid:
                current_url_result = await client.evaluate(session_id, "window.location.href")
                current_page_url = current_url_result.get("result", {}).get("value", "")
                jsessionid_match = re.search(r'jsessionid=([^?&;]+)', current_page_url)
                jsessionid = jsessionid_match.group(1) if jsessionid_match else None
            if not jsessionid:
                logger.warning("[read_otp] Kein JSESSIONID gefunden — versuche trotzdem (iframe-URL enthält Session)")
            known_ids = set()
            for i in range(max_retries):
                logger.info(f"OTP-Suche: Versuch {i+1}/{max_retries}")
                safe_filter = sender_filter.lower().replace("'", "\\'")
                items_js = f"""
                (function() {{
                    function findItems(root) {{
                        let items = [];
                        const all = root.querySelectorAll('*');
                        for (const el of all) {{
                            if (el.tagName.toLowerCase() === 'list-mail-item') {{
                                const text = (el.textContent || '').toLowerCase();
                                if (text.includes('{safe_filter}')) {{
                                    const idAttr = el.getAttribute('id');
                                    const mailId = idAttr ? idAttr.replace(/^id/, '') : null;
                                    if (mailId) {{
                                        items.push({{mailId: mailId, text: el.textContent.trim().slice(0, 120)}});
                                    }}
                                }}
                            }}
                            if (el.shadowRoot) {{
                                items = items.concat(findItems(el.shadowRoot));
                            }}
                        }}
                        return items;
                    }}
                    return findItems(document.body);
                }})()
                """
                items_result = await client.evaluate(session_id, items_js, return_by_value=True)
                items = items_result.get("result", {}).get("value", [])
                new_items = [it for it in items if it.get("mailId") not in known_ids]
                if new_items:
                    await client.send_to_session(session_id, "Accessibility.enable")
                    await asyncio.sleep(1)
                    ax_result = await client.send_to_session(session_id, "Accessibility.getFullAXTree", {"depth": -1, "pierce": True})
                    ax_nodes = ax_result.get("nodes", [])
                    verify_nodes = []
                    for n in ax_nodes:
                        name_val = (n.get("name", {}) or {}).get("value", "")
                        desc_val = (n.get("description", {}) or {}).get("value", "")
                        combined = f"{name_val} {desc_val}".lower()
                        if safe_filter in combined:
                            verify_nodes.append(n)
                    logger.info(f"AXTree: {len(ax_nodes)} nodes, {len(verify_nodes)} {sender_filter} hits")
                    if verify_nodes:
                        target_node = verify_nodes[0]
                        bid = target_node.get("backendDOMNodeId")
                        if bid:
                            try:
                                quad = await client.send_to_session(session_id, "DOM.getContentQuads", {"backendNodeId": bid})
                                quads = quad.get("quads", [])
                                if quads and quads[0]:
                                    q = quads[0]
                                    cx = (q[0] + q[4]) / 2
                                    cy = (q[1] + q[5]) / 2
                                    logger.info(f"Click fireworks email at ({cx:.0f},{cy:.0f})")
                                    before_ids = {t["targetId"] for t in await client.get_targets()}
                                    await client.send_to_session(session_id, "Input.dispatchMouseEvent", {"type": "mouseMoved", "x": cx, "y": cy})
                                    await asyncio.sleep(0.2)
                                    await client.send_to_session(session_id, "Input.dispatchMouseEvent", {"type": "mousePressed", "x": cx, "y": cy, "button": "left", "clickCount": 1})
                                    await asyncio.sleep(0.15)
                                    await client.send_to_session(session_id, "Input.dispatchMouseEvent", {"type": "mouseReleased", "x": cx, "y": cy, "button": "left", "clickCount": 1})
                                    await asyncio.sleep(5)
                                    after = await client.get_targets()
                                    for t in after:
                                        tu = t.get("url", "")
                                        if "mailbody" in tu:
                                            logger.info(f"Mailbody OOPIF: {tu[:120]}")
                                            try:
                                                ifs = await client.attach_to_target(t["targetId"])
                                                await client.send_to_session(ifs, "Runtime.enable")
                                                body_r = await client.evaluate(ifs, 'document.body ? document.body.innerText : ""', return_by_value=True)
                                                b = body_r.get("result", {}).get("value", "") or ""
                                                if not b.strip():
                                                    html_r = await client.evaluate(ifs, 'document.body ? document.body.innerHTML : ""', return_by_value=True)
                                                    b = html_r.get("result", {}).get("value", "") or ""
                                                urls = re.findall(rf'https?://\S*{re.escape(safe_filter)}\S*[^\s"\'<>]+', b)
                                                if urls:
                                                    elapsed = time.time() - start_time
                                                    return {"status": "success", "otp_url": html_module.unescape(urls[0]), "mail_id": None, "execution_time": f"{elapsed:.2f}s"}
                                            except Exception:
                                                pass
                                            await asyncio.sleep(0.1)
                            except Exception as e:
                                logger.warning(f"AXTree click failed: {e}")
                for it in items:
                    mid = it.get("mailId")
                    if mid:
                        known_ids.add(mid)
                if i < max_retries - 1:
                    await asyncio.sleep(retry_delay)
            return {"status": "not_found", "otp_url": None, "error": "Nicht gefunden"}
        except Exception as e:
            logger.error(f"OTP-Suche fehlgeschlagen: {e}")
            return {"status": "error", "otp_url": None, "error": str(e)}
        finally:
            if client:
                await client.disconnect()
