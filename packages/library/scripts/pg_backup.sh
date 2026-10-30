#!/usr/bin/env bash
set -euo pipefail

# pg_backup.sh — PostgreSQL 增量备份脚本
# 依赖: pg_dump, gzip, 本地备份目录
# 用法: ./scripts/pg_backup.sh
# 建议 cron: 0 3 * * * /www/wwwroot/projects/video_manager/scripts/pg_backup.sh >> /var/log/video_manager_pg_backup.log 2>&1

BACKUP_DIR="/www/wwwroot/projects/video_manager/runtime/backups/pg"
RETENTION_DAYS=7
DB_NAME="video_manager"
DB_USER="dev"
DB_HOST="db.example.com"
DB_PORT="5432"
DATE_TAG="$(date +%Y%m%d_%H%M%S)"
DUMP_FILE="${BACKUP_DIR}/${DB_NAME}_${DATE_TAG}.sql.gz"

mkdir -p "${BACKUP_DIR}"

export PGPASSWORD="${PGPASSWORD:-123456}"

echo "[$(date)] 开始备份 ${DB_NAME} -> ${DUMP_FILE}"
pg_dump -U "${DB_USER}" -h "${DB_HOST}" -p "${DB_PORT}" "${DB_NAME}" \
  | gzip > "${DUMP_FILE}"

echo "[$(date)] 备份完成，大小: $(du -h "${DUMP_FILE}" | cut -f1)"

# 清理旧备份
find "${BACKUP_DIR}" -name "${DB_NAME}_*.sql.gz" -mtime +${RETENTION_DAYS} -delete 2>/dev/null || true
echo "[$(date)] 清理 ${RETENTION_DAYS} 天前的备份完成"
