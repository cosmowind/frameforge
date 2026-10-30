import csv

# Fix tasks.csv
with open('runtime/data/tasks.csv', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys())

changed = 0
for r in rows:
    v = r.get('business_type', '')
    if v.strip() == 'sanitary ware production':
        r['business_type'] = '卫浴用品生产'
        changed += 1

with open('runtime/data/tasks.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)
print('tasks.csv changed:', changed)

# Fix VALUE_MAP in auto_upload.py
with open('src/auto_upload.py', encoding='utf-8') as f:
    content = f.read()

old = '"sanitary ware production": "卫生用品生产"'
new = '"sanitary ware production": "卫浴用品生产"'
if old in content:
    content = content.replace(old, new, 1)
    print('Fixed VALUE_MAP')
else:
    print('VALUE_MAP already fixed or pattern not found')

with open('src/auto_upload.py', 'w', encoding='utf-8') as f:
    f.write(content)
