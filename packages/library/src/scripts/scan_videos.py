# ────────────────────────────────────────────────────────────────
# scan_videos.py — 扫描 upload-history，记录每个视频的状态
#
# 唯一标识：session ID + 日期时间（如 session_00020_6月17日_13:33）
# 状态：missing 数量、是否已填写
#
# 用法：python src/scripts/scan_videos.py
# ────────────────────────────────────────────────────────────────

from __future__ import annotations
import sys, os, time, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import urllib.request, urllib.error

API = "http://localhost:5000"


def scan_page(page) -> list[dict]:
    """抓取当前页所有视频信息"""
    return page.evaluate("""
    () => {
        var tiles = document.querySelectorAll('.vcb-tile');
        var results = [];
        tiles.forEach(function(tile) {
            var titleEl = tile.querySelector('.vcb-tile-title');
            var metaEls = tile.querySelectorAll('.vcb-tile-meta');
            var chipEls = tile.querySelectorAll('.vcb-chip');
            var scoreEl = tile.querySelector('.vcb-score-good, .vcb-score-medium, .vcb-score-bad');

            var sessionId = titleEl ? titleEl.textContent.trim() : '';
            var dateStr = '';
            var durationStr = '';
            var chipStr = '';

            metaEls.forEach(function(el) {
                var txt = el.textContent.trim();
                if (txt.match(/\\d月\\d+日/)) dateStr = txt;
            });

            var badgeRight = tile.querySelector('.vcb-tile-badge-right');
            durationStr = badgeRight ? badgeRight.textContent.trim() : '';

            chipEls.forEach(function(el) {
                chipStr += (el.textContent || '').trim() + ' ';
            });

            var score = scoreEl ? scoreEl.textContent.trim() : '';

            // Get unique identifier: session ID + date + chip
            var uid = (sessionId + '_' + dateStr + '_' + chipStr.trim().replace(/\\s+/g, '-')).replace(/\\s/g, '');

            results.push({
                session_id: sessionId,
                date: dateStr,
                duration: durationStr,
                capture_mode: chipStr.trim(),
                score: score,
                uid: uid
            });
        });
        return results;
    }
    """)


def get_missing_count(tile) -> int | None:
    """点击 tile，获取 missing 数量，返回 None 表示无 missing（已填完）"""
    bb = tile.bounding_box()
    if not bb:
        return None
    cx = bb['x'] + bb['width'] / 2
    cy = bb['y'] + bb['height'] / 2

    tile.evaluate("""el => el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}))""")
    time.sleep(1.2)

    # 检查 modal
    modal = tile.evaluate("""el => {
        var overlay = document.querySelector('.vcb-modal-overlay');
        if (!overlay) return null;
        var txt = overlay.textContent || '';
        var m = txt.match(/(\\d+)\\s*missing/);
        return m ? parseInt(m[1]) : 0;
    }""")

    # 关闭 modal（点 X 或 ESC）
    tile.evaluate("""el => {
        var closeBtn = document.querySelector('.vcb-modal button[aria-label=\"Close\"], .vcb-modal .vcb-modal-close, .vcb-modal-overlay');
        if (closeBtn) closeBtn.click();
    }""")
    try:
        tile.page.keyboard.press('Escape')
    except:
        pass
    time.sleep(0.3)
    return modal


def main():
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    try:
        browser = pw.chromium.connect_over_cdp("http://localhost:9222")
        page = browser.contexts[0].pages[0]

        page.goto("https://publish.example.com/vendors?tab=upload-history", timeout=15000)
        page.wait_for_load_state("networkidle", timeout=8000)
        time.sleep(1)

        print(f"URL: {page.url}")
        print("Scanning page...")

        # 抓取基本信息（不点开）
        videos = scan_page(page)
        print(f"Found {len(videos)} tiles on current page")
        print()
        print(f"{'UID':<45} {'Session':<25} {'Date':<12} {'Missing'}")
        print("-" * 90)

        # 对每个 tile 点开检查 missing
        tiles = page.locator(".vcb-tile").all()
        for i, tile in enumerate(tiles):
            vid = videos[i]
            missing = get_missing_count(tile)
            vid['missing'] = missing
            vid['status'] = 'filled' if (missing == 0) else ('missing' if missing else 'unknown')
            print(f"{vid['uid']:<45} {vid['session_id']:<25} {vid['date']:<12} {missing}")

        browser.close()
    finally:
        pw.stop()

    # 保存结果
    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                            "runtime", "data", "video_status.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(videos, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
