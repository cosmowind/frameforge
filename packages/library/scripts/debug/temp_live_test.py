import sys; sys.stdout.reconfigure(encoding='utf-8')
from playwright.sync_api import sync_playwright
import time, re

pw = sync_playwright().start()
browser = pw.chromium.connect_over_cdp('http://localhost:9222')
page = browser.contexts[0].pages[0]
time.sleep(1)

# Inject JS
with open('src/scripts/auto_fill_helper.py', 'r', encoding='utf-8') as f:
    content = f.read()
match = re.search(r'INJECT_INIT_JS = r"""(.*?)"""', content, re.DOTALL)
page.evaluate(match.group(1))
page.evaluate('window.__autoFillApiBase = "http://localhost:5000";')
time.sleep(0.5)

panel = page.query_selector('#autoFillPanel')
print('Panel:', 'OK' if panel else 'MISSING')

# Fill 3 fields via JS
fill_3 = """
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
    el.dispatchEvent(new Event('input', {bubbles:true}));
    el.dispatchEvent(new Event('change', {bubbles:true}));
  }
  function findVis(ph) {
    var phL = ph.toLowerCase();
    var all = Array.from(document.querySelectorAll('input'));
    for (var i = 0; i < all.length; i++) {
      var el = all[i];
      if (!isVis(el)) continue;
      if ((el.getAttribute('placeholder')||'').toLowerCase().includes(phL)) return el;
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
r = page.evaluate(fill_3)
print('3 fields filled:', r)
time.sleep(0.3)

# Click panel to trigger autofill
page.evaluate("document.querySelector('#autoFillMainRow').click()")
time.sleep(3)

status = page.evaluate('document.getElementById("autoFillStatus").textContent')
print('Status:', status)

# Read all filled values
read_all = """
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
      if ((el.getAttribute('placeholder')||'').toLowerCase().includes(phL)) return el;
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
      if (lbl && (lbl.textContent||'').toLowerCase().includes(ph.toLowerCase())) return el;
    }
    return null;
  }

  var textFields = [
    'Operator name', 'Task description', 'Standard occupation',
    'Scene / workstation', 'Facility type', 'Environment category',
    'Stable site', 'Latitude', 'city', 'country',
    'Months or years performing the job role',
    'Hours recorded that day', 'Total prior collection days',
    'Palm/finger span measurements'
  ];
  var selectFields = ['age_range','gender','task_difficulty','handedness','gloves','workforce_type','operator-consent'];

  var result = {};
  textFields.forEach(function(f) {
    var inp = findVis(f);
    result[f] = inp ? inp.value : '(not found)';
  });
  selectFields.forEach(function(f) {
    var sel = getSelect(f);
    result[f] = sel ? sel.value : '(not found)';
  });
  return result;
})()
"""
values = page.evaluate(read_all)
print()
print('=== Autofill Results ===')
for k, v in values.items():
    if v and v != '(not found)':
        print(f'  {k}: {repr(v[:40]) if len(str(v)) < 40 else str(v)}')

browser.close()
pw.stop()
