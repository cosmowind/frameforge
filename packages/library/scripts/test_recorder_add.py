"""Try duplicate id, empty fields, and other edge cases."""
from playwright.sync_api import sync_playwright
import json

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 2000, "height": 1000}).new_page()
    msgs = []
    page.on("console", lambda m: msgs.append((m.type, m.text)))
    page.on("pageerror", lambda e: msgs.append(("ERR", str(e))))
    page.on("response", lambda r: msgs.append(("HTTP", f"{r.status} {r.url}")) if "/api/dim" in r.url else None)
    page.goto("http://127.0.0.1:5000/", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(800)
    page.evaluate("switchPage('recorders')")
    page.wait_for_timeout(2500)

    # 场景 A: 加行后直接点保存（空 id + 空 name）→ 应失败
    page.evaluate("dimAddRow('recorders')")
    page.wait_for_timeout(300)
    page.evaluate("document.querySelector('section[data-page=\"recorders\"] tbody tr button.btn-success').click()")
    page.wait_for_timeout(1500)
    print("[A] empty add+save → state:")
    print(json.dumps(page.evaluate("""() => ({
      dirty: Array.from(dimPageState.recorders.dirty),
      newKeys: Array.from(dimPageState.recorders.newKeys),
      toast: document.getElementById('toast').textContent,
      toastKind: document.getElementById('toast').className,
    })"""), ensure_ascii=False, indent=2))

    # 场景 B: 输一个已存在的 id → 重复
    page.evaluate("""() => {
      const tr = document.querySelector('section[data-page="recorders"] tbody tr');
      const idInput = tr.querySelector("input[data-field='id']");
      idInput.focus();
      idInput.value = 'op1';  // 已存在
      idInput.dispatchEvent(new Event('input', { bubbles: true }));
      const n = tr.querySelector("input[data-field='name']");
      n.focus(); n.value = '重复id测试';
      n.dispatchEvent(new Event('input', { bubbles: true }));
    }""")
    page.wait_for_timeout(400)
    page.evaluate("document.querySelector('section[data-page=\"recorders\"] tbody tr button.btn-success').click()")
    page.wait_for_timeout(2000)
    print("\n[B] duplicate id → state:")
    print(json.dumps(page.evaluate("""() => ({
      toast: document.getElementById('toast').textContent,
      toastKind: document.getElementById('toast').className,
      rowsLen: dimPageState.recorders.rows.length,
    })"""), ensure_ascii=False, indent=2))

    # 场景 C: 加新行只填 id 不填 name → 缺 name
    page.evaluate("dimAddRow('recorders')")
    page.wait_for_timeout(300)
    page.evaluate("""() => {
      const tr = document.querySelector('section[data-page="recorders"] tbody tr');
      const idInput = tr.querySelector("input[data-field='id']");
      idInput.focus();
      idInput.value = 'no_name_001';
      idInput.dispatchEvent(new Event('input', { bubbles: true }));
    }""")
    page.wait_for_timeout(400)
    # 直接点保存按钮
    page.evaluate("document.querySelector('section[data-page=\"recorders\"] tbody tr button.btn-success').click()")
    page.wait_for_timeout(2000)
    print("\n[C] id-only, no name → state:")
    print(json.dumps(page.evaluate("""() => ({
      toast: document.getElementById('toast').textContent,
      toastKind: document.getElementById('toast').className,
    })"""), ensure_ascii=False, indent=2))

    print("\nHTTP responses:")
    for k, v in [m for m in msgs if m[0] == 'HTTP']:
        print(f"  [{k}] {v}")
    print("\nErrors:")
    for k, v in [m for m in msgs if k == 'error']:
        print(f"  [{k}] {v}")
    browser.close()