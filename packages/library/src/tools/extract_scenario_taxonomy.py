#!/usr/bin/env python3
"""Extract the v2 scene taxonomy from frameforge's scene-taxonomy-v2.ts into a
flat JSON list of leaf tasks + a Markdown reference table.

Usage:
    python3 tools/extract_scenario_taxonomy.py <path-to-scene-taxonomy-v2.ts>

Outputs:
    tools/scenario-taxonomy.json   — flat array of {id, labelId, name, slug,
                                       domain, sector, category}
    tools/scenario-taxonomy.md     — Markdown table grouped by domain › sector
                                   › category, with English + Chinese names

The Chinese names below are best-effort translations of the English labels
(see ../MCAP 交付规范(供应商版).md naming conventions) for the vendor portal
preset-options UI. Adjust them to match the portal's wording before shipping.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from tools.taxonomy_translations import (
    CATEGORY_EN_TO_ZH,
    DOMAIN_EN_TO_ZH,
    EN_TO_ZH,
    SECTOR_EN_TO_ZH,
    zh,
)


# ---------------------------------------------------------------------------

RE_ID = re.compile(r"id:\s*'([^']+)'")
RE_NAME = re.compile(r"name:\s*'([^']+)'")
RE_LABEL_ID = re.compile(r"labelId:\s*(\d+)")
RE_SLUG = re.compile(r"slug:\s*'([^']+)'")


def parse_taxonomy(ts_text: str) -> list[dict]:
    """Walk the TS source line-by-line. Properties may appear on separate lines
    (e.g. `id:` on one line, `name:` on the next), so we accumulate them per
    object literal and flush when we hit the closing `},`.

    Object boundaries:
      - Domain:    id starts with 'D' + digits, no `-`
      - Sector:    id matches 'D\\d+-S\\d+'
      - Category:  id matches 'D\\d+-S\\d+-C\\d+'
      - Task:      id matches 'D\\d+-S\\d+-C\\d+-T\\d+'
    """
    current_domain = None  # (id, name)
    current_sector = None
    current_category = None
    leaves = []

    pending = {'id': None, 'name': None, 'labelId': None, 'slug': None}

    def flush_task():
        if (pending['id'] and pending['name'] is not None
                and pending['labelId'] is not None and pending['slug'] is not None
                and re.fullmatch(r'D\d+-S\d+-C\d+-T\d+', pending['id'])):
            if current_domain and current_sector and current_category:
                leaves.append({
                    'id': pending['id'],
                    'labelId': int(pending['labelId']),
                    'name': pending['name'],
                    'slug': pending['slug'],
                    'domain_id': current_domain[0],
                    'domain': current_domain[1],
                    'sector_id': current_sector[0],
                    'sector': current_sector[1],
                    'category_id': current_category[0],
                    'category': current_category[1],
                })
        pending['id'] = None
        pending['name'] = None
        pending['labelId'] = None
        pending['slug'] = None

    for line in ts_text.splitlines():
        line = line.rstrip()

        # An object literal closes with `},` (or just `}`).
        if line.endswith('},') or line == '}':
            flush_task()
            continue

        if (m := RE_ID.search(line)):
            pid = m.group(1)
            if re.fullmatch(r'D\d+', pid):
                # New domain — clear any pending task props.
                flush_task()
                current_domain = (pid, None)
                current_sector = None
                current_category = None
            elif re.fullmatch(r'D\d+-S\d+', pid):
                flush_task()
                current_sector = (pid, None)
                current_category = None
            elif re.fullmatch(r'D\d+-S\d+-C\d+', pid):
                flush_task()
                current_category = (pid, None)
            elif re.fullmatch(r'D\d+-S\d+-C\d+-T\d+', pid):
                # New task — start a fresh pending block.
                pending['id'] = pid
                pending['name'] = None
                pending['labelId'] = None
                pending['slug'] = None
            continue

        if (m := RE_NAME.search(line)):
            name = m.group(1)
            # Attach name to the appropriate scope based on what's currently
            # missing. Domain takes priority over sector over category (since
            # when a domain id landed we cleared current_sector / category,
            # but the domain's `name:` is the only one we can attach).
            if current_domain and current_domain[1] is None and re.fullmatch(r'D\d+', current_domain[0]):
                current_domain = (current_domain[0], name)
            elif current_sector and current_sector[1] is None and re.fullmatch(r'D\d+-S\d+', current_sector[0]):
                current_sector = (current_sector[0], name)
            elif current_category and current_category[1] is None and re.fullmatch(r'D\d+-S\d+-C\d+', current_category[0]):
                current_category = (current_category[0], name)
            else:
                # Otherwise this is a task `name:`.
                pending['name'] = name
            continue

        if (m := RE_LABEL_ID.search(line)):
            pending['labelId'] = int(m.group(1))
            continue

        if (m := RE_SLUG.search(line)):
            pending['slug'] = m.group(1)
            continue

    # Flush any trailing task at EOF.
    flush_task()
    return leaves


def render_markdown(leaves: list[dict]) -> str:
    out = []
    out.append('# Scenario Taxonomy — v2 参考\n')
    out.append('本文档对应 publish.example.com/vendors task-box 创建时 `--scenario` 参数的合法取值列表。\n')
    out.append(f'总计 **{len(leaves)}** 个叶子 task(对应 10 个 domain × 37 个 sector × 106 个 category)。\n')
    out.append('> 数据来源:`F:\\sys\\o\\frameforge\\frameforge\\frameforge\\src\\lib\\scene-taxonomy-v2.ts` '
               '(upstream `origin/master`)')
    out.append('> 中文翻译为人工整理;**不存在的翻译会回退为英文**,请补全后再发布给前端。\n')

    # Translation-coverage summary at the top so the frontend dev sees what to
    # finish. We re-import the dicts already declared at module scope.
    missing_tasks = [l for l in leaves if zh(l['name']) == l['name']]
    missing_sectors = sorted({l['sector'] for l in leaves} - set(SECTOR_EN_TO_ZH.keys()))
    missing_cats = sorted({l['category'] for l in leaves} - set(CATEGORY_EN_TO_ZH.keys()))
    out.append('## 翻译覆盖率\n')
    out.append(f'- task:已翻译 {len(leaves) - len(missing_tasks)}/{len(leaves)},'
               f' 待补 {len(missing_tasks)} 个(完整列表见末尾"待翻译 task"小节)')
    out.append(f'- sector:已翻译 {len(SECTOR_EN_TO_ZH)}/{len({l["sector"] for l in leaves})},'
               f' 待补 {len(missing_sectors)} 个')
    out.append(f'- category:已翻译 {len(CATEGORY_EN_TO_ZH)}/{len({l["category"] for l in leaves})},'
               f' 待补 {len(missing_cats)} 个\n')

    out.append('## 用法\n')
    out.append('```bash')
    out.append('python3 upload_pkg.py \\')
    out.append('    --cookie-file ./cookie.txt \\')
    out.append(f'    --scenario {leaves[0]["id"]} \\')
    out.append(f'    --task-description "{leaves[0]["name"]}" \\')
    out.append('    --environment-description "..." \\')
    out.append('    --operator-name "..." \\')
    out.append('    --capture-mode stereo \\')
    out.append('    --session-dir ./captures/session_000001')
    out.append('```\n')

    # Group by domain → sector → category.
    from collections import OrderedDict
    by_domain: dict = OrderedDict()
    for leaf in leaves:
        d = by_domain.setdefault(leaf['domain_id'], {'name': leaf['domain'], 'sectors': OrderedDict()})
        s = d['sectors'].setdefault(leaf['sector_id'], {'name': leaf['sector'], 'categories': OrderedDict()})
        c = s['categories'].setdefault(leaf['category_id'], {'name': leaf['category'], 'tasks': []})
        c['tasks'].append(leaf)

    for d_id, d in by_domain.items():
        out.append(f'## {d_id} {d["name"]} / {DOMAIN_EN_TO_ZH.get(d["name"], d["name"])}\n')
        for s_id, s in d['sectors'].items():
            out.append(f'### {s_id} {s["name"]} / {SECTOR_EN_TO_ZH.get(s["name"], s["name"])}\n')
            for c_id, c in s['categories'].items():
                out.append(f'#### {c_id} {c["name"]} / {CATEGORY_EN_TO_ZH.get(c["name"], c["name"])}\n')
                out.append('| ID | labelId | English | 中文 | slug |')
                out.append('|---|---|---|---|---|')
                for t in c['tasks']:
                    zh_name = zh(t['name'])
                    out.append(f'| `{t["id"]}` | {t["labelId"]} | {t["name"]} | {zh_name} | `{t["slug"]}` |')
                out.append('')

    # Append a "待翻译 task" listing for quick fill-in by the frontend dev.
    out.append('## 待翻译 task(回退到英文,需补 `EN_TO_ZH` dict)\n')
    out.append(f'共 {len(missing_tasks)} 个。在 `tools/extract_scenario_taxonomy.py` 顶部的 `EN_TO_ZH` 字典里追加键值对,然后重跑脚本即可。\n')
    out.append('| ID | English |')
    out.append('|---|---|')
    for l in sorted(missing_tasks, key=lambda x: x['id']):
        out.append(f'| `{l["id"]}` | {l["name"]} |')
    out.append('')

    if missing_sectors:
        out.append('## 待翻译 sector\n')
        out.append('| English |')
        out.append('|---|')
        for s in missing_sectors:
            out.append(f'| {s} |')
        out.append('')

    if missing_cats:
        out.append('## 待翻译 category\n')
        out.append('| English |')
        out.append('|---|')
        for c in missing_cats:
            out.append(f'| {c} |')
        out.append('')

    return '\n'.join(out)


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit('Usage: extract_scenario_taxonomy.py <path-to-scene-taxonomy-v2.ts>')
    ts_path = Path(sys.argv[1])
    if not ts_path.is_file():
        sys.exit(f'{ts_path} is not a file')
    leaves = parse_taxonomy(ts_path.read_text(encoding='utf-8'))
    if not leaves:
        sys.exit('parser produced 0 leaves — taxonomy format may have changed')

    # Anchor outputs to the video-sort-package project (where this script lives)
    # so the script works regardless of where the frameforge checkout lives.
    project_root = Path(__file__).resolve().parent.parent
    json_out = project_root / 'tools' / 'scenario-taxonomy.json'
    md_out = project_root / 'vendor-upload-pkg' / 'docs' / 'scenario-taxonomy.md'
    json_out.parent.mkdir(parents=True, exist_ok=True)
    md_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(leaves, ensure_ascii=False, indent=2), encoding='utf-8')
    md_out.write_text(render_markdown(leaves), encoding='utf-8')
    print(f'parsed {len(leaves)} leaves')
    print(f'wrote {json_out}')
    print(f'wrote {md_out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())