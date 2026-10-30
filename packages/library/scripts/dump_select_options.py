"""Click each combobox and get its dropdown options."""
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

        # Get all combobox inputs (aria-expanded, aria-haspopup)
        combos = await uploader.page.evaluate("""() => {
            const result = [];
            // Find all inputs that are comboboxes
            document.querySelectorAll('input[role="combobox"], [aria-haspopup="listbox"]').forEach(el => {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    // Get associated label
                    let label = '';
                    const id = el.id || el.getAttribute('data-field') || '';
                    const labels = document.querySelectorAll('label');
                    labels.forEach(lbl => {
                        if (lbl.htmlFor === el.id) label = lbl.textContent.trim();
                    });
                    if (!label) {
                        const prev = el.previousElementSibling;
                        if (prev && prev.tagName === 'LABEL') label = prev.textContent.trim();
                    }
                    result.push({
                        id: el.id,
                        dataField: el.getAttribute('data-field') || '',
                        ariaLabel: el.getAttribute('aria-label') || '',
                        placeholder: el.placeholder || '',
                        label: label,
                        visible: true
                    });
                }
            });
            return result;
        }""")

        print(f"Combobox inputs found: {len(combos)}")
        for c in combos:
            print(f"  id={c['id']}, dataField={c['dataField']}, label={c['label']}, ariaLabel={c['ariaLabel']}")

        # Try clicking each combobox and getting options from the popover
        all_options = {}

        # Click each combobox and get listbox options
        for c in combos:
            try:
                sel = f"input[data-field='{c['dataField']}']" if c['dataField'] else f"#{c['id']}"
                inp = uploader.page.locator(sel)
                if await inp.count() == 0:
                    sel = f"[aria-label='{c['ariaLabel']}']"
                    inp = uploader.page.locator(sel)

                await inp.click()
                await asyncio.sleep(0.5)

                # Get options in popover
                options = await uploader.page.evaluate("""() => {
                    const items = [];
                    document.querySelectorAll('[role="option"], [role="listbox"] [id]').forEach(el => {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            items.push({
                                text: el.textContent.trim(),
                                value: el.getAttribute('data-value') || el.getAttribute('value') || el.id,
                                visible: rect.width > 0
                            });
                        }
                    });
                    return items.slice(0, 50);
                }""")

                all_options[c['dataField'] or c['id']] = {
                    'label': c['label'] or c['ariaLabel'],
                    'options': options[:30]
                }
                print(f"\n{c['dataField'] or c['id']} ({c['label']}): {len(options)} options")
                for opt in options[:10]:
                    print(f"  [{opt['value']}] {opt['text'][:60]}")

                # Close popover
                await uploader.page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
            except Exception as e:
                print(f"\nError on {c['dataField']}: {e}")

        # Also get the raw select options (task difficulty, consent, etc.)
        selects = await uploader.page.evaluate("""() => {
            const result = [];
            document.querySelectorAll('select').forEach(sel => {
                const rect = sel.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0 && !sel.id.includes('tax') && !sel.id.includes('currency') && !sel.id.includes('method')) {
                    const opts = Array.from(sel.options).slice(0, 30).map(o => ({v: o.value, t: o.text}));
                    result.push({id: sel.id, name: sel.name, opts});
                }
            });
            return result;
        }""")

        print(f"\nSelect elements (non-payment): {len(selects)}")
        for s in selects:
            print(f"  {s['id']}: {len(s['opts'])} options")
            for o in s['opts'][:15]:
                print(f"    [{o['v']}] {o['t']}")

        with open('runtime/data/form_options_dump.json', 'w', encoding='utf-8') as f:
            json.dump({'comboboxes': all_options, 'selects': selects}, f, ensure_ascii=False, indent=2)
        print("\nSaved to runtime/data/form_options_dump.json")

    finally:
        await uploader.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
