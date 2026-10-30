# FrameForge 生产部署手册（OpenCloudOS 9 + 宝塔 + pm2）

> **目标环境**：腾讯云 CVM（OpenCloudOS 9 应用镜像 + 宝塔面板）· vps.example.com
> **架构**：pm2 跑 web (3001) + worker + nginx 反代 + HTTPS (Let's Encrypt)
> **CI/CD**：GitHub Actions（private repo 免费 2000 分钟/月，0 成本）
> **配套清单**：[docs/DEPLOY-CHECKLIST.md](DEPLOY-CHECKLIST.md) — 按步骤手把手执行

---

## 0. 网络拓扑

```
[手机/电脑浏览器]
       │ HTTPS
       ▼
[宝塔 Nginx (80/443) ← Let's Encrypt 证书]
       │ proxy_pass http://127.0.0.1:3001 (uploader)
       │ proxy_pass http://127.0.0.1:3002 (admin)
       ▼
[pm2 process: web-uploader (3001)]
[pm2 process: web-admin    (3002)]
[pm2 process: worker       (3010)]
       │
       ├─→ [Postgres 8.x @ 另一台 8.x.x.x:5432 · db: ff · schema: ff]
       └─→ [Redis 6379 @ localhost（本机安装）]
```

| 进程 | 端口 | 用途 |
|---|---|---|
| `web-uploader` | 3001 | Next.js 录制员端（手机/电脑访问）|
| `web-admin`    | 3002 | Next.js 管理员端（PC）|
| `worker`       | 3010 | BullMQ 消费（设备扫描 / 预览 / Puller / 备份）|
| `redis`        | 6379 | BullMQ 后端 + 缓存 |
| `postgres`     | 5432 | 业务库（远端 8.x 主机）|

---

## 1. 服务器前置准备（一次性 SSH 跑）

### 1.1 登录服务器

```bash
ssh root@vps.example.com
```

### 1.2 安装 Redis（OpenCloudOS 9 用 dnf）

```bash
dnf install -y redis
systemctl enable redis
systemctl start redis
redis-cli ping   # 期望：PONG
```

### 1.3 安装 Node.js 20（宝塔自带的 Node 管理器也可）

```bash
# 方案 A：用宝塔 Node 管理器（推荐，UI 一键）
#   宝塔面板 → 软件商店 → Node.js 版本管理器 → 装 v20.18.x → 设为默认

# 方案 B：命令行装 nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc
nvm install 20
nvm alias default 20
node -v   # 期望：v20.x.x
```

### 1.4 安装 pnpm

```bash
corepack enable
corepack prepare pnpm@10.19.0 --activate
pnpm -v   # 期望：10.19.0
```

### 1.5 安装 pm2

```bash
npm install -g pm2
pm2 -v
# 开机自启
pm2 startup systemd    # 会打印一条命令，复制粘贴跑
```

### 1.6 创建 deploy 用户（不要用 root 跑 web）

```bash
useradd -m -s /bin/bash deploy
# 给 deploy 写项目目录 + nginx reload 的权限
usermod -aG www deploy
mkdir -p /www/wwwroot/projects
chown -R deploy:www /www/wwwroot/projects
```

---

## 2. 创建 GitHub 仓库 + 配 SSH 部署密钥

### 2.1 创建 private repo

- 打开 https://github.com/new
- Repository name: `ff`
- Private ✅
- **不勾** Initialize with README（我们本地已有）
- Create repository

### 2.2 推送本地代码

```bash
# 在你本地（不是服务器）
cd /path/to/ff
git remote add origin git@github.com:cosmowind/ff.git
git push -u origin main
```

### 2.3 给服务器生成 deploy key

```bash
# 在服务器（以 deploy 用户）
sudo -u deploy -H bash
ssh-keygen -t ed25519 -C "ff-deploy@cosmowind" -N "" -f ~/.ssh/ff_deploy
cat ~/.ssh/ff_deploy.pub   # 复制这串公钥
```

把公钥加到 GitHub：
- https://github.com/cosmowind/ff/settings/keys/new
- Title: `ff-prod-server`
- Key: 粘贴上面那串
- ✅ Allow write access（CI 要 push tags / status 不用，但方便）

### 2.4 在服务器建 known_hosts

```bash
# 还在 deploy 用户
ssh-keyscan github.com >> ~/.ssh/known_hosts
chmod 600 ~/.ssh/known_hosts
```

测试：
```bash
ssh -i ~/.ssh/ff_deploy -T git@github.com
# 期望：Hi cosmowind/ff! You've been granted access.
```

---

## 3. 服务器首次部署（手动跑一次）

```bash
# 还在 deploy 用户
cd /www/wwwroot/projects
git clone git@github.com:cosmowind/ff.git
cd ff

# 复制 .env（手动填值，见 §4）
cp .env.example .env
nano .env   # 填 DATABASE_URL / REDIS_URL / 各种 KEY

# 装依赖
pnpm install --frozen-lockfile=false

# 跑 v2 migration（建 v2 表）
# 用 postgres 8.x 那台的用户密码
psql "$DATABASE_URL" -f packages/db-schema/src/migrations/v2_frameforge_v2_forms.sql
# 期望：CREATE TABLE / CREATE INDEX 全 ok

# 装 Redis 已跑过，pg 远端已 ok，build Next.js
pnpm --filter @ff/shared build
pnpm --filter @ff/web-uploader build
pnpm --filter @ff/web-admin build
pnpm --filter @ff/worker build
```

### 3.1 配 pm2 进程（`deploy/ecosystem.config.cjs`）

（deploy.sh 会自动建这个文件，参考 §6）

```javascript
// /www/wwwroot/projects/ff/deploy/ecosystem.config.cjs
module.exports = {
  apps: [
    {
      name: 'web-uploader',
      cwd: '/www/wwwroot/projects/ff/apps/web-uploader',
      script: 'node_modules/next/dist/bin/next',
      args: 'start -p 3001',
      env: { NODE_ENV: 'production' },
      max_memory_restart: '512M',
    },
    {
      name: 'web-admin',
      cwd: '/www/wwwroot/projects/ff/apps/web-admin',
      script: 'node_modules/next/dist/bin/next',
      args: 'start -p 3002',
      env: { NODE_ENV: 'production' },
      max_memory_restart: '512M',
    },
    {
      name: 'worker',
      cwd: '/www/wwwroot/projects/ff/apps/worker',
      script: 'dist/index.js',
      env: { NODE_ENV: 'production' },
      max_memory_restart: '512M',
    },
  ],
}
```

启动：
```bash
pm2 start deploy/ecosystem.config.cjs
pm2 save    # 保存当前进程表
pm2 list    # 看 3 个 process 都 online
```

### 3.2 防火墙 + 端口

```bash
# 宝塔面板 → 安全 → 放行端口 80 / 443 / 3001 / 3002 / 3010 / 6379
# 或命令行：
firewall-cmd --permanent --add-port=80/tcp
firewall-cmd --permanent --add-port=443/tcp
firewall-cmd --reload
```

---

## 4. .env 模板（生产值）

```bash
# === Node 环境 ===
NODE_ENV=production
WEB_UPLOADER_PORT=3001
WEB_ADMIN_PORT=3002
WORKER_PORT=3010

# === Postgres（你 8.x 主机，db: ff 已建，schema: ff 已有） ===
# 替换 8.x.x.x 为实际 IP；user/password 改真值
DATABASE_URL=postgresql://ff_user:REAL_PASSWORD@8.x.x.x:5432/ff?schema=ff
DATABASE_SCHEMA=ff

# === Redis（localhost）===
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_URL=redis://127.0.0.1:6379

# === 公网 URL（域名+ HTTPS）===
NEXT_PUBLIC_APP_URL=https://ff.your-domain.com
CLERK_JWT_KEY=
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_xxx
CLERK_SECRET_KEY=sk_live_xxx
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
CLERK_WEBHOOK_SECRET=whsec_xxx

# === 腾讯云 COS（暂未启用，phase 2 接）===
COS_SECRET_ID=
COS_SECRET_KEY=
COS_REGION=ap-shanghai
COS_BUCKET=

# === 设备 Adapter 路径 ===
FFMPEG_PATH=/usr/bin/ffmpeg
HMD_DECODER_PATH=
MCAP_EXTRACTOR_PATH=

# === BullMQ ===
BULLMQ_PREFIX=ff
WORKER_DEVICE_SCAN_CONCURRENCY=4
WORKER_PREVIEW_CONCURRENCY=2
WORKER_PULLER_CONCURRENCY=1
WORKER_BACKUP_CONCURRENCY=1
```

> ⚠ **敏感值**（DATABASE_URL / CLERK_SECRET_KEY / COS_SECRET_KEY）不入仓。.env 留在服务器本地。

---

## 5. Nginx 反代 + HTTPS（宝塔一键）

### 方案 A：用宝塔 UI（推荐，证书自动续期）

1. 宝塔面板 → 网站 → 添加站点
2. 域名：`ff.your-domain.com`
3. PHP 版本：**纯静态**
4. 创建后 → 设置 → 反向代理：
   - 添加代理：名称 `next-uploader`，目标 URL `http://127.0.0.1:3001`
   - 发送域名 `$host`
5. SSL → Let's Encrypt → 申请（自动续期）
6. 配置文件参考 `deploy/nginx-ff.conf`

### 方案 B：手写 nginx

参考 `deploy/nginx-ff.conf` 模板，含：
- 80 强制跳转 443
- 反代 3001 (uploader)
- 静态资源缓存
- gzip 压缩
- WebSocket 升级（step1 后期需要）
- 上传文件大小限制（plan2 ff 视频可能 1-10 GB）

---

## 6. CI/CD：GitHub Actions 自动部署

每次 push 到 main：
1. GitHub Actions 跑 typecheck + build（保证 build 必过）
2. SSH 到服务器 → 拉新代码 → 装依赖 → 重启 pm2
3. 失败 → 邮件通知

### 6.1 创建 GitHub Secrets

打开 https://github.com/cosmowind/ff/settings/secrets/actions/new，加 4 个：

| Secret 名 | 值 |
|---|---|
| `VPS_HOST` | `vps.example.com` |
| `VPS_USER` | `deploy` |
| `VPS_SSH_KEY` | 服务器 `~/.ssh/ff_deploy` 私钥全文（含 `-----BEGIN OPENSSH PRIVATE KEY-----`）|
| `VPS_PORT` | `22` |
| `DEPLOY_PATH` | `/www/wwwroot/projects/ff` |

### 6.2 workflow 文件

`.github/workflows/deploy.yml`（已提交到仓库）：
- 触发：push to main + manual dispatch
- 步骤：typecheck → build (web-uploader + web-admin + worker) → SSH 拉代码 + pm2 reload
- 失败通知

### 6.3 服务器端 deploy.sh

`deploy/deploy.sh`（已提交到仓库）：
- 接收 `$DEPLOY_PATH` 环境变量
- `git fetch + reset --hard origin/main`
- `pnpm install --frozen-lockfile=false`（锁文件未变就 skip）
- `pnpm --filter @ff/* build`（增量 build）
- `pm2 reload ecosystem.config.cjs`（零停机）
- 输出健康检查 curl

---

## 7. 日常 dev 流

```bash
# 本地改代码
git add .
git commit -m "feat: ..."
git push origin main
# → GitHub Actions 自动 build
# → 自动 SSH 部署到 vps.example.com
# → 30-60 秒后 ff.your-domain.com 上生效
```

回滚（生产事故时）：
```bash
ssh deploy@vps.example.com
cd /www/wwwroot/projects/ff
git log --oneline -10   # 找上一个 good commit
pm2 stop all
git checkout <good-commit-sha>
pnpm install
pnpm build
pm2 start deploy/ecosystem.config.cjs
```

---

## 8. 监控 / 日志 / 备份

### 8.1 监控

```bash
pm2 monit              # 实时 CPU / 内存 / 事件循环
pm2 logs --lines 200   # 最近 200 行日志
pm2 logs web-uploader  # 单进程
```

### 8.2 健康检查

- web-uploader: `curl http://127.0.0.1:3001/api/health` → 200
- web-admin:    `curl http://127.0.0.1:3002/api/health` → 200
- worker:       pm2 status
- redis:        `redis-cli ping` → PONG
- pg:           `psql "$DATABASE_URL" -c 'SELECT 1'`

宝塔可装「宝塔跑分」/ 「站点监控」插件做 7×24 监控 + 告警。

### 8.3 数据库备份（plan2 D8 pg_dump daily）

服务器 cron：
```bash
crontab -e
# 每天 03:00 dump
0 3 * * * /usr/bin/pg_dump "$DATABASE_URL" | gzip > /www/backup/ff-$(date +\%Y\%m\%d).sql.gz
# 保留 30 天
0 4 * * * find /www/backup -name "ff-*.sql.gz" -mtime +30 -delete
```

### 8.4 Redis 持久化

`/etc/redis.conf`：
```
appendonly yes
appendfsync everysec
```
重启 `systemctl restart redis`。

---

## 9. 故障排查

| 现象 | 排查 |
|---|---|
| 502 Bad Gateway | `pm2 list` 看 web-uploader online？`pm2 logs web-uploader` 看 stack |
| 静态资源 404 | `pnpm --filter @ff/web-uploader build` 重跑（build 没产出 .next/standalone）|
| DB 连接拒绝 | `psql "$DATABASE_URL" -c 'SELECT 1'`；8.x 主机 PG 监听地址？firewall？ |
| 视频上传慢 | 检查 `client_max_body_size`（nginx 100M 默认，太小）|
| GitHub Actions 失败 | 看 .github/workflows 日志；SSH key 错？known_hosts 没 github.com？ |

---

## 10. 后续 phase

- **phase 1.1**：COS 真接（client 直传 STS 凭证）
- **phase 1.2**：4 设备 Adapter 真 worker 实现（ffmpeg / hmd-decoder / mcap-extract）
- **phase 2**：图床（ff_scenes.environment_photo_url）+ Clerk 接入
- **phase 3**：蓝绿发布（2 台服务器 + LB）
- **phase 4**：K8s（如果 4 设备适配 + 多区域上传场景成立）

---

**关联文档**：
- [docs/DEPLOY-CHECKLIST.md](DEPLOY-CHECKLIST.md) — 用户逐步执行清单
- [docs/v2-forms-spec.md](v2-forms-spec.md) — v2 表单事实层
- [wcs-manifest.yaml](../wcs-manifest.yaml) — docs 中央索引
- [package.json scripts](../package.json) — `pnpm dev / build / start / typecheck`
