"""Keep browser open so user can manually expand each dropdown and capture their options."""
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

        print("Browser is open. Do NOT close it.")
        print("For each field below, manually click the dropdown and wait 2s, then I'll capture the list.")
        print()
        await asyncio.sleep(300)
    finally:
        await uploader.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
