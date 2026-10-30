import sys; sys.stdout.reconfigure(encoding='utf-8')
from playwright.sync_api import sync_playwright
import time, re

pw = sync_playwright().start()
browser = pw.chromium.connect_over_cdp('http://localhost:9222')
page = browser.contexts[0].pages[0]

# Re-inject fresh JS
with open('src/scripts/auto_fill_helper.py', 'r', encoding='utf-8') as f:
    content = f.read()
match = re.search(r'INJECT_INIT_JS = r"""(.*?)"""', content, re.DOTALL)
page.evaluate('window.__autoFillInjected = false')
page.evaluate(match.group(1))
page.evaluate('window.__autoFillApiBase = "http://localhost:5000";')

# Fill 3 fields
op = page.locator('input[placeholder="Operator name"]').nth(1)
tk = page.locator('input[placeholder="Task description"]').nth(1)
ev = page.locator('input[placeholder="Environment (room / lighting / setting)"]').nth(1)
op.fill('op6')
tk.fill('faucet')
ev.fill('factory workshop')
time.sleep(0.5)

# Trigger Ctrl+B by dispatching keydown on document (bypasses the need for run() to be on window)
page.evaluate("""
document.dispatchEvent(new KeyboardEvent('keydown', { key: 'b', ctrlKey: true, bubbles: true }))
""")
time.sleep(2.5)

# Check result
status = page.evaluate('document.getElementById("autoFillStatus").textContent')
print('Status:', status)

# Verify text inputs
def check_input(ph):
    loc = page.locator('input[placeholder*="' + ph + '"]').nth(1)
    if loc.is_visible():
        try: return loc.input_value(timeout=2000)
        except: return '(error)'
    return '(not visible)'

check_phs = ['Operator name', 'Task description', 'Standard occupation',
             'Scene / workstation', 'Facility type', 'Environment category',
             'Stable site', 'Months or years performing the job role',
             'Hours recorded that day', 'Total prior collection days',
             'Palm/finger span measurements']
print()
print('Text input values:')
for ph in check_phs:
    val = check_input(ph)
    print(f'  {ph}: {repr(val[:25]) if val and val != "(not visible)" and val != "(error)" else val}')

# Verify selects
select_check_js = """
(function() {
  var results = {};
  var labels = ['age_range', 'gender', 'task_difficulty', 'handedness', 'gloves', 'workforce_type', 'operator-consent'];
  labels.forEach(function(ph) {
    var all = document.querySelectorAll('select');
    for (var i = 0; i < all.length; i++) {
      var el = all[i];
      var r = el.getBoundingClientRect();
      if (r.width <= 0 || r.x < 0) continue;
      var lblEl = el.closest('label');
      if (lblEl && (lblEl.textContent || '').toLowerCase().includes(ph.toLowerCase())) {
        results[ph] = el.value;
        return;
      }
    }
    results[ph] = null;
  });
  return results;
})
"""
select_results = page.evaluate(select_check_js)
print()
print('Select values:')
for k, v in select_results.items():
    print(f'  {k}: {v}')

browser.close()
pw.stop()
