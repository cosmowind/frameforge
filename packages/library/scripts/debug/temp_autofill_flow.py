import sys; sys.stdout.reconfigure(encoding='utf-8')
from playwright.sync_api import sync_playwright
import time, re

pw = sync_playwright().start()
browser = pw.chromium.connect_over_cdp('http://localhost:9222')
page = browser.contexts[0].pages[0]
time.sleep(0.5)

# Go to upload-history
page.goto('https://publish.example.com/vendors?tab=upload-history', timeout=15000)
page.wait_for_load_state('networkidle', timeout=8000)
time.sleep(1)

# Set filters (via JS)
print('Setting filters...')
for sel in page.locator('select').all():
    opts = [o.strip() for o in sel.locator('option').all_text_contents()]
    if any('Stereo' in o for o in opts):
        sel.select_option('stereo'); break
time.sleep(0.3)
for b in page.locator('button').all():
    if 'Excludes' in (b.text_content() or ''):
        b.click(); time.sleep(0.5)
        for tag in ['review_reject', 'vendor-delete', 'wipe']:
            loc = page.locator(f'button:has-text("{tag}")')
            if loc.count() > 0: loc.first.click()
        page.keyboard.press('Escape'); break
time.sleep(0.5)
print('Filters done. Tiles:', page.locator('.vcb-tile').count())

# Get session IDs
session_ids = [t.text_content().strip() for t in page.locator('.vcb-tile-title').all()]
print(f'Session IDs: {session_ids[:3]}')

# Click tile index 1 (second tile) via JS
print('Clicking tile[1]...')
page.evaluate('''
(function() {
  var tiles = document.querySelectorAll(".vcb-tile");
  if (tiles[1]) tiles[1].dispatchEvent(new MouseEvent("click", {bubbles:true,cancelable:true}));
})()
''')
time.sleep(1.5)

# Check modal state
modal_state = page.evaluate('''
(function() {
  var modal = document.querySelector(".vcb-modal");
  var overlay = document.querySelector(".vcb-modal-overlay");
  var el = modal || overlay;
  if (!el) return {found: false};
  var txt = el.textContent || "";
  var m = txt.match(/(\\d+)\\s*missing/);
  return {
    found: true,
    text: txt.slice(0, 150),
    missing: m ? m[1] : null
  };
})()
''')
print('Modal state:', modal_state)

# Check if form inputs are visible (modal might have auto-expanded)
inputs_visible = page.evaluate('''
(function() {
  var results = [];
  document.querySelectorAll("input").forEach(function(el) {
    var r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0 && r.x >= 0 && r.y >= 0) {
      results.push({placeholder: el.getAttribute("placeholder") || "", x: Math.round(r.x), y: Math.round(r.y)});
    }
  });
  return results;
})()
''')
print('Visible inputs:')
for inp in inputs_visible[:10]:
    if inp['placeholder']:
        print(f'  ({inp["x"]},{inp["y"]}) {inp["placeholder"][:40]}')

# Check buttons for Edit metadata
buttons_info = page.evaluate('''
(function() {
  var results = [];
  document.querySelectorAll("button").forEach(function(b) {
    var txt = (b.textContent || "").trim();
    if (txt.includes("Edit") || txt.includes("Save") || txt.includes("Submit") || txt.includes("metadata")) {
      var r = b.getBoundingClientRect();
      if (r.width > 0) results.push({text: txt.slice(0, 50), x: Math.round(r.x), y: Math.round(r.y)});
    }
  });
  return results;
})()
''')
print('Edit/Save buttons:', buttons_info)

browser.close(); pw.stop()
