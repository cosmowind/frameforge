"""Dump all combobox dropdown options from the Chinese upload page."""
import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from auto_upload import AutoUploader

async def get_listbox_options(uploader):
    """Get options from visible listbox popover."""
    await asyncio.sleep(1.5)
    # Try different popover selectors
    for sel in [
        "[role='listbox']",
        ".bg-popover [role='listbox']",
        "[class*='popover'] [role='listbox']",
    ]:
        cnt = await uploader.page.locator(sel).count()
        if cnt > 0:
            for i in range(cnt):
                lb = uploader.page.locator(sel).nth(i)
                try:
                    visible = await lb.is_visible(timeout=1000)
                    if visible:
                        opts = await lb.locator("[role='option']").all()
                        if opts:
                            items = []
                            for o in opts:
                                t = await o.inner_text()
                                v = await o.get_attribute('data-value') or ''
                                items.append({"t": t.strip(), "v": v})
                            return items
                except:
                    pass
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
        combos = [
            ("operator_job", "操作员从事的标准职业(职业分类)"),
            ("business_type", "细分行业,如 药房、诊所、实验室"),
            ("environment", "环境大类"),
            ("facility_venue", "设施类型 / 场地"),
            ("scene", "场景 / 工位 / 区域"),
        ]

        for key, placeholder in combos:
            print(f"\n{key}...")
            try:
                inp = uploader.page.locator("[placeholder='" + placeholder + "']")
                cnt = await inp.count()
                if cnt == 0:
                    print(f"  input not found")
                    continue
                await inp.first.click()
                items = await get_listbox_options(uploader)
                results[key] = items
                print(f"  {len(items)} options:")
                for opt in items[:20]:
                    print(f"    [{opt['v'][:30]}] {opt['t'][:50]}")
                await uploader.page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"  ERROR: {e}")

        with open('runtime/data/all_dropdown_options.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\nSaved to runtime/data/all_dropdown_options.json")

    finally:
        await uploader.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
