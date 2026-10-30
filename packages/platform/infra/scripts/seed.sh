#!/usr/bin/env bash
# Phase 0 PG 初始化：创建 ff schema（v1 兼容：现有 ff.schema 保留）
set -euo pipefail

PG_HOST=${POSTGRES_HOST:-localhost}
PG_PORT=${POSTGRES_PORT:-5432}
PG_USER=${POSTGRES_USER:-ff}
PG_DB=${POSTGRES_DB:-ff}
SCHEMA=${DATABASE_SCHEMA:-ff}

until pg_isready -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" >/dev/null 2>&1; do
  echo "waiting pg at $PG_HOST:$PG_PORT..."
  sleep 1
done

echo "==> ensuring schema $SCHEMA"
psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
  -c "CREATE SCHEMA IF NOT EXISTS \"$SCHEMA\""

echo "==> seed super admin + 默认 region"
psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
  -v ON_ERROR_STOP=1 <<SQL
INSERT INTO "$SCHEMA".regions (code, name, is_active)
VALUES ('default', '上海', true)
ON CONFLICT (code) DO NOTHING;
SQL

echo "==> done"
