#!/usr/bin/env python3
"""从 Playwright 持久化浏览器上下文中提取 Clerk __session cookie。

用法：
  python scripts/extract_cookie.py              # 输出到 stdout
  python scripts/extract_cookie.py -o cookie.txt  # 写入文件
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

_SELF_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _SELF_DIR.parent
_SRC_DIR = _ROOT_DIR / "src"

sys.path.insert(0, str(_SRC_DIR))

BROWSER_DATA_DIR = str(_ROOT_DIR / "runtime" / "browser_data")


async def extract(output: str | None = None):
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    ctx = await pw.chromium.launch_persistent_context(
        BROWSER_DATA_DIR,
        headless=True,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
    )

    cookies = await ctx.cookies("https://publish.example.com")
    session = None
    client = None
    client_uat = None

    for c in cookies:
        if c["name"] == "__session":
            session = c["value"]
        elif c["name"] == "__client":
            client = c["value"]
        elif c["name"] == "__client_uat":
            client_uat = c["value"]

    await ctx.close()
    await pw.stop()

    if not session:
        print("ERROR: __session cookie not found. Please log in to publish.example.com first.",
              file=sys.stderr)
        sys.exit(1)

    lines = [f"SESSION={session}"]
    if client:
        lines.append(f"CLIENT={client}")
    if client_uat:
        lines.append(f"CLIENT_UAT={client_uat}")

    content = "\n".join(lines) + "\n"

    if output:
        Path(output).write_text(content, encoding="utf-8")
        print(f"Cookie saved to {output}")
    else:
        print(content)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--output", help="Output file path")
    args = ap.parse_args()
    asyncio.run(extract(args.output))


if __name__ == "__main__":
    main()
