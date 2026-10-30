#!/usr/bin/env bash
# 每日 03:00 pg_dump public.videos + ff.* + 保留 10 份
# 用法：./scripts/backup-videos.sh
# 或 cron：0 3 * * * /path/to/ff/scripts/backup-videos.sh

set -euo pipefail

BACKUP_DIR=${BACKUP_DIR:-./runtime/backups/manual}
KEEP=${BACKUP_CSV_ROTATION_KEEP:-10}
TS=$(date +%Y%m%d-%H%M%S)

mkdir -p "${BACKUP_DIR}"

echo "==> backup pg → ${BACKUP_DIR}/all-${TS}.sql.gz"
# 备份 public + ff schema（不含 pg_catalog / information_schema）
pg_dump -Fc \
  --exclude-schema=pg_catalog \
  --exclude-schema=information_schema \
  --no-owner \
  | gzip > "${BACKUP_DIR}/all-${TS}.sql.gz"

# 单独备份 public.videos（业务主表，最敏感）
echo "==> backup public.videos → ${BACKUP_DIR}/videos-${TS}.csv"
psql -At -F, -c "SELECT * FROM public.videos ORDER BY scan_date DESC, path" \
  > "${BACKUP_DIR}/videos-${TS}.csv"

# 单独备份 ff.* 表（plan2 新表）
echo "==> backup ff.* → ${BACKUP_DIR}/ff-${TS}.sql"
pg_dump --schema=ff --no-owner --inserts \
  > "${BACKUP_DIR}/ff-${TS}.sql"

# 保留最近 10 份
ls -1t "${BACKUP_DIR}"/all-*.sql.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm --
ls -1t "${BACKUP_DIR}"/videos-*.csv 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm --
ls -1t "${BACKUP_DIR}"/ff-*.sql 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm --

echo "==> done. Kept ${KEEP} backups each."
ls -lth "${BACKUP_DIR}" | head -10