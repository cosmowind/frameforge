import sys; sys.stdout.reconfigure(encoding='utf-8')
from playwright.sync_api import sync_playwright
import time

pw = sync_playwright().start()
browser = pw.chromium.connect_over_cdp('http://localhost:9222')
page = browser.contexts[0].pages[0]
time.sleep(0.5)

# 1. Click first video tile
print('=== Clicking first tile ===')
tile = page.locator('.vcb-tile').first
bb = tile.bounding_box()
cx = bb['x'] + bb['width']/2
cy = bb['y'] + bb['height']/2
page.mouse.click(cx, cy)
time.sleep(1)
print('URL:', page.url)

# 2. Look for expanded content, missing indicator, expand button
print()
print('=== Looking for elements after tile click ===')

# Look for "missing" text
missing_els = page.locator('text=missing').all()
print(f'"missing" elements: {len(missing_els)}')
for e in missing_els[:5]:
    try:
        bb = e.bounding_box()
        txt = e.text_content()
        print(f'  ({bb["x"]:.0f},{bb["y"]:.0f}) "{txt[:40]}"')
    except: pass

# Look for expand chevron/arrow buttons
all_buttons = {b.text_content() or '': b for b in page.locator('button').all()}
print(f'Buttons with text: {list(all_buttons.keys())[:20]}')

# Look for edit/metadata text
for txt in ['Edit metadata', 'edit', 'metadata', 'chevron', 'expand', 'arrow']:
    els = page.locator(f'text={txt}').all()
    if els:
        print(f'"{txt}" elements: {len(els)}')
        for e in els[:3]:
            try:
                bb = e.bounding_box()
                print(f'  ({bb["x"]:.0f},{bb["y"]:.0f}) "{e.text_content()[:40]}"')
            except: pass

browser.close()
pw.stop()
