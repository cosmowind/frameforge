"""从 video_manager.csv 提取 6.19-6.29 每日录制统计
策略：优先 original_history_date（真实录制日期），占位日期(2021-01-01等)兜底用路径MMDD
"""
import csv
import re
from collections import defaultdict
from datetime import date, timedelta

csv_path = r'runtime\data\video_manager.csv'
stats = defaultdict(lambda: {'count': 0, 'total_duration_sec': 0, 'devices': set(),
                              'from_orig': 0, 'from_path': 0})

with open(csv_path, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        path = row.get('path', '')
        orig = row.get('original_history_date', '').strip()
        
        # Extract path date (MMDD)
        m = re.search(r'\\视频\\(\d{4})', path)
        path_date = ''
        if m:
            mmdd = m.group(1)
            mth, dy = int(mmdd[:2]), int(mmdd[2:])
            path_date = f'2026-{mth:02d}-{dy:02d}'
        
        # Determine recording date
        # Use original_history_date if valid and in 6.19-6.29 range
        # Otherwise fall back to path date (for placeholders like 2021-01-01)
        record_date = ''
        source = ''
        if orig:
            try:
                parts = orig.split('-')
                y, mo, d = int(parts[0]), int(parts[1]), int(parts[2])
                if y == 2026 and mo == 6 and 19 <= d <= 29:
                    record_date = orig
                    source = 'orig'
            except (ValueError, IndexError):
                pass
        
        if not record_date and path_date:
            # Check if path_date is in range
            try:
                parts = path_date.split('-')
                y, mo, d = int(parts[0]), int(parts[1]), int(parts[2])
                if y == 2026 and mo == 6 and 19 <= d <= 29:
                    record_date = path_date
                    source = 'path'
            except (ValueError, IndexError):
                pass
        
        if not record_date:
            continue
        
        dur = row.get('duration_sec', '0')
        try:
            dur_sec = float(dur) if dur else 0
        except ValueError:
            dur_sec = 0
        
        device = row.get('device_id', '').strip()
        
        stats[record_date]['count'] += 1
        stats[record_date]['total_duration_sec'] += dur_sec
        if source == 'orig':
            stats[record_date]['from_orig'] += 1
        else:
            stats[record_date]['from_path'] += 1
        if device:
            stats[record_date]['devices'].add(device)

# Generate all dates 6.19-6.29
all_dates = []
start = date(2026, 6, 19)
end = date(2026, 6, 29)
current = start
while current <= end:
    all_dates.append(current.strftime('%Y-%m-%d'))
    current += timedelta(days=1)

# Output CSV
output_path = r'docs\日报_6.19-6.29_本地视频统计.csv'
with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['日期', '视频数量', '录制时长(h)', '设备数量', '设备列表', '备注'])
    
    for date_str in all_dates:
        s = stats.get(date_str, {'count': 0, 'total_duration_sec': 0, 'devices': set(),
                                  'from_orig': 0, 'from_path': 0})
        dur_h = s['total_duration_sec'] / 3600
        devices_sorted = sorted(s['devices'])
        
        # Build note
        note_parts = []
        if s['from_path'] > 0 and s['from_orig'] > 0:
            note_parts.append(f'{s["from_path"]}条为路径日期补充(original_history_date为占位)')
        elif s['from_path'] > 0:
            note_parts.append('全部为路径日期补充(original_history_date为占位)')
        
        note = '; '.join(note_parts) if note_parts else ''
        
        writer.writerow([
            date_str,
            s['count'],
            round(dur_h, 2),
            len(s['devices']),
            ' / '.join(devices_sorted) if devices_sorted else '-',
            note
        ])

# Print to console
print(f'已生成: {output_path}')
print()
print(f'{"日期":<14} {"视频":>4} {"时长(h)":>8} {"设备":>4}  设备列表')
print('-' * 72)
total_count = 0
total_dur = 0
for date_str in all_dates:
    s = stats.get(date_str, {'count': 0, 'total_duration_sec': 0, 'devices': set(),
                              'from_orig': 0, 'from_path': 0})
    dur_h = s['total_duration_sec'] / 3600
    devices_sorted = sorted(s['devices'])
    devices_str = ' / '.join(devices_sorted) if devices_sorted else '-'
    print(f'{date_str:<14} {s["count"]:>4} {dur_h:>8.2f} {len(s["devices"]):>4}  {devices_str}')
    total_count += s['count']
    total_dur += s['total_duration_sec']

print('-' * 72)
print(f'{"合计":<14} {total_count:>4} {total_dur/3600:>8.2f}')
