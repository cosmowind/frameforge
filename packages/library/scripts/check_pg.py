"""Check PostgreSQL database for upload-ready videos."""
import sys
sys.path.insert(0, 'src')
from config import USE_PG, PG_DSN

if USE_PG:
    import psycopg2
    conn = psycopg2.connect(PG_DSN)
    cur = conn.cursor()

    # Count unuploaded videos
    cur.execute("""
        SELECT COUNT(*) FROM video_manager
        WHERE uploaded != 'Yes' OR uploaded IS NULL
    """)
    total = cur.fetchone()[0]
    print(f'Unuploaded in DB: {total}')

    # Count with complete form data
    cur.execute("""
        SELECT COUNT(*) FROM video_manager
        WHERE (uploaded != 'Yes' OR uploaded IS NULL)
        AND recorder_id IS NOT NULL AND recorder_id != ''
        AND task_id IS NOT NULL AND task_id != ''
        AND env_id IS NOT NULL AND env_id != ''
    """)
    complete = cur.fetchone()[0]
    print(f'Unuploaded + complete form: {complete}')

    # Show examples
    cur.execute("""
        SELECT path, recorder_id, task_id, env_id, uploaded
        FROM video_manager
        WHERE (uploaded != 'Yes' OR uploaded IS NULL)
        AND recorder_id IS NOT NULL AND recorder_id != ''
        AND task_id IS NOT NULL AND task_id != ''
        AND env_id IS NOT NULL AND env_id != ''
        LIMIT 20
    """)
    rows = cur.fetchall()
    print(f'\nReady to upload (first 20):')
    for r in rows:
        path = r[0]
        if path:
            session = path.replace('\\', '/').split('/')[-1]
        else:
            session = 'N/A'
        print(f'  [{r[0]}] {session}  recorder={r[1]}  task={str(r[2])[:20] if r[2] else None}...  env={r[3]}')

    conn.close()
else:
    print("USE_PG=False - not using database")
