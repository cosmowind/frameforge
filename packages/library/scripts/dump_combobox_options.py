"""Click each combobox and read dropdown options."""
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

        # Click Chinese button
        try:
            await uploader.page.locator("button:has-text('中文')").first.click()
            print("Clicked 中文")
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Chinese button: {e}")

        # The 3 key comboboxes have placeholder text
        combos = [
            ("环境大类", "环境"),
            ("设施类型 / 场地", "场所/场地"),
            ("场景 / 工位 / 区域", "场景"),
        ]

        all_options = {}

        for placeholder, label in combos:
            try:
                inp = uploader.page.locator(f"input[placeholder='{placeholder}']")
                await inp.click()
                print(f"\nClicked: {placeholder}")
                await asyncio.sleep(1.5)

                # Get all visible options in the popover
                options = await uploader.page.evaluate("""() => {
                    // Find the popover - could be a div with specific classes
                    const allPopovers = document.querySelectorAll('[class*="popover"], [class*="dropdown"], [class*="autocomplete"], [role="listbox"]');
                    let results = [];
                    for (const pop of allPopovers) {
                        const rect = pop.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0 && rect.width < 600 && rect.height < 500) {
                            const items = pop.querySelectorAll('[role="option"], [class*="option"], [class*="item"]');
                            if (items.length > 0) {
                                results = Array.from(items).slice(0, 50).map(el => ({
                                    text: el.textContent.trim(),
                                    value: el.getAttribute('data-value') || el.getAttribute('value') || el.id || el.textContent.trim()
                                }));
                                break;
                            }
                        }
                    }
                    return results;
                }""")

                if options:
                    all_options[label] = {'placeholder': placeholder, 'options': options}
                    print(f"  Found {len(options)} options:")
                    for opt in options[:20]:
                        print(f"    [{opt['value'][:30]}] {opt['text'][:60]}")
                else:
                    print(f"  No options found")

                await uploader.page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Error on {placeholder}: {e}")

        # Also get business_type and business_name fields
        for placeholder, label in [
            ("细分行业,如 药房、诊所、实验室", "业务类型"),
            ("注册或对外名称(可匿名)", "业务名称"),
        ]:
            try:
                inp = uploader.page.locator(f"input[placeholder='{placeholder}']")
                await inp.click()
                print(f"\nClicked: {placeholder}")
                await asyncio.sleep(1.5)

                options = await uploader.page.evaluate("""() => {
                    const allPopovers = document.querySelectorAll('[class*="popover"], [class*="dropdown"], [class*="autocomplete"], [role="listbox"]');
                    let results = [];
                    for (const pop of allPopovers) {
                        const rect = pop.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0 && rect.width < 600 && rect.height < 500) {
                            const items = pop.querySelectorAll('[role="option"], [class*="option"], [class*="item"]');
                            if (items.length > 0) {
                                results = Array.from(items).slice(0, 50).map(el => ({
                                    text: el.textContent.trim(),
                                    value: el.getAttribute('data-value') || el.getAttribute('value') || el.id || el.textContent.trim()
                                }));
                                break;
                            }
                        }
                    }
                    return results;
                }""")

                if options:
                    all_options[label] = {'placeholder': placeholder, 'options': options}
                    print(f"  Found {len(options)} options:")
                    for opt in options[:20]:
                        print(f"    [{opt['value'][:30]}] {opt['text'][:60]}")
                else:
                    print(f"  No options found")

                await uploader.page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Error on {placeholder}: {e}")

        with open('runtime/data/combobox_options.json', 'w', encoding='utf-8') as out:
            json.dump(all_options, out, ensure_ascii=False, indent=2)
        print(f"\nSaved to runtime/data/combobox_options.json")

    finally:
        await uploader.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
