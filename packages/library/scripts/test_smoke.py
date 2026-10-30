"""Smoke test: page loads + recorders add works end-to-end."""
from playwright.sync_api import sync_playwright
import json

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1600, "height": 900}).new_page()
    page_errors = []
    page.on("pageerror", lambda e: page_errors.append(str(e)))
    page.goto("http://127.0.0.1:5000/", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(1500)
    page.screenshot(path="scripts/shots/smoke_01_home.png", full_page=False)

    # 切到录入员
    page.evaluate("switchPage('recorders')")
    page.wait_for_timeout(2500)
    page.screenshot(path="scripts/shots/smoke_02_recorders.png", full_page=False)

    state = page.evaluate("""() => ({
      tabBtnExists: !!document.querySelector(\"button.tab[data-page='recorders']\"),
      panelVisible: !document.querySelector(\"section[data-page='recorders']\").hidden,
      rowCount: document.querySelectorAll(\"section[data-page='recorders'] tbody tr\").length,
      schemaLen: dimPageState.recorders.schema.length,
      rowsLen: dimPageState.recorders.rows.length,
      headers: Array.from(document.querySelectorAll(\"section[data-page='recorders'] thead th\")).map(th => th.textContent.trim()),
    })""")
    print("[recorders page state]")
    print(json.dumps(state, ensure_ascii=False, indent=2))

    # 点 +新增，填 id+name，保存
    page.evaluate("dimAddRow('recorders')")
    page.wait_for_timeout(300)
    page.evaluate("""() => {
      const tr = document.querySelector('section[data-page="recorders"] tbody tr');
      const idInput = tr.querySelector("input[data-field='id']");
      idInput.focus();
      idInput.value = 'smoke_test_001';
      idInput.dispatchEvent(new Event('input', { bubbles: true }));
      const n = tr.querySelector("input[data-field='name']");
      n.focus(); n.value = '烟测员';
      n.dispatchEvent(new Event('input', { bubbles: true }));
    }""")
    page.wait_for_timeout(400)
    page.evaluate("""() => {
      document.querySelector('section[data-page="recorders"] tbody tr button.btn-success').click();
    }""")
    page.wait_for_timeout(2000)
    page.screenshot(path="scripts/shots/smoke_03_after_save.png", full_page=False)

    backend = page.evaluate("""async () => {
      const r = await fetch('/api/dim/recorders');
      const d = await r.json();
      return { count: d.count, hasNew: d.rows.some(r => r.id === 'smoke_test_001') };
    }""")
    toast = page.evaluate("() => document.getElementById('toast').textContent")
    print("\n[backend after save]")
    print(json.dumps(backend, ensure_ascii=False, indent=2))
    print(f"[toast] {toast}")
    print(f"[page errors] {page_errors}")

    browser.close()
    print("\n✓ DONE")