"""Get ALL options for each combobox by scrolling through the dropdown."""
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
        await uploader._wait_for_upload_form(timeout=20)

        try:
            await uploader.page.locator("button:has-text('中文')").first.click()
            print("Clicked 中文")
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Chinese button: {e}")

        combos = [
            ("环境大类", "environment"),
            ("设施类型 / 场地", "venue"),
            ("场景 / 工位 / 区域", "scene"),
        ]

        all_options = {}

        for placeholder, key in combos:
            try:
                inp = uploader.page.locator(f"input[placeholder='{placeholder}']")
                await inp.click()
                await asyncio.sleep(1.5)

                # Scroll through and collect all options
                options = await uploader.page.evaluate("""() => {
                    const pop = document.querySelector('[role="listbox"]:not([hidden])');
                    if (!pop) return [];
                    const items = pop.querySelectorAll('[role="option"]');
                    return Array.from(items).map(el => ({
                        text: el.textContent.trim(),
                        value: el.getAttribute('data-value') || el.textContent.trim()
                    }));
                }""")

                all_options[key] = options
                print(f"\n{placeholder}: {len(options)} options")
                for opt in options:
                    print(f"  [{opt['value']}] {opt['text']}")

                await uploader.page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Error on {placeholder}: {e}")

        with open('runtime/data/combobox_options.json', 'w', encoding='utf-8') as out:
            json.dump(all_options, out, ensure_ascii=False, indent=2)
        print(f"\nSaved all options")

    finally:
        await uploader.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
