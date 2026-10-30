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

# Fill 3 fields via JS directly (bypass Playwright fill)
fill_3_fields = """
(function() {
  function isVis(el) {
    if (!el) return false;
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && r.x >= 0 && r.y >= 0;
  }
  function setVal(el, v) {
    if (!el) return;
    var proto = Object.getPrototypeOf(el);
    var d = Object.getOwnPropertyDescriptor(proto, 'value');
    if (d && d.set) d.set.call(el, v); else el.value = v;
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
  }
  function findVis(ph) {
    var phL = ph.toLowerCase();
    var all = Array.from(document.querySelectorAll('input'));
    for (var i = 0; i < all.length; i++) {
      var el = all[i];
      if (!isVis(el)) continue;
      if ((el.getAttribute('placeholder') || '').toLowerCase().includes(phL)) return el;
    }
    return null;
  }
  var op = findVis('Operator name');
  var tk = findVis('Task description');
  var ev = findVis('Environment');
  if (op) setVal(op, 'op6');
  if (tk) setVal(tk, 'faucet');
  if (ev) setVal(ev, 'factory workshop');
  return { op: op ? op.value : null, tk: tk ? tk.value : null, ev: ev ? ev.value : null };
})()
"""
result = page.evaluate(fill_3_fields)
print('Filled 3 fields via JS:', result)

time.sleep(0.3)

status_filled = page.evaluate('document.getElementById("autoFillStatus").textContent')
print('Status after fill:', status_filled)

# Click the panel button to trigger run()
page.evaluate("""
(function() {
  var btn = document.querySelector('#autoFillMainRow');
  if (btn) btn.click();
})()
""")
time.sleep(3)

status_after = page.evaluate('document.getElementById("autoFillStatus").textContent')
print('Status after panel click:', status_after)

# Check field values
check_js = """
(function() {
  function isVis(el) {
    if (!el) return false;
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && r.x >= 0 && r.y >= 0;
  }
  function findVis(ph) {
    var phL = ph.toLowerCase();
    var all = Array.from(document.querySelectorAll('input'));
    for (var i = 0; i < all.length; i++) {
      var el = all[i];
      if (!isVis(el)) continue;
      if ((el.getAttribute('placeholder') || '').toLowerCase().includes(phL)) return el;
    }
    return null;
  }
  function getSelect(ph) {
    var all = document.querySelectorAll('select');
    for (var i = 0; i < all.length; i++) {
      var el = all[i];
      var r = el.getBoundingClientRect();
      if (r.width <= 0 || r.x < 0) continue;
      var lbl = el.closest('label');
      if (lbl && (lbl.textContent || '').toLowerCase().includes(ph.toLowerCase())) return el;
    }
    return null;
  }
  var r = {};
  var fields = ['Operator name', 'Task description', 'Standard occupation',
                'Scene / workstation', 'Facility type', 'Environment category',
                'Stable site', 'city', 'country', 'Latitude'];
  fields.forEach(function(f) {
    var inp = findVis(f);
    r[f] = inp ? inp.value : '(not found)';
  });
  var selects = ['age_range', 'gender', 'task_difficulty', 'handedness', 'gloves', 'workforce_type'];
  selects.forEach(function(s) {
    var sel = getSelect(s);
    r[s] = sel ? sel.value : '(not found)';
  });
  return r;
})()
"""
values = page.evaluate(check_js)
print()
print('Field values:')
for k, v in values.items():
    print(f'  {k}: {repr(v[:30]) if isinstance(v, str) and v != "(not found)" else v}')

browser.close()
pw.stop()
