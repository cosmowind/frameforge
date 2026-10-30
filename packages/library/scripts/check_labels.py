"""Check labels for problematic fields."""
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

        # Get all labels and their for-attribute
        labels = await uploader.page.evaluate("""() => {
            const result = [];
            document.querySelectorAll('label, [class*="label"]').forEach(el => {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    result.push({
                        text: el.textContent.trim().substring(0, 50),
                        htmlFor: el.htmlFor || '',
                        tag: el.tagName,
                        className: el.className.substring(0, 60)
                    });
                }
            });
            return result;
        }""")

        print(f"Labels ({len(labels)}):")
        for lbl in labels[:40]:
            print(f"  [{lbl['tag']}] {lbl['text']} | for={lbl['htmlFor']}")

    finally:
        await uploader.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
