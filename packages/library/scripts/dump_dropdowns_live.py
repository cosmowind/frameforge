"""Get all dropdown options from live page by clicking each combobox."""
import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from auto_upload import AutoUploader

async def click_and_get_list(uploader, placeholder):
    """Click combobox by placeholder, get [role=option] items from visible listbox."""
    inp = uploader.page.locator("[placeholder='" + placeholder + "']")
    try:
        visible = await inp.first.is_visible(timeout=3000)
        if not visible:
            return []
    except:
        return []
    await inp.first.click()
    await asyncio.sleep(2)

    # Try to find listbox
    for sel in ["[role='listbox']", "[class*='listbox']"]:
        cnt = await uploader.page.locator(sel).count()
        for i in range(cnt):
            lb = uploader.page.locator(sel).nth(i)
            try:
                r = await lb.bounding_box()
                if r and r['width'] > 0 and r['height'] > 0 and r['width'] < 600:
                    opts = lb.locator("[role='option']")
                    n = await opts.count()
                    items = []
                    for j in range(n):
                        t = await opts.nth(j).inner_text()
                        v = await opts.nth(j).get_attribute("data-value") or ""
                        items.append({"t": t.strip(), "v": v})
                    await uploader.page.keyboard.press("Escape")
                    return items
            except:
                pass

    await uploader.page.keyboard.press("Escape")
    return []

async def main():
    uploader = AutoUploader()
    try:
        await uploader.start()
        await uploader._wait_for_upload_form(timeout=20)
        try:
            await uploader.page.locator("button:has-text('中文')").first.click()
            await asyncio.sleep(2)
        except:
            pass

        results = {}
        # (key, placeholder)
        targets = [
            ("operator_job", "操作员从事的标准职业(职业分类)"),
            ("business_type", "细分行业,如 药房、诊所、实验室"),
            ("environment", "环境大类"),
            ("facility_venue", "设施类型 / 场地"),
            ("scene", "场景 / 工位 / 区域"),
        ]

        for key, placeholder in targets:
            print(f"\n{key}...")
            items = await click_and_get_list(uploader, placeholder)
            results[key] = items
            print(f"  {len(items)} options:")
            for it in items[:20]:
                print(f"    [{it['v'][:30]}] {it['t'][:50]}")
            await asyncio.sleep(0.5)

        with open('runtime/data/all_dropdown_options.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print("\nSaved dropdown options")

    finally:
        await uploader.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
