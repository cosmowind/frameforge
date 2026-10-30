#!/usr/bin/env python3
"""诊断脚本：打开上传页面，抓取所有表单元素信息，用于修正选择器"""
import asyncio
import json
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("请安装 playwright")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # 项目根目录
BROWSER_DATA_DIR = str(BASE_DIR / "runtime" / "browser_data")
UPLOAD_URL = "https://publish.example.com/vendors?tab=upload"


def log(msg: str):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


async def check_login_required(page) -> bool:
    """判断当前是否需要登录"""
    url = page.url.lower()
    if any(kw in url for kw in ("sign-up", "sign-in", "login", "signin", "signup")):
        return True
    try:
        page_text = await page.locator("body").inner_text(timeout=3000)
        if any(kw in page_text.lower() for kw in ("sign in to continue", "log in to your account", "become a data vendor")):
            return True
    except Exception:
        pass
    return False


async def wait_for_login(page, context) -> bool:
    """阻塞等待用户手动登录"""
    log("=" * 60)
    log("⚠ 检测到未登录状态！")
    log("请在浏览器窗口中手动登录 FrameForge")
    log("登录后导航到 Vendors > Upload 标签页")
    log("程序将自动检测登录状态并继续...")
    log("=" * 60)
    print("\n请在浏览器窗口中完成登录...")

    deadline = time.time() + 600  # 10分钟超时
    while time.time() < deadline:
        await asyncio.sleep(3)
        try:
            current_url = page.url
            if not await check_login_required(page):
                log(f"✓ 检测到已登录，当前页面: {current_url}")
                return True
        except Exception:
            pass
        if context.pages:
            page = context.pages[-1]
        else:
            log("⚠ 浏览器窗口已关闭")
            return False

    log("✗ 登录等待超时（10分钟），放弃。")
    return False


async def scrape_form_elements(page):
    """抓取页面上所有表单元素"""
    # 等待表单加载
    log("等待表单元素加载...")
    await asyncio.sleep(3)

    # 截图
    await page.screenshot(path=str(BASE_DIR / "diagnose_form.png"))
    log("截图保存为 diagnose_form.png")

    # 抓取所有表单元素信息
    form_info = await page.evaluate("""() => {
        const elements = [];
        
        // Helper: get element signature
        function getSignature(el) {
            const sig = {
                tag: el.tagName.toLowerCase(),
                type: el.type || '',
                id: el.id || '',
                name: el.name || '',
                placeholder: el.placeholder || '',
                'data-field': el.getAttribute('data-field') || '',
                'data-testid': el.getAttribute('data-testid') || '',
                'aria-label': el.getAttribute('aria-label') || '',
                'aria-labelledby': el.getAttribute('aria-labelledby') || '',
                class: (el.className || '').substring(0, 100),
                value: (el.value || '').substring(0, 50),
                text: (el.textContent || '').trim().substring(0, 100),
            };
            
            // Get computed selector
            let selector = sig.tag;
            if (sig.id) selector += '#' + sig.id;
            else if (sig.name) selector += `[name="${sig.name}"]`;
            else if (sig.class) {
                const classes = sig.class.split(/\\s+/).filter(c => c).slice(0, 2);
                if (classes.length) selector += '.' + classes.join('.');
            }
            sig.selector = selector;
            
            return sig;
        }
        
        // Helper: find associated label
        function findLabel(el) {
            // Via for attribute
            if (el.id) {
                const label = document.querySelector(`label[for="${el.id}"]`);
                if (label) return label.textContent.trim().substring(0, 100);
            }
            // Via parent label
            let parent = el.parentElement;
            for (let i = 0; i < 3 && parent; i++) {
                if (parent.tagName === 'LABEL') {
                    return parent.textContent.trim().substring(0, 100);
                }
                const labelInParent = parent.querySelector(':scope > label');
                if (labelInParent) return labelInParent.textContent.trim().substring(0, 100);
                parent = parent.parentElement;
            }
            // Via preceding sibling
            const prev = el.previousElementSibling;
            if (prev && prev.tagName === 'LABEL') {
                return prev.textContent.trim().substring(0, 100);
            }
            return '';
        }
        
        // 1. Standard form elements
        const tags = ['input', 'select', 'textarea'];
        for (const tag of tags) {
            document.querySelectorAll(tag).forEach(el => {
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 && rect.height === 0) return; // skip hidden
                
                const info = getSignature(el);
                info.label = findLabel(el);
                info.visible = rect.width > 0 && rect.height > 0;
                info.bbox = {x: rect.x, y: rect.y, w: rect.width, h: rect.height};
                elements.push(info);
            });
        }
        
        // 2. Custom select/dropdown widgets (common in React apps)
        document.querySelectorAll('[role="combobox"], [role="listbox"], [role="button"][aria-haspopup]').forEach(el => {
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) return;
            
            const info = getSignature(el);
            info.role = el.getAttribute('role') || '';
            info.label = findLabel(el);
            info.visible = true;
            info.widget = 'custom-select';
            elements.push(info);
        });
        
        // 3. React-Ant Design style dropdowns
        document.querySelectorAll('.ant-select, .ant-dropdown-trigger, [class*="select"]').forEach(el => {
            const rect = el.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) return;
            if (elements.some(e => e.id === el.id && e.id)) return; // skip duplicates
            
            const info = getSignature(el);
            info.label = findLabel(el);
            info.visible = true;
            info.widget = 'antd-select';
            elements.push(info);
        });
        
        return elements;
    }""")

    return form_info


async def main():
    log("启动浏览器...")
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            BROWSER_DATA_DIR,
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            viewport={"width": 1280, "height": 900},
        )
        page = context.pages[0] if context.pages else await context.new_page()

        log(f"导航到: {UPLOAD_URL}")
        try:
            await page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            log(f"导航超时: {e}")
        
        log(f"当前页面: {page.url}")

        # 检查登录状态
        if await check_login_required(page):
            logged_in = await wait_for_login(page, context)
            if not logged_in:
                log("登录未完成，退出")
                await context.close()
                return
            # 重新导航到上传页
            await page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)

        # 抓取表单元素
        form_info = await scrape_form_elements(page)

        # 打印结果
        log(f"\n找到 {len(form_info)} 个可见表单元素:\n")
        for i, el in enumerate(form_info):
            tag_type = f"{el['tag']}[{el['type']}]" if el.get('type') else el['tag']
            role = f"[{el.get('role')}]" if el.get('role') else ''
            print(f"[{i}] {tag_type} {role}")
            if el.get('id'): print(f"    id: {el['id']}")
            if el.get('name'): print(f"    name: {el['name']}")
            if el.get('placeholder'): print(f"    placeholder: {el['placeholder']}")
            if el.get('data-field'): print(f"    data-field: {el['data-field']}")
            if el.get('aria-label'): print(f"    aria-label: {el['aria-label']}")
            if el.get('label'): print(f"    label: {el['label']}")
            if el.get('selector'): print(f"    selector: {el['selector']}")
            if el.get('text'): print(f"    text: {el['text']}")
            if el.get('value'): print(f"    value: {el['value']}")
            if el.get('widget'): print(f"    widget: {el['widget']}")
            print()

        # 保存 JSON
        out_path = BASE_DIR / "diagnose_form.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(form_info, f, indent=2, ensure_ascii=False)
        log(f"完整数据已保存到: {out_path}")

        # 保持浏览器打开 60 秒供查看
        log("\n浏览器将在 60 秒后关闭，请查看页面...")
        await asyncio.sleep(60)

        await context.close()


if __name__ == "__main__":
    asyncio.run(main())
