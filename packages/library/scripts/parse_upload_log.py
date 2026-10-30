#!/usr/bin/env python3
"""解析 upload 日志，提取关键结果"""
import re
import sys
from collections import namedtuple

def parse_log(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    total = 0
    success = []
    fail = []
    fail_reasons = {}

    for line in lines:
        # 汇总行
        m = re.search(r'流水线上传完成:\s*(\d+)\s*成功,\s*(\d+)\s*失败,\s*共\s*(\d+)', line)
        if m:
            total = int(m.group(3))
            print(f"[汇总] {m.group(1)} 成功, {m.group(2)} 失败, 共 {m.group(3)} 个")
            print()

        # 成功
        m = re.search(r'✓\s+(\S+)\s+上传成功', line)
        if m:
            success.append(m.group(1))

        # 超时失败
        m = re.search(r'⚠\s+(\S+)\s+在 inflight 中超过 600s.*强制标记失败', line)
        if m:
            name = m.group(1)
            fail.append(name)
            reason = "上传超时（inflight > 600s），可能是服务器上传队列拥堵或网络问题"
            fail_reasons[name] = reason

    print(f"{'='*70}")
    print(f"[成功] {len(success)} 个")
    print(f"{'='*70}")
    for s in success:
        print(f"  [OK] {s}")

    print()
    print(f"{'='*70}")
    print(f"[失败] {len(fail)} 个")
    print(f"{'='*70}")
    for i, f in enumerate(fail, 1):
        reason = fail_reasons.get(f, "未知")
        print(f"  [{i:2d}] [FAIL] {f}")
        print(f"       原因: {reason}")
        print()

    # 按日期分组统计
    print(f"{'='*70}")
    print(f"[按批次/日期分组]")
    print(f"{'='*70}")
    
    def group_by_prefix(names):
        groups = {}
        for n in names:
            prefix = n[:4]  # 0621, 0622, 0627
            groups.setdefault(prefix, []).append(n)
        return groups

    succ_groups = group_by_prefix(success)
    fail_groups = group_by_prefix(fail)

    all_dates = sorted(set(list(succ_groups.keys()) + list(fail_groups.keys())))
    for date in all_dates:
        s_count = len(succ_groups.get(date, []))
        f_count = len(fail_groups.get(date, []))
        print(f"  {date}: 成功 {s_count}, 失败 {f_count}")

    # 再按 session 前缀细分组
    print()
    print(f"{'='*70}")
    print(f"[按 session 前缀分组]")
    print(f"{'='*70}")
    
    def group_by_session_prefix(names):
        groups = {}
        for n in names:
            # e.g. 0621_4aa45c_session_00004 -> 0621_4aa45c
            prefix = '_'.join(n.split('_')[:2])
            groups.setdefault(prefix, []).append(n)
        return groups

    succ_sg = group_by_session_prefix(success)
    fail_sg = group_by_session_prefix(fail)

    all_sessions = sorted(set(list(succ_sg.keys()) + list(fail_sg.keys())))
    for session in all_sessions:
        s_list = sorted(succ_sg.get(session, []))
        f_list = sorted(fail_sg.get(session, []))
        print(f"  {session}:")
        for s in s_list:
            print(f"    [OK] {s}")
        for f in f_list:
            print(f"    [FAIL] {f} (超时)")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        path = r'./vendor'
    parse_log(path)
