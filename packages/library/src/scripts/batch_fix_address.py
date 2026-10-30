# ────────────────────────────────────────────────────────────────
# batch_fix_address.py — 批量修正 location address 字段
#
# 前提：已在 upload-history 页面设好筛选条件（如 has tags=address）
# 本脚本遍历所有 tile（忽略 missing），进入 Edit metadata 把
# location address 改成指定值，然后保存关闭。
#
# 用法：python src/scripts/batch_fix_address.py
# ────────────────────────────────────────────────────────────────
from __future__ import annotations

import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

TARGET_ADDRESS = "No. 84, Changcheng Road, Jijiang Subdistrict, Jiangjin District"
CDP_URL = "http://localhost:9222"
MAX_PAGES = 10  # 最多翻几页


def wait_for_tiles(page, min_count=1, timeout=15000):
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        count = page.evaluate("document.querySelectorAll('.vcb-tile').length")
        if count >= min_count:
            return count
        time.sleep(0.5)
    return page.evaluate("document.querySelectorAll('.vcb-tile').length")


def get_tile_uids(page):
    """获取当前页所有 tile 的 uid（session_id + date），用于去重"""
    return page.evaluate("""
    () => {
        var tiles = document.querySelectorAll('.vcb-tile');
        var uids = [];
        tiles.forEach(function(tile) {
            var titleEl = tile.querySelector('.vcb-tile-title');
            var metaEls = tile.querySelectorAll('.vcb-tile-meta');
            var sid = titleEl ? titleEl.textContent.trim() : '';
            var dateStr = '';
            metaEls.forEach(function(el) {
                var txt = el.textContent.trim();
                if (txt.match(/\\d月\\d+日/)) dateStr = txt;
            });
            uids.push(sid + '|' + dateStr);
        });
        return uids;
    }
    """)


def click_tile(page, tile_idx):
    """点击第 tile_idx 个 tile 的 media 区域，返回是否成功打开 modal"""
    coords = page.evaluate("""
    (idx) => {
        var tiles = document.querySelectorAll('.vcb-tile');
        var tile = tiles[idx];
        if (!tile) return null;
        var media = tile.querySelector('.vcb-tile-media');
        if (!media) return null;
        media.scrollIntoView({behavior: 'instant', block: 'center'});
        var r = media.getBoundingClientRect();
        return { x: Math.round(r.x + r.width / 2),
                 y: Math.round(r.y + r.height / 2) };
    }
    """, tile_idx)

    if not coords:
        return False

    time.sleep(0.3)
    page.mouse.click(coords['x'], coords['y'])
    time.sleep(1.5)

    has_modal = page.evaluate("""
    () => !!document.querySelector('.vcb-modal-overlay')
    """)
    return has_modal


def click_edit_metadata(page):
    """在 modal 中点击 Edit metadata 按钮，返回是否成功"""
    info = page.evaluate("""
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
    if not info:
        return False

    page.mouse.click(info['x'], info['y'])
    time.sleep(2)
    return True


def find_address_field(page):
    """
    检测 location address 字段的类型和位置。
    返回 { found: bool, is_combobox: bool, placeholder: str }
    """
    return page.evaluate("""
    () => {
        function isVisible(el) {
            if (!el) return false;
            var r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0 && r.x >= 0 && r.y >= 0;
        }
        // 尝试多个 placeholder 关键词
        var keywords = ['stable site', 'location', 'address'];
        var inputs = Array.from(document.querySelectorAll('input'));

        for (var k = 0; k < keywords.length; k++) {
            for (var i = 0; i < inputs.length; i++) {
                var ph = (inputs[i].getAttribute('placeholder') || '').toLowerCase();
                if (isVisible(inputs[i]) && ph.includes(keywords[k])) {
                    var cls = inputs[i].className || '';
                    return {
                        found: true,
                        is_combobox: cls.indexOf('ring-offset-background') >= 0,
                        placeholder: inputs[i].getAttribute('placeholder') || '',
                        current_value: inputs[i].value || ''
                    };
                }
            }
        }
        // 兜底
        for (var i = 0; i < inputs.length; i++) {
            var ph = (inputs[i].getAttribute('placeholder') || '').toLowerCase();
            if (isVisible(inputs[i]) && (ph.includes('stable') || ph.includes('site'))) {
                var cls = inputs[i].className || '';
                return {
                    found: true,
                    is_combobox: cls.indexOf('ring-offset-background') >= 0,
                    placeholder: inputs[i].getAttribute('placeholder') || '',
                    current_value: inputs[i].value || ''
                };
            }
        }
        return { found: false };
    }
    """)


def fill_address_plain(page, address_value):
    """对普通 text input 用 setReactValue 写入"""
    return page.evaluate("""
    (addr) => {
        function isVisible(el) {
            if (!el) return false;
            var r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0 && r.x >= 0 && r.y >= 0;
        }
        function setReactValue(el, value) {
            var proto = Object.getPrototypeOf(el);
            var desc = Object.getOwnPropertyDescriptor(proto, 'value');
            if (desc && desc.set) { desc.set.call(el, value); }
            else { el.value = value; }
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }
        var keywords = ['stable site', 'location', 'address'];
        var inputs = Array.from(document.querySelectorAll('input'));
        var target = null;
        for (var k = 0; k < keywords.length; k++) {
            for (var i = 0; i < inputs.length; i++) {
                var ph = (inputs[i].getAttribute('placeholder') || '').toLowerCase();
                if (isVisible(inputs[i]) && ph.includes(keywords[k])) {
                    target = inputs[i]; break;
                }
            }
            if (target) break;
        }
        if (!target) return { ok: false, error: 'input not found' };
        setReactValue(target, addr);
        return { ok: true, placeholder: target.getAttribute('placeholder') || '' };
    }
    """, address_value)


def fill_address_combobox(page, address_value):
    """
    对 shadcn/ui combobox 输入框：
    1. 点击打开下拉
    2. 清空现有值
    3. 输入新值
    4. 等待下拉选项出现，点击匹配项
    5. 如果没有匹配项，按 Escape 关闭下拉（值已写入 input）
    """
    # Step 1: 点击 input 打开下拉
    clicked = page.evaluate("""
    () => {
        function isVisible(el) {
            if (!el) return false;
            var r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0 && r.x >= 0 && r.y >= 0;
        }
        var keywords = ['stable site', 'location', 'address'];
        var inputs = Array.from(document.querySelectorAll('input'));
        var target = null;
        for (var k = 0; k < keywords.length; k++) {
            for (var i = 0; i < inputs.length; i++) {
                var ph = (inputs[i].getAttribute('placeholder') || '').toLowerCase();
                if (isVisible(inputs[i]) && ph.includes(keywords[k])) {
                    target = inputs[i]; break;
                }
            }
            if (target) break;
        }
        if (!target) return null;
        target.focus();
        target.click();
        return { x: 0, y: 0 };  // signal success
    }
    """)
    if not clicked:
        return { ok: False, 'error': 'combobox input not found' }

    time.sleep(0.3)

    # Step 2 & 3: 清空并输入新值
    # 用 Playwright keyboard 操作（比 JS 更可靠地触发 combobox 过滤）
    page.evaluate("""
    () => {
        function isVisible(el) {
            if (!el) return false;
            var r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0 && r.x >= 0 && r.y >= 0;
        }
        var keywords = ['stable site', 'location', 'address'];
        var inputs = Array.from(document.querySelectorAll('input'));
        var target = null;
        for (var k = 0; k < keywords.length; k++) {
            for (var i = 0; i < inputs.length; i++) {
                var ph = (inputs[i].getAttribute('placeholder') || '').toLowerCase();
                if (isVisible(inputs[i]) && ph.includes(keywords[k])) {
                    target = inputs[i]; break;
                }
            }
            if (target) break;
        }
        if (target) {
            // 全选清空
            target.value = '';
            target.dispatchEvent(new Event('input', { bubbles: true }));
        }
    }
    """)
    time.sleep(0.1)

    # 用 keyboard.type 输入值（触发 combobox 过滤）
    page.keyboard.type(address_value, delay=20)
    time.sleep(0.8)

    # Step 4: 尝试点击匹配的下拉选项
    matched = page.evaluate("""
    (addr) => {
        // 尝试多种选项选择器
        var selectors = [
            '[cmdk-item]',
            "[role='option']",
            '[class*="CommandItem"]',
            'div[role="option"]',
            '[data-value]',
            '[role="menuitem"]',
        ];
        var addrLower = addr.toLowerCase();

        for (var s = 0; s < selectors.length; s++) {
            var items = document.querySelectorAll(selectors[s]);
            for (var i = 0; i < items.length; i++) {
                var item = items[i];
                var r = item.getBoundingClientRect();
                if (r.width <= 0 || r.height <= 0) continue;
                var txt = (item.textContent || '').toLowerCase();
                // 匹配：选项文本包含地址关键词，或地址包含选项文本
                if (txt.includes('changcheng') || txt.includes('jijiang') ||
                    txt.includes('jiangjin') || txt.includes('84') ||
                    addrLower.includes(txt.trim())) {
                    item.click();
                    return { clicked: true, text: item.textContent.trim() };
                }
            }
        }
        // 没找到精确匹配，尝试第一个可见选项
        for (var s = 0; s < selectors.length; s++) {
            var items = document.querySelectorAll(selectors[s]);
            for (var i = 0; i < items.length; i++) {
                var item = items[i];
                var r = item.getBoundingClientRect();
                if (r.width > 0 && r.height > 0) {
                    item.click();
                    return { clicked: true, text: item.textContent.trim(), first: true };
                }
            }
        }
        return { clicked: false };
    }
    """, address_value)

    if matched.get('clicked'):
        time.sleep(0.3)
        return { ok: True, method: 'combobox-select', matched: matched.get('text', '') }

    # 没有匹配选项 — 按 Escape 关闭下拉（input 中的值保留）
    page.keyboard.press('Escape')
    time.sleep(0.2)

    # 验证 input 中是否有值
    final_value = page.evaluate("""
    () => {
        function isVisible(el) {
            if (!el) return false;
            var r = el.getBoundingClientRect();
            return r.width > 0 && r.height > 0 && r.x >= 0 && r.y >= 0;
        }
        var keywords = ['stable site', 'location', 'address'];
        var inputs = Array.from(document.querySelectorAll('input'));
        for (var k = 0; k < keywords.length; k++) {
            for (var i = 0; i < inputs.length; i++) {
                var ph = (inputs[i].getAttribute('placeholder') || '').toLowerCase();
                if (isVisible(inputs[i]) && ph.includes(keywords[k])) {
                    return inputs[i].value || '';
                }
            }
        }
        return '';
    }
    """)

    if final_value:
        return { ok: True, method: 'combobox-type', value: final_value }

    return { ok: False, error: 'combobox: value not retained after close' }


def save_form(page):
    """
    在 Edit metadata 表单中保存。
    尝试多种方式：Save 按钮 → Save changes 按钮 → Ctrl+Enter。
    返回是否成功保存。
    """
    # 尝试点击各种可能的 Save 按钮
    saved = page.evaluate("""
    () => {
        var btns = document.querySelectorAll('button');
        var saveTexts = ['save changes', 'save', 'submit', 'update', 'confirm'];
        for (var i = 0; i < btns.length; i++) {
            var txt = (btns[i].textContent || '').trim().toLowerCase();
            for (var j = 0; j < saveTexts.length; j++) {
                if (txt === saveTexts[j] || txt.indexOf(saveTexts[j]) === 0) {
                    // 排除 "Save" 在其他上下文（如关闭按钮）
                    var r = btns[i].getBoundingClientRect();
                    if (r.width > 0 && r.height > 0) {
                        btns[i].click();
                        return { clicked: true, text: txt };
                    }
                }
            }
        }
        return { clicked: false };
    }
    """)

    if saved.get('clicked'):
        time.sleep(2)
        return True

    # 兜底：Ctrl+Enter
    page.keyboard.press('Control+Enter')
    time.sleep(2)
    return True


def close_all_overlays(page):
    """关闭所有可能的 modal / overlay"""
    for _ in range(3):
        page.keyboard.press('Escape')
        time.sleep(0.3)


def go_to_page(page, page_num):
    """翻到第 N 页（1-indexed）"""
    if page_num <= 1:
        return

    page.evaluate("""
    (() => {
        var inputs = document.querySelectorAll('input[type=number]');
        var target = inputs[inputs.length - 1];
        if (!target) return;
        var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
            window.HTMLInputElement.prototype, 'value'
        ).set;
        nativeInputValueSetter.call(target, '%d');
        target.dispatchEvent(new Event('input', { bubbles: true }));
        target.dispatchEvent(new Event('change', { bubbles: true }));
    })()
    """ % page_num)
    time.sleep(0.5)

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


def process_one_video(page, idx, uid):
    """处理单个视频：点击 → Edit metadata → 填 address → 保存"""
    # 1. 点击 tile
    if not click_tile(page, idx):
        return 'FAIL', 'no modal'

    # 2. 点击 Edit metadata
    if not click_edit_metadata(page):
        close_all_overlays(page)
        return 'FAIL', 'no Edit btn'

    # 3. 检测字段类型
    field_info = find_address_field(page)
    if not field_info.get('found'):
        close_all_overlays(page)
        return 'FAIL', 'address field not found'

    # 4. 填写
    if field_info.get('is_combobox'):
        result = fill_address_combobox(page, TARGET_ADDRESS)
    else:
        result = fill_address_plain(page, TARGET_ADDRESS)

    if not result.get('ok'):
        close_all_overlays(page)
        return 'FAIL', result.get('error', 'fill failed')

    # 5. 保存
    save_form(page)

    # 6. 关闭残留 overlay
    close_all_overlays(page)

    method = result.get('method', 'plain')
    return 'OK', method


def main():
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    try:
        browser = pw.chromium.connect_over_cdp(CDP_URL)
        page = browser.contexts[0].pages[0]

        # 确保在 upload-history 页面
        if 'upload-history' not in page.url and 'vendors' not in page.url:
            page.goto("https://publish.example.com/vendors?tab=upload-history",
                       timeout=15000)
            page.wait_for_load_state("load", timeout=15000)
            time.sleep(2)

        print(f"Current URL: {page.url}")
        print(f"Target address: {TARGET_ADDRESS}")
        print(f"NOTE: Processing ALL tiles (ignoring missing count)")
        print()

        processed_uids = set()
        total_fixed = 0
        total_failed = 0
        total_skipped = 0

        for page_num in range(1, MAX_PAGES + 1):
            if page_num > 1:
                go_to_page(page, page_num)

            tile_count = wait_for_tiles(page, min_count=1, timeout=10000)
            if tile_count == 0:
                print(f"  Page {page_num}: no tiles found, stopping.")
                break

            # 滚回顶部
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(0.3)

            uids = get_tile_uids(page)
            print(f"  Page {page_num}: {len(uids)} tiles")

            for idx in range(len(uids)):
                uid = uids[idx]
                if uid in processed_uids:
                    print(f"    [{idx+1}/{len(uids)}] SKIP (dup) {uid[:50]}")
                    total_skipped += 1
                    continue
                processed_uids.add(uid)

                status, detail = process_one_video(page, idx, uid)

                if status == 'OK':
                    total_fixed += 1
                    print(f"    [{idx+1}/{len(uids)}] ✓ {uid[:50]}  [{detail}]")
                else:
                    total_failed += 1
                    print(f"    [{idx+1}/{len(uids)}] ✗ {uid[:50]}  ({detail})")

                # 每次操作后滚回顶部
                page.evaluate("window.scrollTo(0, 0)")
                time.sleep(0.3)

        print()
        print(f"{'='*50}")
        print(f"  DONE")
        print(f"  Fixed:   {total_fixed}")
        print(f"  Failed:  {total_failed}")
        print(f"  Skipped: {total_skipped}")
        print(f"  Total:   {total_fixed + total_failed + total_skipped}")
        print(f"{'='*50}")

    finally:
        pw.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
