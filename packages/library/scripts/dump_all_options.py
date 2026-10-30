"""Dump all form options including combobox dropdown lists."""
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

        # Get all combobox popover options
        # Click each combobox and collect its dropdown options
        result = {}

        # Map of field labels we know about
        field_labels = [
            "环境", "场所 / 场地", "场景",
            "国家", "省/州", "城市",
        ]

        # Get all [role="combobox"] inputs
        combos = await uploader.page.evaluate("""() => {
            const cbs = document.querySelectorAll('[role="combobox"]');
            return Array.from(cbs).map(el => {
                const rect = el.getBoundingClientRect();
                return {
                    id: el.id,
                    ariaLabel: el.getAttribute('aria-label') || '',
                    placeholder: el.placeholder || '',
                    visible: rect.width > 0 && rect.height > 0,
                    className: el.className.substring(0, 80)
                };
            });
        }""")
        print(f"Comboboxes found: {len(combos)}")
        for c in combos:
            print(f"  {c}")

        # Try to get options from popovers by clicking each combobox
        # Get all labelled form fields
        labels = await uploader.page.evaluate("""() => {
            const result = [];
            document.querySelectorAll('label, [class*="label"], [class*="Label"]').forEach(el => {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    const text = el.textContent.trim();
                    if (text && text.length < 50) {
                        result.push({text, bbox: {x: Math.round(rect.x), y: Math.round(rect.y)}});
                    }
                }
            });
            return result;
        }""")
        print(f"\nLabels found: {len(labels)}")
        for lbl in labels[:30]:
            print(f"  {lbl}")

        # Get all button text
        buttons = await uploader.page.evaluate("""() => {
            return Array.from(document.querySelectorAll('button')).map(el => ({
                text: el.textContent.trim(),
                visible: el.offsetParent !== null
            })).filter(b => b.text && b.visible);
        }""")
        print(f"\nButtons: {len(buttons)}")
        for b in buttons[:20]:
            print(f"  '{b['text']}'")

        # Save page HTML for analysis
        html = await uploader.page.content()
        with open('runtime/data/upload_page_full.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("\nSaved HTML to runtime/data/upload_page_full.html")

        # Keep open for a bit so user can check
        print("\nBrowser staying open 60s...")
        await asyncio.sleep(60)

    finally:
        await uploader.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
