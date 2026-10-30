"""Check actual selectors on Chinese page."""
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
            print("Switched to Chinese")
            await asyncio.sleep(2)
        except:
            pass

        # Get all inputs with their selectors
        inputs = await uploader.page.evaluate("""() => {
            const result = [];
            document.querySelectorAll('input, select').forEach(el => {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    result.push({
                        tag: el.tagName.toLowerCase(),
                        type: el.type || '',
                        id: el.id,
                        name: el.name,
                        dataField: el.getAttribute('data-field') || '',
                        placeholder: el.placeholder || '',
                        role: el.getAttribute('role') || '',
                        className: el.className.substring(0, 80)
                    });
                }
            });
            return result;
        }""")

        print(f"Found {len(inputs)} interactive elements:")
        for inp in inputs:
            print(f"  {inp['tag']} type={inp['type']} id={inp['id']} data-field={inp['dataField']} placeholder={inp['placeholder'][:40]}")

    finally:
        await uploader.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
