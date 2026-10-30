"""Sync all dimension tables from cloud PostgreSQL to local CSV files."""
import psycopg2
import csv
import os

cloud_conn = psycopg2.connect('postgresql://ffuser:changeme@db.example.com:5432/video_manager')
cloud_cur = cloud_conn.cursor()

def sync_dim(table_name, key_field, local_file):
    print(f'\n=== Syncing {table_name} ===')

    # Get cloud data
    cloud_cur.execute(f'SELECT * FROM {table_name}')
    cloud_rows = cloud_cur.fetchall()
    cloud_col_names = [desc[0] for desc in cloud_cur.description]
    print(f'Cloud DB: {len(cloud_rows)} records')

    # Read local CSV
    local_path = f'runtime/data/{local_file}'
    with open(local_path, 'r', encoding='utf-8-sig') as f:
        local_rows = list(csv.DictReader(f))
        fieldnames = list(local_rows[0].keys()) if local_rows else cloud_col_names
    print(f'Local CSV: {len(local_rows)} records')

    existing_keys = {r[key_field].strip() for r in local_rows if r.get(key_field)}

    # Find missing
    missing = []
    for row in cloud_rows:
        d = dict(zip(cloud_col_names, row))
        key = d.get(key_field, '').strip()
        if key and key not in existing_keys:
            missing.append(d)

    print(f'Missing from local: {len(missing)}')
    if missing:
        for r in missing:
            print(f'  + {r.get(key_field)}: {r}')

        # Append missing
        with open(local_path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            w.writeheader()
            w.writerows(local_rows)
            w.writerows(missing)

        with open(local_path, 'r', encoding='utf-8-sig') as f:
            new_count = len(list(csv.DictReader(f)))
        print(f'Updated {local_path}: now {new_count} records')
    else:
        print('Already in sync!')

# Sync recorders
sync_dim('recorders', 'id', 'recorders.csv')

# Sync environments
sync_dim('environments', 'env_id', 'environments.csv')

# Sync tasks (already done)
sync_dim('tasks', 'task_id', 'tasks.csv')

cloud_cur.close()
cloud_conn.close()
print('\n=== All dimension tables synced! ===')
