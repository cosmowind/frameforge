# ────────────────────────────────────────────────────────────────
# auto_fill_helper.py — 视频补录参数助手（浏览器端）
#
# 业务背景：
#   用户在 publish.example.com 上传页面手填 3 个 free-text 字段
#   (operator-name / task-description / environment-description)
#   后，需要程序自动补完 20+ 个其他字段。
#   本脚本用 Playwright 启动一个受控 Chrome，注入一个"🚀 一键补全"按钮。
#   用户填 3 个字段、点按钮、脚本调用本地 Flask API（http://localhost:5000）
#   获取完整 fields 并填到表单；用户继续看下一个视频。
#
# 用法：
#   # 1) 先启动 video_manager（这个工具的 Flask 服务，端口 5000）
#   python src/run.py
#
#   # 2) 在另一个终端跑本脚本（需先 pip install playwright && playwright install chromium）
#   python src/scripts/auto_fill_helper.py
#   python src/scripts/auto_fill_helper.py --url https://publish.example.com/upload
#   python src/scripts/auto_fill_helper.py --api http://localhost:5000
#
# 流程：
#   - 启动 chromium（非 headless 模式，保留 cookie/login 状态）
#   - 打开上传页（默认 https://publish.example.com，如已登录会直接进）
#   - 注入"🚀 一键补全"浮动按钮 + 候选下拉提示
#   - 用户填 3 字段 → 点按钮 → 脚本调 /api/auto-fill → 填完 20+ 字段
#   - 按钮在用户提交/导航前持续可见
# ────────────────────────────────────────────────────────────────

from __future__ import annotations

import argparse
import json
import sys
import time

# ── 标准路径引导 ──
import os
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "src"))


# ── 浏览器内运行的 JS ──

# 注入脚本：定位 3 个 free-text 输入框，加 🚀 浮窗 + Ctrl+B 快捷键
# 触发后：读 3 个 input 值 → 调本地 /api/auto-fill → 填 20+ 字段
# publish.example.com 表单用 placeholder 属性定位，每个字段在 DOM 中有两个 input（第一个隐藏），取第二个可见
INJECT_INIT_JS = r"""
(() => {
  if (window.__autoFillInjected) return;
  window.__autoFillInjected = true;

  // ── 工具函数 ──
  function isVisible(el) {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && r.x >= 0 && r.y >= 0;
  }

  function setReactValue(el, value) {
    if (!el) return false;
    const proto = Object.getPrototypeOf(el);
    const desc = Object.getOwnPropertyDescriptor(proto, 'value');
    if (desc && desc.set) { desc.set.call(el, value); }
    else { el.value = value; }
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }

  function findInputs(ph) {
    if (!ph) return [];
    const phLower = ph.toLowerCase();
    return Array.from(document.querySelectorAll('input')).filter(
      el => (el.getAttribute('placeholder') || '').toLowerCase().includes(phLower)
    );
  }
  function findVisibleInput(ph) {
    const els = findInputs(ph);
    for (const el of els) { if (isVisible(el)) return el; }
    return els[0] || null;
  }

  function findVisibleSelect(labelText) {
    const lower = labelText.toLowerCase();
    return Array.from(document.querySelectorAll('select')).find(el => {
      if (!isVisible(el)) return false;
      const lbl = el.closest('label');
      return lbl && (lbl.textContent || '').toLowerCase().includes(lower);
    }) || null;
  }

  function setSelectValue(sel, value) {
    if (!sel) return false;
    const vLower = String(value).toLowerCase();
    const opts = Array.from(sel.options);
    for (const o of opts) {
      if (o.value.toLowerCase() === vLower ||
          (o.textContent || '').toLowerCase().includes(vLower)) {
        sel.value = o.value;
        sel.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
      }
    }
    return false;
  }

  // ── 3 个 free-text 字段定位器 ──
  function findOperatorInput() { return findVisibleInput('Operator name'); }
  function findTaskInput() { return findVisibleInput('Task description'); }
  function findEnvInput() { return findVisibleInput('Environment'); }
  window.__autoFillLocate = { findOperatorInput, findTaskInput, findEnvInput };

  // ── 字段 → placeholder/label 关键字映射 ──
  const FIELD_PH = {
    operator_name:           'Operator name',
    operator_job:            'Standard occupation',
    task_description:        'Task description',
    environment_description: 'Environment',
    city:                   'city',
    state_province:         'state',
    country:                'country',
    location_address:       'Stable site',
    environment:            'Environment category',
    facility_venue:         'Facility type',
    scene:                  'Scene / workstation',
    business_type:          'Sub-industry',
    business_name:           'Registered or public-facing name',
    age_range:             'age_range',
    gender:                'gender',
    handedness:            'handedness',
    gloves:                'gloves',
    workforce_type:        'workforce_type',
    role_experience:        'Months or years performing the job role',
    task_experience:        'Months or years performing the specific',
    recording_hours_today: 'Hours recorded that day',
    recording_experience_days: 'Total prior recording days',
    hand_size_cm:           'Palm/finger span measurements',
    task_difficulty:        'task_difficulty',
    operator_consent:       'operator-consent',
    gps_coordinates:        'Latitude',
  };

  // select 字段列表（通过 label 定位）
  const SELECT_KEYS = new Set([
    'age_range', 'gender', 'handedness', 'gloves',
    'workforce_type', 'task_difficulty', 'operator_consent',
  ]);

  // ── 浮动面板（🚀 + Ctrl+B） ──
  const panel = document.createElement('div');
  panel.id = 'autoFillPanel';
  panel.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:2147483647;background:#1677ff;color:white;padding:10px 14px;border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,.25);font:13px/1.4 -apple-system,Segoe UI,sans-serif;min-width:240px;user-select:none;';
  panel.innerHTML = '<div id="autoFillMainRow" style="font-weight:600;display:flex;align-items:center;gap:8px;cursor:pointer;"><span>🚀</span><span>一键补全</span><span style="margin-left:auto;font-size:10px;background:rgba(255,255,255,.25);padding:2px 6px;border-radius:3px;font-family:monospace;">Ctrl+B</span></div><div id="autoFillStatus" style="font-size:11px;opacity:.95;">Ready - fill 3 fields and press Ctrl+B</div>';
  document.body.appendChild(panel);

  const statusEl = panel.querySelector('#autoFillStatus');
  panel.querySelector('#autoFillMainRow').addEventListener('click', run);

  // ── 调本地 Flask /api/auto-fill ──
  async function callApi(payload) {
    const apiBase = window.__autoFillApiBase || 'http://localhost:5000';
    const r = await fetch(apiBase + '/api/auto-fill', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!r.ok) throw new Error('API ' + r.status + ': ' + await r.text());
    return await r.json();
  }

  // ── 主逻辑：读 3 字段 → API → 填 20+ 字段 ──
  async function run() {
    try {
      const op = findOperatorInput();
      const tk = findTaskInput();
      const ev = findEnvInput();
      const operator_name = (op && op.value) || '';
      const task_description = (tk && tk.value) || '';
      const environment_description = (ev && ev.value) || '';
      if (!operator_name && !task_description && !environment_description) {
        statusEl.textContent = 'Fill 3 fields first, then Ctrl+B';
        return;
      }
      statusEl.textContent = 'Calling API...';
      const data = await callApi({ operator_name, task_description, environment_description });
      if (!data.ok) {
        statusEl.textContent = 'API error: ' + (data.error || 'unknown');
        return;
      }
      const fields = data.fields || {};
      let filled = 0, skipped = 0, errors = [];
      for (const [key, val] of Object.entries(fields)) {
        if (!val || key.startsWith('_')) { skipped++; continue; }
        const ph = FIELD_PH[key];
        if (!ph) { skipped++; continue; }
        let ok = false;
        if (SELECT_KEYS.has(key)) {
          const sel = findVisibleSelect(ph);
          if (sel) { ok = setSelectValue(sel, String(val)); }
        } else {
          const input = findVisibleInput(ph);
          if (input) { setReactValue(input, String(val)); ok = true; }
        }
        if (ok) filled++; else { errors.push(key + '(' + ph + ')'); skipped++; }
      }
      const unmatched = (data.unmatched || []).join(', ') || 'none';
      statusEl.innerHTML = '<div>Filled ' + filled + ' fields, skipped ' + skipped + '</div><div style="font-size:10px;opacity:.8;">Unmatched: ' + unmatched + '</div><div style="font-size:10px;opacity:.8;">Missing: ' + (errors.length ? errors.join(', ') : 'none') + '</div>';
      if (window.__autoFillVideoPath) {
        fetch((window.__autoFillApiBase || 'http://localhost:5000') + '/api/auto-fill/apply', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ video_path: window.__autoFillVideoPath, matched: data.matched }),
        }).catch(function() {});
      }
    } catch(e) {
      statusEl.textContent = 'Error: ' + e.message;
    }
  }

  // ── Ctrl+B 快捷键（编辑框外层触发） ──
  document.addEventListener('keydown', function(e) {
    var isTrigger = (e.ctrlKey || e.metaKey) && (e.key === 'b' || e.key === 'B');
    if (!isTrigger) return;
    var tag = (e.target && e.target.tagName || '').toLowerCase();
    var inEditable = ['input', 'textarea', 'select'].indexOf(tag) !== -1 && e.target.type !== 'button';
    if (inEditable) return;
    e.preventDefault();
    e.stopPropagation();
    run();
  });

  // ── 状态更新 ──
  function bindStatus() {
    var op = findOperatorInput(), tk = findTaskInput(), ev = findEnvInput();
    function update() {
      var has = (op && op.value) || (tk && tk.value) || (ev && ev.value);
      if (statusEl.textContent.indexOf('Ready') !== -1 || statusEl.textContent.indexOf('fill') !== -1) {
        statusEl.textContent = has ? 'Ready - press Ctrl+B' : 'Fill 3 fields, then Ctrl+B';
      }
    }
    [op, tk, ev].filter(Boolean).forEach(function(i) { i.addEventListener('input', update); });
  }
  setTimeout(bindStatus, 500);
})();
"""


def _try_import_playwright():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        print("Need to install playwright:  pip install playwright", file=sys.stderr)
        print("(For mode A only) also run:  playwright install chromium", file=sys.stderr)
        print("Mode B (--connect) does NOT need chromium install.", file=sys.stderr)
        raise


def main():
    p = argparse.ArgumentParser(
        description="视频补录参数助手（注入 Ctrl+B 快捷键到 publish.example.com 页面）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
两种模式：

  模式 A（默认）：Playwright 启动 Chromium
    第一次需装：pip install playwright && playwright install chromium
    一次性登录 publish.example.com；想保留登录态用 --user-data-dir
    适用：你没有常用 Chrome，或愿意用独立窗口

  模式 B（推荐）：连接你已打开的 Chrome（CDP）
    1) 关闭所有 Chrome 窗口
    2) 用调试端口重启：
         Windows:  start chrome.exe --remote-debugging-port=9222
         Mac:      /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222
         Linux:    google-chrome --remote-debugging-port=9222
    3) 在 Chrome 里打开 publish.example.com 并登录
    4) 跑：python auto_fill_helper.py --connect
    适用：你已经有登录态的 Chrome，想继续用扩展/书签
""")
    p.add_argument("--url", default="https://publish.example.com",
                   help="[模式A] 目标上传页 URL（默认 https://publish.example.com）")
    p.add_argument("--api", default="http://localhost:5000",
                   help="本地 Flask API 地址（默认 http://localhost:5000）")
    p.add_argument("--user-data-dir", default=None,
                   help="[模式A] Chrome 用户数据目录（保留登录态）")
    p.add_argument("--headless", action="store_true",
                   help="[模式A] 无头模式（默认有头）")
    p.add_argument("--connect", action="store_true",
                   help="[模式B] 连用户已打开的 Chrome（CDP 9222 端口）")
    p.add_argument("--cdp-url", default="http://localhost:9222",
                   help="[模式B] CDP 地址（默认 http://localhost:9222）")
    p.add_argument("--video-path", default=None,
                   help="把 matched 写回 video_manager.csv 时用的 path（可选）")
    args = p.parse_args()

    sync_playwright = _try_import_playwright()

    init_script = (
        f"window.__autoFillApiBase = {json.dumps(args.api)};"
        f"window.__autoFillVideoPath = {json.dumps(args.video_path or '')};"
    )

    with sync_playwright() as pw:
        if args.connect:
            # ── 模式 B：CDP 连接用户已有 Chrome ──
            print(f"[CONNECT] Connecting to your Chrome at {args.cdp_url}")
            try:
                browser = pw.chromium.connect_over_cdp(args.cdp_url)
            except Exception as e:
                print(f"[ERROR] Cannot connect to {args.cdp_url}: {e}", file=sys.stderr)
                print("        Please start Chrome with --remote-debugging-port=9222 first.", file=sys.stderr)
                print("        Windows:  start chrome.exe --remote-debugging-port=9222", file=sys.stderr)
                print('        Mac:      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222', file=sys.stderr)
                print("        Linux:    google-chrome --remote-debugging-port=9222", file=sys.stderr)
                return 1

            # 找所有已打开的 context 和 page
            contexts = browser.contexts
            all_pages = []
            for ctx in contexts:
                all_pages.extend(ctx.pages)

            # 优先找 publish.example.com 标签页，否则用当前活动 page，最后一个 page
            target = None
            for p_ in all_pages:
                if "frameforge" in p_.url.lower() or "upload" in p_.url.lower():
                    target = p_; break
            if target is None:
                for ctx in contexts:
                    for p_ in ctx.pages:
                        if p_.url and p_.url != "about:blank":
                            target = p_
            if target is None and all_pages:
                target = all_pages[0]
            if target is None:
                print("[WARN] Your Chrome has no open tabs. Open publish.example.com first.")
                return 1

            # 注入 init script
            for ctx in contexts:
                ctx.add_init_script(init_script)
            target.add_init_script(init_script)
            target.evaluate(INJECT_INIT_JS)

            print(f"[OK] Injected into tab: {target.url[:80]}")
            print(f"     Now go to that tab, fill 3 fields, press Ctrl+B.")
            print(f"     Press Ctrl+C to exit (your Chrome will stay open).")
            try:
                while True:
                    time.sleep(5)
            except KeyboardInterrupt:
                print("\n[EXIT] Helper stopped.")
            return 0

        # ── 模式 A：Playwright 启动 Chromium ──
        print(f"[LAUNCH] Starting browser: {args.url}")
        print(f"         API: {args.api}")
        if args.user_data_dir:
            print(f"         user-data-dir: {args.user_data_dir}")
        print(f"         Fill 3 free-text fields, then press Ctrl+B (or click the floating button).")
        print(f"         Press Ctrl+C to exit.")

        launch_kwargs = {"headless": args.headless}
        browser = pw.chromium.launch(**launch_kwargs)

        if args.user_data_dir:
            context = browser.new_context(
                user_data_dir=args.user_data_dir,
                viewport={"width": 1400, "height": 900},
            )
        else:
            context = browser.new_context(viewport={"width": 1400, "height": 900})

        page = context.new_page()
        page.add_init_script(init_script)
        page.goto(args.url, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        page.evaluate(INJECT_INIT_JS)
        print("[OK] Floating button injected. Browser is yours. Ctrl+C to exit.")
        try:
            while True:
                time.sleep(5)
        except KeyboardInterrupt:
            print("\n[EXIT] Helper stopped.")
        finally:
            context.close()
            browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())