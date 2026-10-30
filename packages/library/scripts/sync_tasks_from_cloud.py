"""Sync missing tasks from cloud PostgreSQL to local tasks.csv."""
import psycopg2
import csv
import os

# Connect to cloud DB
cloud_conn = psycopg2.connect('postgresql://ffuser:changeme@db.example.com:5432/video_manager')
cloud_cur = cloud_conn.cursor()

# Read local tasks.csv
csv_path = 'runtime/data/tasks.csv'
with open(csv_path, 'r', encoding='utf-8-sig') as f:
    local_tasks = list(csv.DictReader(f))
    fieldnames = list(local_tasks[0].keys())

existing_ids = {r['task_id'].strip() for r in local_tasks}
print(f'Local tasks.csv: {len(local_tasks)} records, {len(existing_ids)} unique task_ids')

# Get ALL tasks from cloud DB
cloud_cur.execute('SELECT task_id, scene, product, task, tool, process, process_en, difficulty, quota_min, location_address, business_type, business_name, environment, environment_description, environment_description_en, facility_venue, notes FROM tasks')
cloud_rows = cloud_cur.fetchall()
cloud_cur.close()
cloud_conn.close()

# Find missing tasks
missing = []
for row in cloud_rows:
    tid = row[0]
    if tid and tid.strip() not in existing_ids:
        missing.append(row)

print(f'Cloud DB: {len(cloud_rows)} tasks, missing from local: {len(missing)}')

if missing:
    print(f'\nWill add {len(missing)} tasks to local CSV:')
    for row in missing:
        print(f'  {row[0]}  {row[2]}/{row[3]}  [{row[6]}]')

    # Append to local CSV
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(local_tasks)
        for row in missing:
            d = dict(zip(fieldnames, row))
            w.writerow(d)

    print(f'\nAppended {len(missing)} tasks to {csv_path}')

    # Verify
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        new_tasks = list(csv.DictReader(f))
    print(f'New total: {len(new_tasks)} tasks')
else:
    print('No missing tasks - already in sync!')
