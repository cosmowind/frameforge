"""Inspect the GPS address field on the Chinese upload page."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from auto_upload import AutoUploader

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

        # Type in the address field
        inp = uploader.page.locator("input[placeholder*='输入地址搜索']")
        if await inp.count() > 0:
            await inp.first.fill("南安市辉煌工业园区")
            print("Filled address")
            await asyncio.sleep(3)

            # Get all visible popover/dropdown elements
            popup_info = await uploader.page.evaluate("""() => {
                const results = [];
                document.querySelectorAll('[class*="popover"], [class*="suggest"], [class*="dropdown"], [class*="autocomplete"], [role="listbox"], [role="option"]').forEach(el => {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        results.push({
                            tag: el.tagName,
                            cls: el.className.substring(0, 80),
                            role: el.getAttribute('role') || '',
                            text: el.textContent.trim().substring(0, 60),
                            bbox: {x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height)}
                        });
                    }
                });
                return results;
            }""")
            print(f"Popup elements: {len(popup_info)}")
            for el in popup_info[:15]:
                print(f"  [{el['tag']}] role={el['role']} cls={el['cls']} text={el['text'][:40]}")

        else:
            print("Address input NOT found!")

    finally:
        await uploader.cleanup()

