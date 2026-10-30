# ────────────────────────────────────────────────────────────────
# scan_all_videos.py — 扫描全部 6 页视频，获取 session_id + date
# + 对有 missing 的视频读 operator_name / task_description / environment_description
#
# 运行：python src/scripts/scan_all_videos.py
# ────────────────────────────────────────────────────────────────

from __future__ import annotations
import sys, os, time, csv
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

TARGET_URL = "https://publish.example.com/vendors?tab=upload-history"
OUT_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
               "runtime", "data", "video_batch_config.csv")


def get_tile_info(page) -> list[dict]:
    return page.evaluate("""
    () => {
        var tiles = document.querySelectorAll('.vcb-tile');
        var results = [];
        tiles.forEach(function(tile) {
            // 滚动到 tile 使其渲染
            tile.scrollIntoView({behavior: 'instant', block: 'center'});

            var titleEl = tile.querySelector('.vcb-tile-title');
            var scoreEl  = tile.querySelector('.vcb-score-good, .vcb-score-medium, .vcb-score-bad');
            var badgeRight = tile.querySelector('.vcb-tile-badge-right');
            var chipEl = tile.querySelector('.vcb-chip');
            var metaEls = tile.querySelectorAll('.vcb-tile-meta');

            var sessionId = titleEl ? titleEl.textContent.trim() : '';
            var title    = titleEl ? (titleEl.getAttribute('title') || sessionId) : '';

            var dateStr = '';
            metaEls.forEach(function(el) {
                var txt = el.textContent.trim();
                if (txt.match(/\\d月\\d+日/)) dateStr = txt;
            });

            // Unique ID: sessionId + date
            var uid = sessionId + '|' + dateStr;

            results.push({
                session_id:   sessionId,
                uid:          uid,
                date:         dateStr,
                duration:     badgeRight ? badgeRight.textContent.trim() : '',
                capture_mode: chipEl ? chipEl.textContent.trim() : '',
                score:        scoreEl ? scoreEl.textContent.trim() : '',
            });
        });
        return results;
    }
    """)


def wait_for_tiles(page, min_count=1, timeout=15000):
    """等待至少 min_count 个 .vcb-tile 出现"""
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        count = page.evaluate("document.querySelectorAll('.vcb-tile').length")
        if count >= min_count:
            return count
        time.sleep(0.5)
    return page.evaluate("document.querySelectorAll('.vcb-tile').length")


def go_to_page(page, page_num: int):
    """翻到第 N 页（1-indexed）；已在第1页则跳过"""
    if page_num <= 1:
        return
    # 用 JS 填页码（React 受控 input，Playwright fill 可能不触发）
    page.evaluate(f"""
    (() => {{
        var inputs = document.querySelectorAll('input[type=number]');
        var target = inputs[inputs.length - 1];
        if (!target) return;
        var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value'
        ).set;
        nativeInputValueSetter.call(target, '{page_num}');
        target.dispatchEvent(new Event('input', {{ bubbles: true }}));
        target.dispatchEvent(new Event('change', {{ bubbles: true }}));
    }})()
    """)
    time.sleep(0.5)
    # 用 JS 点击 Go 按钮（Playwright 认为 button disabled）
    page.evaluate("""
    (() => {
        var btns = document.querySelectorAll('button');
        for (var i = 0; i < btns.length; i++) {
            if ((btns[i].textContent || '').trim() === 'Go') {
                btns[i].click(); return;
            }
        }
    })()
    """)
    time.sleep(2)
    wait_for_tiles(page)


def get_missing_fields(page) -> dict:
    """
    打开 Edit metadata，读取 operator_name / task_description /
    environment_description 三个字段，然后关闭。
    """
    # 1. 点击 Edit metadata 按钮
    edit_info = page.evaluate("""
    () => {
        var modal = document.querySelector('.vcb-modal-overlay');
        if (!modal) return null;
        var btns = modal.querySelectorAll('button');
        for (var i = 0; i < btns.length; i++) {
            var txt = (btns[i].textContent || '').trim();
            if (txt.indexOf('Edit') >= 0 || txt.indexOf('metadata') >= 0) {
                var r = btns[i].getBoundingClientRect();
                return { x: Math.round(r.x + r.width / 2),
                         y: Math.round(r.y + r.height / 2) };
            }
        }
        return null;
    }
    """)
    if not edit_info:
        return {}
    page.mouse.click(edit_info['x'], edit_info['y'])
    time.sleep(2)

    # 2. 读取三个字段值
    result = page.evaluate("""
    () => {
        function isVis(el) {
            if (!el) return false;
            var r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0 && r.x >= 0 && r.y >= 0;
        }
        function findVis(ph) {
            ph = ph.toLowerCase();
            return Array.from(document.querySelectorAll('input')).find(function(el) {
                return isVis(el) &&
                       ((el.getAttribute('placeholder') || '').toLowerCase().includes(ph) ||
                        (el.id && el.id.toLowerCase().includes(ph)));
            }) || null;
        }
        var r = {};
        var op = findVis('Operator name');
        var tk = findVis('Task description');
        var ev = findVis('Environment');
        r.operator_name            = op ? op.value : '';
        r.task_description         = tk ? tk.value : '';
        r.environment_description  = ev ? ev.value : '';
        return r;
    }
    """)

    # 3. 关闭 Edit metadata 表单（按 Escape）
    page.keyboard.press('Escape')
    time.sleep(0.5)
    return result


def process_tile(page, tile_info: dict, tile_idx: int) -> dict:
    """
    点击单个 tile，打开 modal，返回 missing 数量。
    若 > 0 missing，再打开 Edit metadata，读取三个字段。
    """
    # 先滚动到 tile 可见，再取坐标点击
    tile_center = page.evaluate("""
    (idx) => {
        var tiles = document.querySelectorAll('.vcb-tile');
        var tile  = tiles[idx];
        if (!tile) return null;
        var media = tile.querySelector('.vcb-tile-media');
        if (!media) return null;
        media.scrollIntoView({behavior: 'instant', block: 'center'});
        var r = media.getBoundingClientRect();
        return { x: Math.round(r.x + r.width / 2),
                 y: Math.round(r.y + r.height / 2) };
    }
    """, tile_idx)

    if not tile_center:
        return {**tile_info, 'missing': -1}

    time.sleep(0.3)
    page.mouse.click(tile_center['x'], tile_center['y'])
    time.sleep(1.5)

    # 检查 modal missing 数量
    missing = page.evaluate("""
    () => {
        var modal = document.querySelector('.vcb-modal-overlay');
        if (!modal) return -1;
        var txt = modal.textContent || '';
        var m = txt.match(/(\\d+)\\s*missing/);
        return m ? parseInt(m[1]) : 0;
    }
    """)

    row = {**tile_info, 'missing': missing}

    if missing > 0:
        fields = get_missing_fields(page)
        row['operator_name']           = fields.get('operator_name', '')
        row['task_description']        = fields.get('task_description', '')
        row['environment_description'] = fields.get('environment_description', '')
    else:
        row['operator_name']           = ''
        row['task_description']        = ''
        row['environment_description'] = ''

    # 关闭 modal
    page.keyboard.press('Escape')
    time.sleep(0.5)
    # 每次关闭 modal 后滚回顶部，防止后续 tile 坐标偏移
    page.evaluate("window.scrollTo(0, 0)")
    return row


def main():
    from playwright.sync_api import sync_playwright

    all_videos = []

    pw = sync_playwright().start()
    try:
        browser = pw.chromium.connect_over_cdp("http://localhost:9222")
        page    = browser.contexts[0].pages[0]

        page.goto(TARGET_URL, timeout=15000)
        page.wait_for_load_state("load", timeout=15000)
        time.sleep(1)

        # ── 设置筛选条件 ─────────────────────────────────────────
        print("Setting Capture = Stereo...")
        page.evaluate("""
        (function() {
            var selects = document.querySelectorAll("select");
            for (var i = 0; i < selects.length; i++) {
                var opts = Array.from(selects[i].options)
                    .map(function(o){ return o.textContent.trim(); });
                if (opts.some(function(o){ return o.indexOf("Stereo") >= 0; })) {
                    selects[i].value = "stereo";
                    selects[i].dispatchEvent(new Event("change", {bubbles:true}));
                    break;
                }
            }
        })()
        """)
        time.sleep(0.3)

        print("Setting Excludes tags...")
        page.evaluate("""
        (function() {
            var btns = document.querySelectorAll("button");
            for (var i = 0; i < btns.length; i++) {
                if ((btns[i].textContent || "").indexOf("Excludes") >= 0) {
                    btns[i].click(); return;
                }
            }
        })()
        """)
        time.sleep(0.5)
        for tag in ["review_reject", "vendor-delete", "wipe"]:
            page.evaluate(
                "(function() { var btns = document.querySelectorAll('button'); "
                "for (var i = 0; i < btns.length; i++) { "
                "if ((btns[i].textContent||'').indexOf('" + tag + "') >= 0) "
                "{ btns[i].click(); return; } } })()"
            )
            time.sleep(0.2)
        page.keyboard.press("Escape")
        time.sleep(0.5)
        print("Filters set. Waiting for tiles to render...")
        tile_count = wait_for_tiles(page, min_count=10, timeout=15000)
        print(f"Filters set.\n")

        # ── 加载已扫过的 CSV，跳过重复 ────────────────────────────
        skip_keys = set()
        existing_csv = OUT_CSV
        if os.path.exists(existing_csv):
            with open(existing_csv, 'r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    key = (row.get('session_id', '').strip(),
                           row.get('date', '').strip())
                    if key[0]:
                        skip_keys.add(key)
            print(f"Loaded {len(skip_keys)} existing rows from CSV, will skip them.\n")

        # ── 遍历全部 6 页 ──────────────────────────────────────────
        TOTAL_PAGES = 6

        for page_num in range(1, TOTAL_PAGES + 1):
            if page_num > 1:
                go_to_page(page, page_num)
                tile_count = wait_for_tiles(page, min_count=10, timeout=15000)

            # 翻页后可能落在页面底部，先滚到顶部
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(0.3)
            tile_count = page.evaluate(
                "document.querySelectorAll('.vcb-tile').length"
            )
            print(f"  Page {page_num}: {tile_count} tiles")

            tile_infos = get_tile_info(page)

            for tile_idx, tile_info in enumerate(tile_infos):
                # 跳过已存在于 CSV 的视频（按 session_id + date 判重）
                key = (tile_info.get('session_id', '').strip(),
                       tile_info.get('date', '').strip())
                if key[0] and key in skip_keys:
                    print(f"    [{tile_idx+1}/{tile_count}] SKIP (already in CSV) "
                          f"{tile_info['session_id']} | {tile_info['date']}")
                    continue

                row = process_tile(page, tile_info, tile_idx)
                row['page'] = page_num
                all_videos.append(row)

                status = (f"missing={row['missing']}"
                          if row['missing'] > 0
                          else f"OK ({row['missing']} missing)")
                print(f"    [{tile_idx+1}/{tile_count}] {tile_info['session_id']} | "
                      f"{tile_info['date']} | {status}")

        print(f"\nTotal tiles processed: {len(all_videos)}")

        browser.close()
    finally:
        pw.stop()

    # ── 去重 ──────────────────────────────────────────────────────
    uid_seen     = set()
    unique_vids  = []
    for v in all_videos:
        if v['uid'] not in uid_seen:
            uid_seen.add(v['uid'])
            unique_vids.append(v)

    print(f"Unique videos: {len(unique_vids)}")

    # ── 写 CSV（删掉 device_id 和 status）────────────────────────
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    headers = [
        'session_id', 'date', 'duration', 'score',
        'missing',
        'operator_name', 'task_description', 'environment_description',
        'notes'
    ]
    with open(OUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for v in unique_vids:
            writer.writerow({
                'session_id':              v.get('session_id', ''),
                'date':                    v.get('date', ''),
                'duration':                v.get('duration', ''),
                'score':                   v.get('score', ''),
                'missing':                 v.get('missing', 0),
                'operator_name':           v.get('operator_name', ''),
                'task_description':        v.get('task_description', ''),
                'environment_description': v.get('environment_description', ''),
                'notes':                   '',
            })

    print(f"\nCSV saved: {OUT_CSV}")
    print(f"Rows: {len(unique_vids)}")
    print()
    print("Columns you need to fill manually:")
    print("  operator_name       — 录制员名称（如 op6）")
    print("  task_description   — 任务描述关键词（如 faucet）")
    print("  environment_description — 环境描述（如 factory workshop）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
