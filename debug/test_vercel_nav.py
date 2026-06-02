"""
Debug script: Navigate to Vercel referral link via sin-browser-tools,
take screenshot and save DOM snapshot.
"""
import asyncio
import json
from pathlib import Path
from sin_browser_tools.core.manager import BrowserManager
from sin_browser_tools.tools.navigation import manager as nav_mgr, browser_navigate, browser_new_tab, browser_get_url
from sin_browser_tools.tools.vision import browser_screenshot
from sin_browser_tools.tools.extraction import browser_get_html
from sin_browser_tools.tools.diagnostics import browser_diag_snapshot_all

async def main():
    mgr = BrowserManager(headless=False)
    await mgr.connect_cdp("http://127.0.0.1:9222")
    nav_mgr._set_instance(mgr)
    
    # List existing tabs
    print("Existing tabs:")
    for ctx in mgr._browser.contexts:
        for i, pg in enumerate(ctx.pages):
            print(f"  [{i}] {pg.url[:80]}")
    
    # Open new tab for Vercel
    new_page = await mgr.new_page()
    mgr.set_active_page(new_page)
    print(f"\nNew tab URL: {new_page.url}")
    
    # Navigate to referral link
    result = await browser_navigate("https://v0.app/ref/6IMSRI")
    print(f"Navigate result: {result}")
    
    await asyncio.sleep(8)
    
    # Screenshot
    ss = await browser_screenshot(full_page=True)
    if ss.get("image_data"):
        out = Path("/Users/jeremy/dev/SINator-v0+Vercel/debug/vercel_referral.png")
        out.write_bytes(ss["image_data"])
        print(f"Screenshot saved: {out}")
    
    # HTML snapshot
    html = await browser_get_html()
    html_path = Path("/Users/jeremy/dev/SINator-v0+Vercel/debug/vercel_referral.html")
    html_path.write_text(str(html)[:50000])
    print(f"HTML saved: {html_path}")
    
    # Diagnostics snapshot
    diag = await browser_diag_snapshot_all()
    diag_path = Path("/Users/jeremy/dev/SINator-v0+Vercel/debug/vercel_referral_diag.json")
    diag_path.write_text(json.dumps(diag, indent=2, default=str)[:50000])
    print(f"Diag saved: {diag_path}")
    
    await mgr.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
