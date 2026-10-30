#!/usr/bin/env bash
# 每日 pg_dump + csv 备份（Phase 3 完善）
set -euo pipefail

BACKUP_DIR=${BACKUP_DIR:-./runtime/backups/pg}
KEEP=${CSV_ROTATION_KEEP:-10}
TS=$(date +%Y%m%d-%H%M%S)
OUT="${BACKUP_DIR}/ff-${TS}.sql.gz"

mkdir -p "${BACKUP_DIR}"
echo "==> pg_dump -> ${OUT}"
pg_dump -Fc | gzip > "${OUT}"

ls -1t "${BACKUP_DIR}"/ff-*.sql.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm --
echo "==> done. Kept ${KEEP} backups."
