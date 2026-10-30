"""Final repro: ssSelect → 等到 fetch 完成 → 再读 PG."""
import asyncio, json, time
from playwright.async_api import async_playwright
import psycopg2

DSN = "postgresql://ffuser:changeme@db.example.com:5432/video_manager"
TBL = "videos"

def get_row(path):
    with psycopg2.connect(DSN) as c, c.cursor() as cur:
        cur.execute(f"SELECT path, task_id, recorder_id, env_id FROM {TBL} WHERE path=%s", (path,))
        return cur.fetchone()

async def main():
    path = "/media/videos/0625/hmd/0625_4aa45c_session_00000"
    new_val = f"REPRO_{int(time.time())}"
    print(f"[PROBE] {path}")
    print(f"[BEFORE] {get_row(path)}")
    print(f"[TARGET] task_id → {new_val}")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width":1700,"height":900})
        page = await ctx.new_page()

        save_events = []
        async def on_req(req):
            if "/api/save-rows" in req.url:
                save_events.append(("REQ", req.method, req.url, req.post_data))
        async def on_resp(resp):
            if "/api/save-rows" in resp.url:
                try: txt = await resp.text()
                except: txt = "<err>"
                save_events.append(("RES", resp.status, resp.url[:60], txt[:200]))
        page.on("request", on_req)
        page.on("response", on_resp)
        page.on("console", lambda m: print(f"  [c.{m.type}] {m.text[:300]}"))

        await page.goto("http://127.0.0.1:5000/", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)

        # 清掉所有筛选
        await page.evaluate("""
            () => {
              try { localStorage.removeItem('sharedFilterState'); } catch(e) {}
              const ids = ['sharedFilterLocation','sharedFilterRecorder','sharedFilterTask','sharedFilterUploaded','sharedFilterType'];
              for (const id of ids) { const el = document.getElementById(id); if (el) el.value=''; }
              if (typeof renderTable === 'function') renderTable();
            }
        """)
        await page.wait_for_timeout(1000)

        info = await page.evaluate("""
            () => {
              const inp = document.querySelector('input[id^="rt-"][id$="-task_id_inp"]');
              if (!inp) return {found: false};
              const tr = inp.closest('tr');
              return {
                found: true,
                uid: inp.id.replace('_inp',''),
                rowIdx: parseInt(tr.dataset.index),
                curVal: (tr.querySelector('input.searchable-sel-val[data-field="task_id"]') || {}).value
              };
            }
        """)
        print(f"[FOUND] {info}")
        if not info["found"]:
            return
        uid = info["uid"]

        # 改 task_id
        print(f"\n[STEP 1] ssSelect({uid}, '{new_val}')")
        await page.evaluate(f"ssSelect({json.dumps(uid)}, {json.dumps(new_val)}, {json.dumps('REPRO')})")

        # 关键：等 6 秒，足够 fetch + auto-save timer 完成
        print(f"[STEP 2] wait 6s for fetch to complete")
        await page.wait_for_timeout(6000)

        after = get_row(path)
        print(f"[AFTER] {after}")
        if after and after[1] == new_val:
            print("✅ 写入成功！")
        else:
            print("❌ 写入失败！")
            print(f"   期望 task_id={new_val}, 实际={after[1] if after else None}")

        print(f"\n========= save-rows 事件 ({len(save_events)}) =========")
        for ev in save_events:
            print(f"  {ev}")

        await browser.close()

asyncio.run(main())
