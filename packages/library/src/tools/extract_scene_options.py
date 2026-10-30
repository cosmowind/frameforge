#!/usr/bin/env python3
"""
打开可见浏览器，让用户登录后自动提取上传页面的 scene 下拉选项。
"""
import asyncio
import json
import os
import sys
from pathlib import Path

# 添加项目根目录到 path
PROJ_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ_DIR))

from auto_upload import UPLOAD_URL, BROWSER_DATA_DIR

OUTPUT_FILE = PROJ_DIR / "tools" / "scene_options_live.json"

async def main():
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("[!] playwright 未安装，请运行: pip install playwright")
        return

    async with async_playwright() as p:
        # 使用 launch() 而非 launch_persistent_context，避免 profile 锁定问题
        browser = await p.chromium.launch(
            headless=False,
            args=["--no-sandbox"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()

        print(f"[*] 打开浏览器，导航到: {UPLOAD_URL}")
        print("[*] 如果看到登录页，请先登录 FrameForge...")
        await page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=60000)

        # 等待用户登录（最长10分钟）
        print("[*] 等待登录或上传表单加载...")
        deadline = asyncio.get_event_loop().time() + 600
        scene_select = None
        while asyncio.get_event_loop().time() < deadline:
            try:
                # 检查是否有 scene 下拉框
                scene_el = page.locator("select[data-field='scene']")
                count = await scene_el.count()
                if count > 0:
                    print("[✓] 发现 scene 下拉框！")
                    scene_select = scene_el.first
                    break

                # 也尝试其他可能的 scene 选择器
                alt_el = page.locator("select[name*='scene'], select[id*='scene'], select[data-field*='Scene']")
                alt_count = await alt_el.count()
                if alt_count > 0:
                    print(f"[✓] 发现可能的 scene 下拉框 ({alt_count} 个)")
                    scene_select = alt_el.first
                    break
            except Exception:
                pass

            await asyncio.sleep(2)
            # 打印等待进度
            try:
                url = page.url
                if any(kw in url.lower() for kw in ("sign-in", "login", "signin", "signup", "sign-up")):
                    print("   ... 等待登录中，请在浏览器窗口登录 ...")
                elif "vendors" in url.lower():
                    print("   ... 等待上传表单加载 ...")
            except Exception:
                pass

        if not scene_select:
            print("[✗] 超时：未能在10分钟内找到 scene 下拉框")
            print(f"[*] 当前页面 URL: {page.url}")
            # 打印页面上所有 select 元素帮助诊断
            all_selects = await page.locator("select").all()
            for s in all_selects:
                try:
                    name = await s.get_attribute("name") or ""
                    df = await s.get_attribute("data-field") or ""
                    sid = await s.get_attribute("id") or ""
                    print(f"   select: name={name}, data-field={df}, id={sid}")
                except Exception:
                    pass
            await browser.close()
            return

        # 提取所有 option
        print("[*] 提取 scene 选项...")
        options = await scene_select.locator("option").all()
        results = []
        for opt in options:
            try:
                val = await opt.get_attribute("value") or ""
                text = (await opt.inner_text()).strip()
                if val:  # 跳过空的占位 option
                    results.append({"value": val, "label": text})
            except Exception:
                continue

        print(f"[✓] 成功提取 {len(results)} 个 scene 选项")

        # 保存到文件
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"[✓] 已保存到: {OUTPUT_FILE}")
        print("\n前20个选项预览:")
        for r in results[:20]:
            print(f"  {r['value']}  →  {r['label']}")

        # 同时显示选项总数
        print(f"\n... 共 {len(results)} 个选项")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
