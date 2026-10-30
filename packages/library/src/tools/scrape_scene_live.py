"""
交互式提取 scene 选项：
1. 打开可见浏览器到上传页
2. 用户手动登录（如需要）、手动点击打开 scene 下拉
3. 用户切换到终端按 Enter
4. 脚本自动提取所有可见的 scene 选项
"""
import asyncio, json, sys, io
from pathlib import Path
from playwright.async_api import async_playwright

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

UPLOAD_URL = "https://publish.example.com/vendors?tab=upload"
PROFILE = r"./vendor"
OUTPUT = Path(r"./vendor")

async def main():
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            PROFILE, headless=False, viewport={"width": 1280, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        print("🌐 打开上传页面...")
        await page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
        print(f"   当前 URL: {page.url}")

        print("\n" + "=" * 60)
        print("📌 请在浏览器窗口中操作：")
        print("   1) 如果没登录，请先登录")
        print("   2) 切换到 Upload 标签页")
        print("   3) 滚动到场景区域，点击打开 scene 下拉框")
        print("   4) 下拉打开后，切换回这个终端按 Enter")
        print("=" * 60)

        input("\n✅ 场景下拉已打开？按 Enter 继续提取...")

        # 截图
        await page.screenshot(path=str(Path(r"./vendor")))
        print("   📸 已截图")

        # 提取选项 - 多种策略
        print("\n🔍 提取下拉选项...")

        options = await page.evaluate("""() => {
            const results = [];
            const foundSources = [];

            // 策略1: role="option" / role="listbox"
            const ropts = document.querySelectorAll('[role="option"]');
            if (ropts.length > 5) {
                foundSources.push(`[role="option"] x ${ropts.length}`);
                ropts.forEach(el => {
                    const txt = el.textContent.trim();
                    if (txt && txt.length > 0 && txt.length < 200 && !results.find(r => r.label === txt))
                        results.push({value: txt, label: txt});
                });
            }

            // 策略2: Ant Design
            const antItems = document.querySelectorAll('.ant-select-item-option-content, .ant-select-item-option, .ant-select-item');
            if (antItems.length > 0) {
                foundSources.push(`ant-select x ${antItems.length}`);
                antItems.forEach(el => {
                    const txt = el.textContent.trim();
                    if (txt && txt.length < 200 && !results.find(r => r.label === txt))
                        results.push({value: txt, label: txt});
                });
            }

            // 策略3: 虚拟滚动列表
            const virtualItems = document.querySelectorAll('.rc-virtual-list-holder-inner > *, [class*="virtual"] li, [class*="Virtual"] li');
            if (virtualItems.length > 0) {
                foundSources.push(`virtual list x ${virtualItems.length}`);
                virtualItems.forEach(el => {
                    const txt = el.textContent.trim();
                    if (txt && txt.length < 200 && !results.find(r => r.label === txt))
                        results.push({value: txt, label: txt});
                });
            }

            // 策略4: popup/dropdown/menu 中的 li
            for (const sel of ['[class*="dropdown"] li', '[class*="popup"] li', '[class*="menu"] li', '[class*="overlay"] li']) {
                const items = document.querySelectorAll(sel);
                if (items.length > 5 && results.length < 20) {
                    foundSources.push(`${sel} x ${items.length}`);
                    items.forEach(el => {
                        const txt = el.textContent.trim();
                        if (txt && txt.length < 200 && !results.find(r => r.label === txt))
                            results.push({value: txt, label: txt});
                    });
                }
            }

            // 策略5: body > div portal (非 vendors-root)
            document.querySelectorAll('body > div').forEach(div => {
                if (div.className === 'vendors-root') return;
                if (div.id === 'clerk-components') return;
                const lis = div.querySelectorAll('li');
                if (lis.length > 5) {
                    foundSources.push(`portal div li x ${lis.length}`);
                    lis.forEach(el => {
                        const txt = el.textContent.trim();
                        if (txt && txt.length < 200 && !results.find(r => r.label === txt))
                            results.push({value: txt, label: txt});
                    });
                }
                // 也要看 div 内的直接文本选项
                const spans = div.querySelectorAll('span, div > *');
                if (spans.length > 5 && results.length < 5) {
                    spans.forEach(el => {
                        if (el.children.length === 0) {
                            const txt = el.textContent.trim();
                            if (txt && txt.length > 1 && txt.length < 200 && !results.find(r => r.label === txt))
                                results.push({value: txt, label: txt});
                        }
                    });
                }
            });

            // 策略6: 所有 portal div (可能是自定义 react 渲染)
            if (results.length < 5) {
                document.querySelectorAll('body > div').forEach(div => {
                    if (div.querySelector('input')) return; // 跳过有 input 的（可能是搜索）
                    const allTextNodes = div.querySelectorAll('*');
                    const texts = [];
                    allTextNodes.forEach(el => {
                        if (el.children.length === 0 && el.textContent.trim().length > 1) {
                            texts.push(el.textContent.trim());
                        }
                    });
                    if (texts.length > 10) {
                        foundSources.push(`body>div text nodes x ${texts.length}`);
                        texts.forEach(t => {
                            if (t && !results.find(r => r.label === t)) results.push({value: t, label: t});
                        });
                    }
                });
            }

            return {options: results, sources: foundSources};
        }""")

        opt_list = options.get("options", [])
        print(f"   来源: {options.get('sources', [])}")
        print(f"   找到 {len(opt_list)} 个选项")

        # 过滤掉明显的非选项项（页面UI文本等）
        # 场景选项通常是简短的词组
        filtered = []
        skip_patterns = [
            "What's new", "View all updates", "Important", "Update 06/",
            "Choose capture mode", "Pick files for", "Fill in attributes",
            "Upload to server", "CAPTURE MODE", "required", "Single-cam",
            "Three-Views", "Stereo", "Quick tips", "Preview", "TASK ATTRIBUTES",
            "required left", "Operator name", "operator-job", "operator-consent",
            "task_difficulty", "Task description", "Environment description",
            "ENVIRONMENT", "gps_coordinates", "country", "state_province",
            "city", "Location address", "facility", "venue", "business_type",
            "business_name", "OPERATOR", "age_range", "gender", "handedness",
            "gloves", "workforce_type", "role_experience", "task_experience",
            "collection_hours", "collection_experience", "hand_size",
            "RECENT UPLOADS", "session_", "ViewCopy attributes", "Sample Platform",
            "MANAGER", "Progress", "Application", "Profile", "Upload",
            "Upload History", "Operators", "Updates", "Payments",
            "How to hardware", "historical videos", "support delete",
            "support mcap", "Open /vendors", "Pilot:", "No distortion",
            "GoPro", "Industrial/Lab"
        ]
        for o in opt_list:
            if any(s.lower() in o["label"].lower() for s in skip_patterns):
                continue
            if o["label"].startswith(("✓", "→", "⚠")):
                continue
            if len(o["label"]) < 2:
                continue
            filtered.append(o)

        OUTPUT.write_text(json.dumps({
            "totalRaw": len(opt_list),
            "filtered": len(filtered),
            "options": filtered,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"\n   过滤后: {len(filtered)} 个选项")
        for o in filtered[:30]:
            print(f"   {o['label']}")
        if len(filtered) > 30:
            print(f"   ... 还有 {len(filtered) - 30} 项")

        print(f"\n💾 已保存到: {OUTPUT}")

        input("\n按 Enter 关闭浏览器...")
        await ctx.close()

if __name__ == "__main__":
    asyncio.run(main())
