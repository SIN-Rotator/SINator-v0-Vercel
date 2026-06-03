import asyncio
import json
from pathlib import Path
from sin_browser_tools.core.manager import BrowserManager
from sin_browser_tools.tools.navigation import manager as nav_mgr, browser_navigate, browser_get_url
from sin_browser_tools.tools.extraction import browser_get_html

async def main():
    mgr = BrowserManager(headless=False)
    try:
        await mgr.connect_cdp("http://127.0.0.1:9222")
        nav_mgr._set_instance(mgr)
        print(f"Connected. URL before nav: {mgr.page.url}")
        
        # Navigate
        result = await browser_navigate("https://v0.app/ref/6IMSRI")
        print(f"Navigate result: {result}")
        
        await asyncio.sleep(5)
        print(f"URL after sleep: {mgr.page.url}")
        
        # Get title
        title = await mgr.page.evaluate("document.title")
        print(f"Page title: {title}")
        
        # Save HTML
        html = await browser_get_html()
        out = Path("/Users/jeremy/dev/SINator-v0+Vercel/debug/smoke_html.html")
        out.write_text(str(html)[:50000])
        print(f"HTML saved to {out}")
        
        # Check for key elements
        html_str = str(html).lower()
        has_email = 'type="email"' in html_str or 'name="email"' in html_str
        has_continue = 'continue' in html_str
        print(f"Has email field: {has_email}")
        print(f"Has continue text: {has_continue}")
        
    finally:
        # Do NOT cleanup — we connected to existing Chrome
        print("Test complete. Not calling cleanup() to preserve Chrome session.")

if __name__ == "__main__":
    asyncio.run(main())
