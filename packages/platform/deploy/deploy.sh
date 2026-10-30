#!/bin/bash
# FrameForge 服务器端 deploy 脚本
# 由 GitHub Actions 通过 SSH 调起（也可手动跑）
# 输入：$DEPLOY_PATH（默认 /www/wwwroot/projects/ff）

set -euo pipefail

DEPLOY_PATH="${DEPLOY_PATH:-/www/wwwroot/projects/ff}"
cd "$DEPLOY_PATH" || { echo "❌ DEPLOY_PATH not found: $DEPLOY_PATH"; exit 1; }

echo "============================================"
echo "FrameForge deploy @ $(date -Iseconds)"
echo "PATH = $DEPLOY_PATH"
echo "============================================"

# ====== 1. 拉代码 ======
echo "→ git fetch + reset"
git fetch origin main
git reset --hard origin/main
git log --oneline -3

# ====== 2. 装依赖（lockfile 没变就 0 改动）======
echo "→ pnpm install"
pnpm install --frozen-lockfile=false

# ====== 3. Build（Next.js standalone 已开）======
echo "→ pnpm build"
pnpm --filter @ff/shared build
pnpm --filter @ff/web-uploader build
pnpm --filter @ff/web-admin build
pnpm --filter @ff/worker build

# ====== 4. 跑 v2 migration（IF NOT EXISTS 兜底）======
# 取 .env 里的 DATABASE_URL
if [ -f .env ]; then
  set -a; source .env; set +a
fi

if [ -n "${DATABASE_URL:-}" ]; then
  echo "→ psql: v2_frameforge_v2_forms.sql (IF NOT EXISTS)"
  PGPASSWORD="${POSTGRES_PASSWORD:-}" psql "$DATABASE_URL" \
    -f packages/db-schema/src/migrations/v2_frameforge_v2_forms.sql \
    -v ON_ERROR_STOP=1 \
    || echo "⚠ migration 失败（IF NOT EXISTS 重复跑通常无害）"
fi

# ====== 5. pm2 reload（零停机）======
echo "→ pm2 reload"
pm2 reload deploy/ecosystem.config.cjs || pm2 start deploy/ecosystem.config.cjs
pm2 save

# ====== 6. 健康检查 ======
sleep 3
echo "→ health check"
echo -n "  web-uploader: "
if curl -fsS http://127.0.0.1:3001/api/health > /dev/null; then
  echo "✅"
else
  echo "❌（查 pm2 logs web-uploader）"
  exit 1
fi

echo -n "  web-admin:    "
if curl -fsS http://127.0.0.1:3002/api/health > /dev/null; then
  echo "✅"
else
  echo "❌（查 pm2 logs web-admin）"
  exit 1
fi

echo -n "  redis:        "
if redis-cli ping > /dev/null; then
  echo "✅"
else
  echo "❌（systemctl status redis）"
  exit 1
fi

echo ""
echo "✅ Deploy done @ $(date -Iseconds)"
pm2 list
