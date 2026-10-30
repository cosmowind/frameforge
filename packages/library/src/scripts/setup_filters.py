# ────────────────────────────────────────────────────────────────
# setup_filters.py — 视频筛选初始化（每次启动浏览器只需运行一次）
#
# 设置：
#   Capture  → Stereo
#   Excludes tags → 全选（Flagged only / Not annotated / Rejected only）
#
# 运行：python src/scripts/setup_filters.py
# ────────────────────────────────────────────────────────────────

from __future__ import annotations
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from playwright.sync_api import sync_playwright

TARGET_URL = "https://publish.example.com/vendors?tab=upload-history"
EXCLUDE_CHECKBOX_LABELS = ["review_reject", "vendor-delete", "wipe"]


def setup_page(page):
    """在 upload-history 页面上设置筛选条件"""
    page.goto(TARGET_URL, timeout=15000)
    page.wait_for_load_state("networkidle", timeout=8000)
    time.sleep(1)

    # 1. Capture → Stereo
    selects = page.locator("select").all()
    for sel in selects:
        opts = [o.strip() for o in sel.locator("option").all_text_contents()]
        if any("Stereo" in o for o in opts):
            sel.select_option("stereo")
            print("[OK] Capture = Stereo")
            break
    time.sleep(0.3)

    # 2. Excludes tags → 全选（review_reject / vendor-delete / wipe）
    all_buttons = {b.text_content() or "": b for b in page.locator("button").all()}
    if "Excludes tags" in all_buttons:
        all_buttons["Excludes tags"].click()
        time.sleep(0.5)
        for target in EXCLUDE_CHECKBOX_LABELS:
            loc = page.locator(f'button:has-text("{target}")')
            if loc.count() > 0:
                loc.first.click()
                print(f"[OK] Excluded: {target}")
        page.keyboard.press("Escape")
        time.sleep(0.3)

    page.wait_for_load_state("networkidle", timeout=5000)
    time.sleep(1)


def main():
    pw = sync_playwright().start()
    try:
        browser = pw.chromium.connect_over_cdp("http://localhost:9222")
        page = browser.contexts[0].pages[0]
        print(f"Page: {page.url}")

        setup_page(page)

        # 统计结果
        items = [t for t in page.locator("text=Stereo · left eye").all() if t.is_visible()]
        print(f"\nStereo items shown: {len(items)}")
        print("Setup complete!")

        browser.close()
    finally:
        pw.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
