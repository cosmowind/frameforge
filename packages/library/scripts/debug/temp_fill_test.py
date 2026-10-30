import sys; sys.stdout.reconfigure(encoding='utf-8')
from playwright.sync_api import sync_playwright
import time, json, urllib.request

pw = sync_playwright().start()
browser = pw.chromium.connect_over_cdp('http://localhost:9222')
page = browser.contexts[0].pages[0]

# Get API fields
req = urllib.request.Request(
    'http://localhost:5000/api/auto-fill',
    data=json.dumps({'operator_name': 'op6', 'task_description': 'faucet', 'environment_description': 'factory workshop'}).encode(),
    headers={'Content-Type': 'application/json'}, method='POST'
)
with urllib.request.urlopen(req, timeout=10) as r:
    result = json.loads(r.read())
fields = result['fields']
print('Matched:', result['matched'])
print('Unmatched:', result.get('unmatched'))

# Build FIELD_CONFIG
FIELD_CONFIG = {
    'operator_name':          ('input', 'Operator name'),
    'operator_job':           ('input', 'Standard occupation'),
    'task_description':        ('input', 'Task description'),
    'environment_description': ('input', 'Environment'),
    'city':                   ('input', 'city'),
    'state_province':         ('input', 'state'),
    'country':               ('input', 'country'),
    'location_address':       ('input', 'Stable site'),
    'environment':           ('input', 'Environment category'),
    'facility_venue':        ('input', 'Facility type'),
    'scene':                 ('input', 'Scene / workstation'),
    'business_type':         ('input', 'Sub-industry'),
    'business_name':          ('input', 'Registered or public-facing'),
    'age_range':             ('select', 'age_range'),
    'gender':                ('select', 'gender'),
    'handedness':            ('select', 'handedness'),
    'gloves':                ('select', 'gloves'),
    'workforce_type':        ('select', 'workforce_type'),
    'role_experience':        ('input', 'Months or years performing the job role'),
    'task_experience':       ('input', 'Months or years performing the specific'),
    'collection_hours_today':('input', 'Hours recorded'),
    'collection_experience_days':('input', 'Total prior collection days'),
    'hand_size_cm':          ('input', 'Palm'),
    'task_difficulty':       ('select', 'task_difficulty'),
    'operator_consent':      ('select', 'operator-consent'),
}

fields_json = json.dumps(fields)
config_json = json.dumps(FIELD_CONFIG)

# Write JS to temp file
js_code = f"""
(function() {{
  var fieldMap = {fields_json};
  var FIELD_CONFIG = {config_json};

  function isVisible(el) {{
    if (!el) return false;
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && r.x >= 0 && r.y >= 0;
  }}

  function setReactValue(el, value) {{
    if (!el) return false;
    var proto = Object.getPrototypeOf(el);
    var desc = Object.getOwnPropertyDescriptor(proto, "value");
    if (desc && desc.set) {{ desc.set.call(el, value); }}
    else {{ el.value = value; }}
    el.dispatchEvent(new Event("input", {{ bubbles: true }}));
    el.dispatchEvent(new Event("change", {{ bubbles: true }}));
    return true;
  }}

  function findVisibleInput(phLower) {{
    var all = Array.from(document.querySelectorAll("input"));
    for (var i = 0; i < all.length; i++) {{
      var el = all[i];
      if (!isVisible(el)) continue;
      var p = (el.getAttribute("placeholder") || "").toLowerCase();
      if (p.includes(phLower)) return el;
    }}
    return null;
  }}

  function findVisibleSelect(labelText) {{
    var all = Array.from(document.querySelectorAll("select"));
    for (var i = 0; i < all.length; i++) {{
      var el = all[i];
      if (!isVisible(el)) continue;
      var lblEl = el.closest("label");
      if (lblEl && (lblEl.textContent || "").toLowerCase().includes(labelText.toLowerCase())) {{
        return el;
      }}
    }}
    return null;
  }}

  function setSelectValue(sel, value) {{
    if (!sel) return false;
    var opts = Array.from(sel.options);
    var vLower = String(value).toLowerCase();
    for (var i = 0; i < opts.length; i++) {{
      if (opts[i].value.toLowerCase() === vLower) {{
        sel.value = opts[i].value;
        sel.dispatchEvent(new Event("change", {{ bubbles: true }}));
        return true;
      }}
    }}
    for (var i = 0; i < opts.length; i++) {{
      if ((opts[i].textContent || "").toLowerCase().includes(vLower) ||
          (opts[i].value && opts[i].value.toLowerCase().includes(vLower))) {{
        sel.value = opts[i].value;
        sel.dispatchEvent(new Event("change", {{ bubbles: true }}));
        return true;
      }}
    }}
    return false;
  }}

  var filled = 0, skipped = 0, errors = [];
  for (var key in fieldMap) {{
    if (!fieldMap.hasOwnProperty(key) || key.startsWith("_")) {{ skipped++; continue; }}
    var value = fieldMap[key];
    if (!value) {{ skipped++; continue; }}
    var config = FIELD_CONFIG[key];
    if (!config) {{ skipped++; continue; }}
    var tag = config[0], labelText = config[1];
    var ok = false;
    if (tag === "input") {{
      var input = findVisibleInput(labelText.toLowerCase());
      if (input) {{ setReactValue(input, String(value)); ok = true; }}
    }} else if (tag === "select") {{
      var sel = findVisibleSelect(labelText);
      if (sel) {{ ok = setSelectValue(sel, String(value)); }}
    }}
    if (ok) filled++; else {{ errors.push(key + "(" + labelText + ")"); skipped++; }}
  }}
  window.__fillResult = {{ filled: filled, skipped: skipped, errors: errors }};
}})()
"""

with open('temp_autofill.js', 'w', encoding='utf-8') as f:
    f.write(js_code)

page.evaluate(js_code)
time.sleep(1.5)

res = page.evaluate('window.__fillResult')
print('Fill result:', res)
print()

# Verify text inputs
print('Text input values:')
for ph in ['Operator name', 'Task description', 'city', 'country', 'Standard occupation',
           'Scene / workstation', 'Facility type', 'Environment category',
           'Stable site', 'Months or years performing the job role']:
    try:
        loc = page.locator('input[placeholder*="' + ph + '"]').nth(1)
        if loc.is_visible():
            val = loc.input_value(timeout=2000)
            print(f'  {ph}: {repr(val[:25]) if val else "(empty)"}')
        else:
            print(f'  {ph}: (not visible)')
    except Exception as e:
        print(f'  {ph}: error')

# Verify selects
print()
print('Select values:')
for ph, expected_key in [('age_range', '20-25'), ('gender', 'male'), ('task_difficulty', 'hard'),
                          ('operator_consent', 'yes'), ('handedness', 'right'), ('gloves', 'no'),
                          ('workforce_type', 'real_worker')]:
    try:
        sel_result = page.evaluate("""
        (function(ph) {
          var all = document.querySelectorAll("select");
          for (var i = 0; i < all.length; i++) {
            var el = all[i];
            var r = el.getBoundingClientRect();
            if (r.width <= 0 || r.x < 0) continue;
            var lblEl = el.closest("label");
            if (lblEl && (lblEl.textContent || "").toLowerCase().includes(ph.toLowerCase())) {
              return { value: el.value };
            }
          }
          return null;
        })
        """, ph)
        if sel_result:
            print(f'  {ph}: value={sel_result["value"]}')
        else:
            print(f'  {ph}: (not found)')
    except Exception as e:
        print(f'  {ph}: {e}')

browser.close()
pw.stop()
