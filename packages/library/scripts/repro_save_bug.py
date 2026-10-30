"""Repro v5: 严格走 dropdown 选择路径，看是否触发 save."""
import asyncio, json, time
from playwright.async_api import async_playwright
import psycopg2

VIDEO_URL = "http://127.0.0.1:5000/"
DSN = "postgresql://ffuser:changeme@db.example.com:5432/video_manager"
TBL = "videos"

def pick_path():
    with psycopg2.connect(DSN) as c, c.cursor() as cur:
        cur.execute(f"SELECT path FROM {TBL} WHERE task_id IS NOT NULL AND task_id != '' LIMIT 1")
        return cur.fetchone()[0]

def get_row(path):
    with psycopg2.connect(DSN) as c, c.cursor() as cur:
        cur.execute(f"SELECT path, task_id, recorder_id, env_id FROM {TBL} WHERE path=%s", (path,))
        return cur.fetchone()

async def main():
    path = pick_path()
    print(f"[PROBE] {path}")
    before = get_row(path)
    print(f"[BEFORE] {before}")
    new_val = f"REPRO_{int(time.time())}"
    print(f"[TARGET] task_id → {new_val}")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1700, "height": 900})
        page = await ctx.new_page()
        save_calls = []
        all_reqs = []
        async def on_req(req):
            if "/api/" in req.url:
                all_reqs.append(f"REQ {req.method} {req.url}")
        async def on_resp(resp):
            if "/api/" in resp.url:
                try: txt = await resp.text()
                except: txt = "<err>"
                all_reqs.append(f"RES {resp.status} {resp.url} body={txt[:200]}")
                if "/api/save-rows" in resp.url:
                    save_calls.append({"status": resp.status, "body": txt[:300]})
        page.on("request", on_req)
        page.on("response", on_resp)
        page.on("console", lambda m: print(f"  [c.{m.type}] {m.text[:300]}"))

        await page.goto(VIDEO_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        # 清空所有筛选，确保 task_id 列渲染
        await page.evaluate("""
            () => {
              const ids = ['sharedFilterLocation','sharedFilterRecorder','sharedFilterTask','sharedFilterUploaded','sharedFilterType'];
              for (const id of ids) {
                const el = document.getElementById(id);
                if (el) el.value = '';
              }
              try { localStorage.removeItem('sharedFilterState'); } catch(e) {}
              if (typeof applySharedFilters === 'function' && typeof renderTable === 'function') renderTable();
            }
        """)
        await page.wait_for_timeout(1000)

        # 找到第一个 task_id 的 searchable-sel
        info = await page.evaluate("""
            () => {
              const all = [...document.querySelectorAll('input[id^="rt-"][id$="_inp"]')];
              const tkInp = document.querySelector('input[id^="rt-"][id$="-task_id_inp"]');
              const sampleFields = all.slice(0, 30).map(i => i.id);
              if (!tkInp) {
                return {found: false, count: all.length, sampleFields};
              }
              const tr = tkInp.closest('tr');
              const td = tr.querySelector('td[data-key="task_id"]');
              return {
                found: true,
                inpId: tkInp.id,
                uid: tkInp.id.replace('_inp', ''),
                valElId: tkInp.id.replace('_inp', '_val'),
                curVal: (tr.querySelector('input.searchable-sel-val[data-field="task_id"]') || {}).value,
                rowIdx: parseInt(tr.dataset.index),
                trKey: tr.dataset.key,
                path: tr.querySelector('td.path-cell')?.textContent,
                tdClass: td?.className,
                colHidden: td?.classList.contains('col-hidden'),
                count: all.length
              };
            }
        """)
        print(f"[FOUND] {info}")
        if not info.get("found"):
            return
        uid = info["uid"]
        path = info.get("path", path)
        if path:
            print(f"[USING path] {path}")
            print(f"[BEFORE] {get_row(path)}")

        # 1) 走 ssSelect（模拟 dropdown 选项点击）
        print(f"\n[T1] 调 ssSelect({uid}, '{new_val}', 'REPRO_DISPLAY')")
        await page.evaluate(f"ssSelect({json.dumps(uid)}, {json.dumps(new_val)}, {json.dumps('REPRO_DISPLAY')})")
        await page.wait_for_timeout(2000)

        after1 = get_row(path)
        print(f"[AFTER T1] {after1}")
        if after1 and after1[1] == new_val:
            print("✅ T1 成功：ssSelect 直调写入 OK")
        else:
            print("❌ T1 失败：ssSelect 直调没生效")

        # 2) 走真实 user 路径：点击 input → 等 dropdown → 点一个 options
        print(f"\n[T2] 模拟用户点 dropdown 选项")
        # 先恢复原值
        await page.evaluate(f"""
            () => {{
              const inp = document.getElementById({json.dumps(uid+'_inp')});
              inp.focus();
            }}
        """)
        await page.wait_for_timeout(500)
        # 查 dropdown 是否弹出
        drop_state = await page.evaluate(f"""
            () => {{
              const drop = document.getElementById({json.dumps(uid+'_drop')});
              return {{display: drop?.style.display, opts: drop ? drop.querySelectorAll('.searchable-sel-opt, div').length : 0, html: drop?.innerHTML.slice(0, 200)}};
            }}
        """)
        print(f"[T2 dropdown] {drop_state}")
        # 点第一个 option（如果有）
        opt_clicked = await page.evaluate(f"""
            () => {{
              const drop = document.getElementById({json.dumps(uid+'_drop')});
              if (!drop || drop.style.display === 'none') return {{ok: false, reason: 'dropdown not open'}};
              const opts = drop.querySelectorAll('[data-value]');
              if (!opts.length) return {{ok: false, reason: 'no options', html: drop.innerHTML.slice(0,500)}};
              // 取第一个非空 value 的 option
              let target = null;
              for (const o of opts) {{
                if (o.dataset.value) {{ target = o; break; }}
              }}
              if (!target) return {{ok: false, reason: 'no target'}};
              const v = target.dataset.value;
              const d = target.textContent;
              // 模拟点击
              target.click();
              return {{ok: true, value: v, display: d, total: opts.length}};
            }}
        """)
        print(f"[T2 click] {opt_clicked}")
        await page.wait_for_timeout(2000)

        after2 = get_row(path)
        print(f"[AFTER T2] {after2}")

        # 3) 走"打字不改 dropdown"路径
        print(f"\n[T3] 模拟在 input 里打字但 blur（不点 dropdown）")
        await page.evaluate(f"""
            () => {{
              const inp = document.getElementById({json.dumps(uid+'_inp')});
              inp.focus();
            }}
        """)
        await page.wait_for_timeout(300)
        new_typed = f"TYPED_{int(time.time())}"
        # 用 fill 模拟键入
        await page.fill(f"#{uid}_inp", new_typed)
        await page.wait_for_timeout(200)
        # 模拟 blur
        await page.evaluate(f"document.getElementById({json.dumps(uid+'_inp')}).blur()")
        await page.wait_for_timeout(2000)

        after3 = get_row(path)
        print(f"[AFTER T3] {after3}")
        if after3 and after3[1] == new_typed:
            print("✅ T3 成功：纯打字也能写")
        else:
            print("❌ T3 失败：纯打字（不选 dropdown）不写")

        print(f"\n========= /api/save-rows calls ({len(save_calls)}) =========")
        for c in save_calls:
            print(f"  status={c['status']}  body={c['body']}")

        await page.screenshot(path="/tmp/vm_repro3.png", full_page=False)
        await browser.close()

    print(f"\n========= 所有 /api/* 请求 ({len(all_reqs)}) =========")
    for r in all_reqs:
        if "/api/" in r:
            print(f"  {r[:300]}")

asyncio.run(main())
