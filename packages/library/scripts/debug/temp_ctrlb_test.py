import sys; sys.stdout.reconfigure(encoding='utf-8')
from playwright.sync_api import sync_playwright
import time, re

pw = sync_playwright().start()
browser = pw.chromium.connect_over_cdp('http://localhost:9222')
page = browser.contexts[0].pages[0]

# Inject JS
with open('src/scripts/auto_fill_helper.py', 'r', encoding='utf-8') as f:
    content = f.read()
match = re.search(r'INJECT_INIT_JS = r"""(.*?)"""', content, re.DOTALL)
page.evaluate(match.group(1))
page.evaluate('window.__autoFillApiBase = "http://localhost:5000";')
time.sleep(0.5)

panel = page.query_selector('#autoFillPanel')
print('Panel:', 'OK' if panel else 'MISSING')
print('Status:', page.evaluate('document.getElementById("autoFillStatus").textContent'))

# Fill 3 fields
op = page.locator('input[placeholder="Operator name"]').nth(1)
tk = page.locator('input[placeholder="Task description"]').nth(1)
ev = page.locator('input[placeholder="Environment (room / lighting / setting)"]').nth(1)
op.fill('op6')
tk.fill('faucet')
ev.fill('factory workshop')
time.sleep(0.3)

status_filled = page.evaluate('document.getElementById("autoFillStatus").textContent')
print('Status after fill:', status_filled)

# Expose run() on window by modifying the injected JS context
# We do this by injecting a helper that calls run()
page.evaluate("""
(function() {
  // Find the autoFill panel and click it to trigger run
  var panel = document.getElementById('autoFillPanel');
  if (panel) {
    var btn = panel.querySelector('#autoFillMainRow');
    if (btn) btn.click();
  }
})()
""")
time.sleep(3)

status_after = page.evaluate('document.getElementById("autoFillStatus").textContent')
print('Status after panel click:', status_after)

browser.close()
pw.stop()
