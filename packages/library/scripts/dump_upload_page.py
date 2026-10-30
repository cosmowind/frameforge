"""Quick dump of upload page structure - find Chinese button and dropdown options."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from auto_upload import AutoUploader

async def main():
    uploader = AutoUploader()
    try:
        await uploader.start()

        # Wait for form
        await uploader._wait_for_upload_form(timeout=20)

        # Try to find Chinese button
        print("Looking for Chinese button...")
        for selector in [
            "button:has-text('中文')",
            "button:has-text('Chinese')",
            "[aria-label*='中文']",
            "[aria-label*='Language']",
            "text=中文",
        ]:
            try:
                cnt = await uploader.page.locator(selector).count()
                if cnt > 0:
                    txt = await uploader.page.locator(selector).first.inner_text()
                    print(f"  FOUND: {selector} → '{txt}' ({cnt} elements)")
            except Exception as e:
                print(f"  {selector}: {e}")

        # Click it
        try:
            await uploader.page.locator("button:has-text('中文')").first.click()
            print("Clicked Chinese button")
            await asyncio.sleep(2)
        except:
            print("Could not click Chinese button")

        # Get page text
        body = await uploader.page.locator("body").inner_text()
        lines = [l.strip() for l in body.split('\n') if l.strip()]
        print(f"\nVisible text ({len(lines)} lines):")
        for l in lines[:80]:
            print(f"  {l}")

        # Get all selects with options
        selects = await uploader.page.evaluate("""() => {
            const result = [];
            document.querySelectorAll('select').forEach((sel, i) => {
                const rect = sel.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    result.push({
                        id: sel.id,
                        name: sel.name,
                        opts: Array.from(sel.options).slice(0, 30).map(o => ({v: o.value, t: o.text}))
                    });
                }
            });
            return result;
        }""")

        print(f"\nSelect elements ({len(selects)}):")
        for s in selects:
            print(f"  id={s['id']}, name={s['name']}")
            for o in s['opts']:
                print(f"    [{o['v']}] {o['t']}")

        # Get combobox inputs
        combos = await uploader.page.evaluate("""() => {
            const result = [];
            document.querySelectorAll('[role="combobox"]').forEach((el, i) => {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0) {
                    result.push({
                        id: el.id,
                        ariaLabel: el.getAttribute('aria-label') || '',
                        placeholder: el.placeholder || '',
                        className: el.className.substring(0, 100)
                    });
                }
            });
            return result;
        }""")

        print(f"\nCombobox elements ({len(combos)}):")
        for c in combos:
            print(f"  id={c['id']}, ariaLabel={c['ariaLabel']}, placeholder={c['placeholder']}")

        with open('runtime/data/upload_page_dump.json', 'w', encoding='utf-8') as f:
            json.dump({"selects": selects, "comboboxes": combos, "body_text": lines[:80]}, f, ensure_ascii=False, indent=2)
        print("\nSaved to runtime/data/upload_page_dump.json")

    finally:
        await uploader.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
