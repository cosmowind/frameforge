import sys; sys.stdout.reconfigure(encoding='utf-8')
from playwright.sync_api import sync_playwright
import time, re

pw = sync_playwright().start()
browser = pw.chromium.connect_over_cdp('http://localhost:9222')
page = browser.contexts[0].pages[0]
time.sleep(0.5)

# Inject autofill JS
with open('src/scripts/auto_fill_helper.py', 'r', encoding='utf-8') as f:
    content = f.read()
match = re.search(r'INJECT_INIT_JS = r"""(.*?)"""', content, re.DOTALL)
page.evaluate(match.group(1))
page.evaluate('window.__autoFillApiBase = "http://localhost:5000";')
time.sleep(0.5)
print('JS injected, panel:', page.evaluate("!!document.getElementById('autoFillPanel')"))

# Go to upload-history
page.goto('https://publish.example.com/vendors?tab=upload-history', timeout=15000)
page.wait_for_load_state('networkidle', timeout=8000)
time.sleep(1)

# Set filters
page.evaluate('''
(function() {
    var selects = document.querySelectorAll("select");
    for (var i = 0; i < selects.length; i++) {
        var opts = Array.from(selects[i].options).map(function(o){ return o.textContent.trim(); });
        if (opts.some(function(o){ return o.indexOf("Stereo") >= 0; })) {
            selects[i].value = "stereo"; selects[i].dispatchEvent(new Event("change", {bubbles:true})); break;
        }
    }
})()
''')
time.sleep(0.3)
page.evaluate('''
(function() {
    var btns = document.querySelectorAll("button");
    for (var i = 0; i < btns.length; i++) {
        if ((btns[i].textContent||"").indexOf("Excludes") >= 0) { btns[i].click(); return; }
    }
})()
''')
time.sleep(0.5)
for tag in ["review_reject", "vendor-delete", "wipe"]:
    page.evaluate("(function() { var btns = document.querySelectorAll('button'); for (var i = 0; i < btns.length; i++) { if ((btns[i].textContent||'').indexOf('" + tag + "') >= 0) { btns[i].click(); return; } } })()")
    time.sleep(0.2)
page.keyboard.press("Escape")
time.sleep(0.5)

# Click tile[0] via media button
media = page.evaluate("(function() { var tile = document.querySelector('.vcb-tile'); var m = tile && tile.querySelector('.vcb-tile-media'); if (!m) return null; var r = m.getBoundingClientRect(); return {x: r.x+r.width/2, y: r.y+r.height/2}; })()")
print('Media center:', media)
page.mouse.click(media['x'], media['y'])
time.sleep(1.5)

# Find Edit button inside modal
edit = page.evaluate("""
(function() {
    var modal = document.querySelector(".vcb-modal-overlay");
    if (!modal) return null;
    var btns = modal.querySelectorAll("button");
    for (var i = 0; i < btns.length; i++) {
        var txt = (btns[i].textContent||"").trim();
        if (txt.indexOf("Edit") >= 0) {
            var r = btns[i].getBoundingClientRect();
            return {text: txt, x: Math.round(r.x), y: Math.round(r.y)};
        }
    }
    return null;
})()
""")
print('Edit button:', edit)

if edit:
    page.mouse.click(edit['x'], edit['y'])
    time.sleep(2)
    print('Clicked Edit, URL:', page.url)

    # Fill 3 fields
    fill3 = page.evaluate("""
    (function() {
        function isVis(el) {
            if (!el) return false;
            var r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0 && r.x >= 0 && r.y >= 0;
        }
        function setVal(el, v) {
            if (!el) return;
            var proto = Object.getPrototypeOf(el);
            var d = Object.getOwnPropertyDescriptor(proto, "value");
            if (d && d.set) d.set.call(el, v); else el.value = v;
            el.dispatchEvent(new Event("input", {bubbles:true}));
            el.dispatchEvent(new Event("change", {bubbles:true}));
        }
        function findVis(ph) {
            var phL = ph.toLowerCase();
            return Array.from(document.querySelectorAll("input")).find(function(el) {
                if (!isVis(el)) return false;
                return (el.getAttribute("placeholder")||"").toLowerCase().indexOf(phL) >= 0;
            }) || null;
        }
        var op = findVis("Operator name");
        var tk = findVis("Task description");
        var ev = findVis("Environment");
        if (op) setVal(op, "op6"); else return "op missing";
        if (tk) setVal(tk, "faucet"); else return "tk missing";
        if (ev) setVal(ev, "factory workshop"); else return "ev missing";
        return "filled";
    })()
    """)
    print('Fill 3 result:', fill3)

    # Trigger autofill
    page.evaluate("(function() { var btn = document.getElementById('autoFillMainRow'); if (btn) btn.click(); })()")
    time.sleep(3)
    status = page.evaluate("document.getElementById('autoFillStatus').textContent")
    print('Status:', status)

    # Show results
    results = page.evaluate("""
    (function() {
        function isVis(el) {
            if (!el) return false;
            var r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0 && r.x >= 0 && r.y >= 0;
        }
        function findVis(ph) {
            var phL = ph.toLowerCase();
            return Array.from(document.querySelectorAll("input")).find(function(el) {
                return isVis(el) && (el.getAttribute("placeholder")||"").toLowerCase().indexOf(phL) >= 0;
            }) || null;
        }
        function getSel(ph) {
            var phL = ph.toLowerCase();
            return Array.from(document.querySelectorAll("select")).find(function(el) {
                if (!isVis(el)) return false;
                var lbl = el.closest("label");
                return lbl && (lbl.textContent||"").toLowerCase().indexOf(phL) >= 0;
            }) || null;
        }
        var r = {};
        var texts = ["Operator name","Task description","Standard occupation","Scene / workstation","Facility type","Environment category","Stable site","city","country"];
        texts.forEach(function(f) { var inp = findVis(f); r[f] = inp ? inp.value : "(not found)"; });
        var selects = ["age_range","gender","task_difficulty","handedness","gloves","workforce_type"];
        selects.forEach(function(f) { var sel = getSel(f); r[f] = sel ? sel.value : "(not found)"; });
        return r;
    })()
    """)
    print()
    print("Autofill results:")
    for (k, v) in results.items():
        if v and v != "(not found)":
            print("  {}: {}".format(k, v[:30]))

browser.close()
pw.stop()
