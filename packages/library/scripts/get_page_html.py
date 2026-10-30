"""Get page HTML and take screenshot while browser is open."""
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

        # Save HTML
        html = await uploader.page.content()
        with open('runtime/data/upload_page_cn.html', 'w', encoding='utf-8') as f:
            f.write(html)
        await uploader.page.screenshot(path='runtime/data/upload_page_cn.png')
        print("Saved HTML and screenshot")

        # Keep open
        print("Browser staying open 60s...")
        await asyncio.sleep(60)
    finally:
        await uploader.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
