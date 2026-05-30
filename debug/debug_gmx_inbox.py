#!/usr/bin/env python3
"""Debug GMX inbox - access webmailer iframe without navigation."""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        
        page = None
        for ctx in browser.contexts:
            for pg in ctx.pages:
                url = pg.url
                # Don't touch the page - use the existing tab as-is
                if "navigator.gmx.net" in url and "mail?sid" in url:
                    page = pg
                    print(f"Found inbox: {url[:100]}")
                    break
            if page: break
        
        if not page:
            print("No inbox - creating new page")
            page = await browser.contexts[0].new_page()
            await page.goto("https://navigator.gmx.net/mail", wait_until='domcontentloaded')
            await asyncio.sleep(8)
        
        print(f"\nPage URL: {page.url[:100]}")
        
        # List frames (DON'T navigate - just inspect)
        print(f"\n=== Frames ({len(page.frames)}) ===")
        webmailer = None
        for i, f in enumerate(page.frames):
            url = f.url[:80]
            if 'webmailer.gmx.net' in url:
                webmailer = f
                print(f"  [{i}] WEBMAILER: {url}")
            elif 'navigator.gmx.net' in url or 'bap.navigator.gmx.net' in url:
                print(f"  [{i}] MAIN: {url}")
            elif 'gmx' in url.lower():
                print(f"  [{i}] GMX: {url}")
        
        if webmailer:
            print("\n=== webmailer iframe loaded ===")
            
            # Wait a bit for dynamic content
            await asyncio.sleep(3)
            
            # Get inner text
            text = await webmailer.evaluate("() => document.body.innerText")
            print(f"\nFull text (first 2000 chars):")
            print(text[:2000])
            
            # List custom elements with shadow
            print(f"\n=== Custom Elements with Shadow in webmailer ===")
            ce = await webmailer.evaluate("""(() => {
                const results = [];
                document.querySelectorAll('*').forEach(el => {
                    if (el.shadowRoot) {
                        const all = el.shadowRoot.querySelectorAll('*');
                        let hasMailItem = false;
                        let hasText = false;
                        for (const c of all) {
                            if (c.tagName.toLowerCase() === 'list-mail-item') hasMailItem = true;
                            if (c.textContent) hasText = true;
                        }
                        results.push({
                            tag: el.tagName.toLowerCase(),
                            shadowChildren: el.shadowRoot.children.length,
                            hasMailItem,
                            hasText,
                            firstChild: el.shadowRoot.children[0]?.tagName || ''
                        });
                    }
                });
                return results;
            })()""")
            for item in ce:
                print(f"  <{item['tag']}> children={item['shadowChildren']} mailItem={item['hasMailItem']} hasText={item['hasText']} firstChild={item['firstChild']}")
            
            # Check for mail elements directly
            for sel in ['list-mail-box', 'list-mail-item', 'nav-mail-check', 'list-box', 'mail-item']:
                try:
                    count_js = await webmailer.evaluate(f"() => document.querySelectorAll('{sel}').length")
                    print(f"  {sel}: JS count={count_js}")
                except:
                    pass
            
            # Check for ANY text elements that could be mail senders
            print(f"\n=== All list items (via innerText from shadow roots) ===")
            items = await webmailer.evaluate("""(() => {
                const results = [];
                function walkShadow(root) {
                    if (!root) return;
                    root.querySelectorAll('*').forEach(el => {
                        if (el.shadowRoot) {
                            const text = el.shadowRoot.textContent || '';
                            if (text.trim()) {
                                results.push({
                                    tag: el.tagName,
                                    text: text.substring(0, 200)
                                });
                            }
                        }
                    });
                }
                walkShadow(document);
                return results;
            })()""")
            for item in items[:10]:
                print(f"  <{item['tag']}> '{item['text']}'")
            if len(items) > 10:
                print(f"  ... and {len(items) - 10} more")
            
        else:
            print("\nNo webmailer frame found!")
            # Maybe the iframe hasn't loaded yet - wait and check
            for _ in range(10):
                await asyncio.sleep(2)
                for f in page.frames:
                    if 'webmailer.gmx.net' in f.url:
                        webmailer = f
                        print(f"Found webmailer after wait: {f.url[:80]}")
                        break
                if webmailer: break
            
            if not webmailer:
                print("Still no webmailer. Refreshing via JS (not navigation)...")
                try:
                    await page.evaluate("() => window.location.reload()")
                    await asyncio.sleep(5)
                    for f in page.frames:
                        if 'webmailer.gmx.net' in f.url:
                            webmailer = f
                            print(f"Found webmailer after JS reload: {f.url[:80]}")
                            break
                except:
                    pass
        
        await browser.close()

asyncio.run(main())
