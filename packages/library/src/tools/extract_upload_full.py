#!/usr/bin/env python3
"""
提取上传表单完整字段列表，包括 scene。
"""
import asyncio, json, sys
from pathlib import Path
from playwright.async_api import async_playwright

PROJ_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ_DIR))
from auto_upload import BROWSER_DATA_DIR, UPLOAD_URL

OUTPUT = PROJ_DIR / "tools" / "upload_form_scene.json"

async def main():
    async with async_playwright() as p:
        try:
            ctx = await p.chromium.launch_persistent_context(
                BROWSER_DATA_DIR,
                headless=False,
                viewport={"width": 1400, "height": 1000},
            )
        except Exception as e:
            print(f"[!] profile busy: {e}")
            ctx = await p.chromium.launch_persistent_context(
                str(PROJ_DIR / "runtime" / "browser_data_temp"),
                headless=False,
                viewport={"width": 1400, "height": 1000},
            )

        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        
        print(f"[*] navigating to: {UPLOAD_URL}")
        await page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(3)
        
        print(f"[*] current URL: {page.url}")
        
        # Scroll to bottom to load all fields
        print("[*] scrolling to load all fields...")
        for _ in range(5):
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(0.5)
        await asyncio.sleep(2)
        
        # 1. Look for specific "scene" field
        print("\n[*] searching for 'scene' field...")
        
        # Try various selectors
        scene_selectors = [
            "select[data-field='scene']",
            "select[name*='scene']",
            "select[id*='scene']",
            "select[data-field*='scene']",
            "label:has-text('Scene') + select",
            "label:has-text('scene') + select",
        ]
        
        scene_sel = None
        for sel in scene_selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible():
                    scene_sel = el
                    print(f"[√] found scene with selector: {sel}")
                    break
            except:
                pass
        
        if scene_sel:
            opts = await scene_sel.locator("option").all()
            results = []
            for o in opts:
                v = (await o.get_attribute("value") or "").strip()
                t = (await o.inner_text()).strip()
                if v:
                    results.append({"value": v, "label": t})
            print(f"[√] scene has {len(results)} options")
            for r in results[:10]:
                print(f"    {r['value']} => {r['label']}")
            if len(results) > 10:
                print(f"    ... and {len(results)-10} more")
            
            # Save results
            data = {"scene": results}
            with open(OUTPUT, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"[√] saved to: {OUTPUT}")
        else:
            print("[!] scene field not found with standard selectors")
            
            # Try to find it by labels
            print("\n[*] listing all select fields...")
            selects = await page.locator("select").all()
            
            all_data = {}
            for i, s in enumerate(selects):
                try:
                    name = (await s.get_attribute("name")) or ""
                    df = (await s.get_attribute("data-field")) or ""
                    sid = (await s.get_attribute("id")) or ""
                    
                    # Find associated label
                    label = ""
                    if sid:
                        lbl = page.locator(f"label[for='{sid}']")
                        if await lbl.count():
                            label = await lbl.first.inner_text()
                    
                    key = df or name or f"select_{i}"
                    opts = await s.locator("option").all()
                    opt_data = []
                    for o in opts:
                        v = (await o.get_attribute("value") or "").strip()
                        t = (await o.inner_text()).strip()
                        if v:
                            opt_data.append({"value": v, "label": t})
                    
                    print(f"  [{i}] {key} ({len(opt_data)} opts) label='{label}'")
                    if len(opt_data) > 100:
                        print(f"      sample: {opt_data[0]}")
                    all_data[key] = opt_data
                except Exception as e:
                    print(f"  [{i}] error: {e}")
            
            # Save everything
            with open(OUTPUT, "w", encoding="utf-8") as f:
                json.dump(all_data, f, ensure_ascii=False, indent=2)
            print(f"[√] all selects saved to: {OUTPUT}")
        
        # Screenshot
        await page.screenshot(path=str(PROJ_DIR / "tools" / "upload_full.png"))
        print("[√] screenshot saved")
        
        await ctx.close()
        print("[√] done")

if __name__ == "__main__":
    asyncio.run(main())
