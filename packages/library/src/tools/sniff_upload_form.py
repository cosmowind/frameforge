#!/usr/bin/env python3
"""打开可见浏览器（用户已登录），截图并提取上传表单所有 select 选项。"""
import asyncio, json, os, sys, time
from pathlib import Path

PROJ_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ_DIR))

UPLOAD_URL = "https://publish.example.com/vendors?tab=upload"
BROWSER_DATA = str(PROJ_DIR / "runtime" / "browser_data")
OUT_DIR = PROJ_DIR / "tools"

async def main():
    from playwright.async_api import async_playwright

    # 如果 profile 被占用，提示用户关闭其他 Chrome
    print("[*] 启动浏览器（可见窗口）...")
    
    async with async_playwright() as p:
        try:
            ctx = await p.chromium.launch_persistent_context(
                BROWSER_DATA,
                headless=False,
                viewport={"width": 1400, "height": 950},
            )
        except Exception as e:
            print(f"[!] 无法使用 browser_data 目录: {e}")
            print("[*] 尝试使用新目录...")
            ctx = await p.chromium.launch_persistent_context(
                str(PROJ_DIR / "runtime" / "browser_data_fresh"),
                headless=False,
                viewport={"width": 1400, "height": 950},
            )

        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        
        print(f"[*] 导航到: {UPLOAD_URL}")
        await page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
        print(f"[*] 当前 URL: {page.url}")
        
        # 等待页面稳定
        await asyncio.sleep(2)
        
        # 检查是否需要登录
        url_lower = page.url.lower()
        if any(kw in url_lower for kw in ("sign-in", "signup", "sign-up", "login")):
            print("[!] 需要登录！请在浏览器窗口中登录 FrameForge...")
            print("[*] 等待中（最多 5 分钟）...")
            deadline = time.time() + 300
            while time.time() < deadline:
                await asyncio.sleep(2)
                try:
                    cur = page.url.lower()
                    if not any(kw in cur for kw in ("sign-in", "signup", "sign-up", "login")):
                        print(f"[√] 已登录，当前页面: {page.url}")
                        await asyncio.sleep(3)  # wait for form to render
                        break
                except:
                    pass
            else:
                print("[!] 登录超时")
                await ctx.close()
                return
        
        # 截图
        ss_path = str(OUT_DIR / "upload_form_screenshot.png")
        await page.screenshot(path=ss_path, full_page=False)
        print(f"[√] 截图已保存: {ss_path}")
        
        # 列出所有 select 元素
        selects = await page.locator("select").all()
        print(f"\n[=] 找到 {len(selects)} 个 select 元素:")
        
        all_options = {}
        
        for i, sel in enumerate(selects):
            try:
                name = (await sel.get_attribute("name")) or ""
                df = (await sel.get_attribute("data-field")) or ""
                sid = (await sel.get_attribute("id")) or ""
                placeholder = (await sel.get_attribute("placeholder")) or ""
                label_text = ""
                # try to find associated label
                try:
                    label_el = await sel.evaluate("el => { const id = el.id; if(id) { const lbl = document.querySelector(`label[for='${id}']`); return lbl ? lbl.textContent.trim() : ''; } return ''; }")
                    label_text = label_el or ""
                except:
                    pass
                
                print(f"\n  [{i}] name='{name}' data-field='{df}' id='{sid}' placeholder='{placeholder}' label='{label_text}'")
                
                # Extract options
                opts = await sel.locator("option").all()
                opt_list = []
                for o in opts[:10]:  # first 10
                    v = (await o.get_attribute("value")) or ""
                    t = (await o.inner_text()).strip()
                    opt_list.append({"value": v, "label": t})
                total = len(opts)
                key = df or name or f"select_{i}"
                print(f"      选项总数: {total}")
                for o in opt_list:
                    print(f"        - '{o['value']}' => '{o['label']}'")
                if total > 10:
                    # fetch all
                    all_opts = []
                    for o in opts:
                        v = (await o.get_attribute("value")) or ""
                        t = (await o.inner_text()).strip()
                        if v:
                            all_opts.append({"value": v, "label": t})
                    all_options[key] = all_opts
                    print(f"      全部选项 ({len(all_opts)}): 已保存到输出文件")
                else:
                    all_options[key] = [o for o in opt_list if o["value"]]
                    
            except Exception as e:
                print(f"  [{i}] 读取失败: {e}")
        
        # 保存全部
        out_json = OUT_DIR / "upload_form_selects.json"
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(all_options, f, ensure_ascii=False, indent=2)
        print(f"\n[√] 所有选项已导出: {out_json}")
        
        # 特别标注 scene 相关字段
        print("\n[=] ============ SCENE 相关字段 ============")
        for key, opts in all_options.items():
            if "scene" in key.lower():
                print(f"\n  {key} ({len(opts)} 项):")
                for o in opts[:20]:
                    print(f"    {o['value']} => {o['label']}")
                if len(opts) > 20:
                    print(f"    ... 还有 {len(opts)-20} 项")
        
        await asyncio.sleep(1)
        await ctx.close()
        print("\n[√] 完成")

if __name__ == "__main__":
    asyncio.run(main())
