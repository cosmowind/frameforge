# FrameForge 部署执行清单（v1.0 · 2026-07-15）

> **目标**：把 dev 改完的代码，自动部署到 `https://ff.your-domain.com`，另一台手机可访问。
> **预计耗时**：第一次 1-2 小时（含 DNS 解析等待），后续 push → 部署 1-2 分钟。
> **配套文档**：[docs/deploy-production.md](deploy-production.md) — 全套原理 + 故障排查

---

## 📋 准备清单（开始前先备齐）

- [ ] 服务器 SSH 密码或密钥（root@vps.example.com）
- [ ] 域名（你的已有域名，准备一个子域名如 `ff.your-domain.com`）
- [ ] DNS 服务商账号（DNSPod / Cloudflare / 阿里云 DNS，看域名在哪买的）
- [ ] GitHub 账号
- [ ] 8.x 主机 PG 的用户名密码（要允许 vps.example.com 远程连）

---

## 🚀 步骤 1：服务器前置（首次 30 分钟）

### 1.1 SSH 登录
```bash
ssh root@vps.example.com
```

### 1.2 装 Redis
```bash
dnf install -y redis
systemctl enable redis
systemctl start redis
redis-cli ping    # 期望 PONG
```

### 1.3 装 Node 20
宝塔面板 → 软件商店 → Node.js 版本管理器 → 装 v20.18.x → 设为默认。
或命令行：
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc
nvm install 20
nvm alias default 20
node -v    # v20.x.x
```

### 1.4 装 pnpm + pm2
```bash
corepack enable
corepack prepare pnpm@10.19.0 --activate
npm install -g pm2
pm2 startup systemd    # 复制粘贴打印的命令
```

### 1.5 创建 deploy 用户
```bash
useradd -m -s /bin/bash deploy
usermod -aG www deploy
mkdir -p /www/wwwroot/projects
chown -R deploy:www /www/wwwroot/projects
```

### 1.6 防火墙放行
```bash
firewall-cmd --permanent --add-port=80/tcp
firewall-cmd --permanent --add-port=443/tcp
firewall-cmd --reload
```
或宝塔面板 → 安全 → 80/443。

---

## 🚀 步骤 2：DNS 解析（10 分钟 + 等待生效）

在你的 DNS 服务商（DNSPod/Cloudflare）：

| 主机记录 | 记录类型 | 记录值 | TTL |
|---|---|---|---|
| `ff` | A | `vps.example.com` | 600 |
| `ff-admin` | A | `vps.example.com` | 600 |

DNS 全球生效：5-30 分钟。检查：
```bash
nslookup ff.your-domain.com
# 期望返回 vps.example.com
```

---

## 🚀 步骤 3：HTTPS 证书（Let's Encrypt · 5 分钟）

宝塔面板 → 网站 → 添加站点：
- 域名：`ff.your-domain.com`
- PHP 版本：纯静态
- 创建后 → SSL → Let's Encrypt → 申请（自动 90 天续期）

或在服务器命令行：
```bash
certbot certonly --nginx -d ff.your-domain.com -d ff-admin.your-domain.com
```

---

## 🚀 步骤 4：8.x 主机 PG 允许远程连

在 8.x 主机上：
```bash
# 编辑 postgresql.conf
listen_addresses = 'localhost,8.x.x.x'   # 或 '*'（不推荐）

# 编辑 pg_hba.conf，加一行：
host    ff    ff_user    vps.example.com/32    scram-sha-256

# 重启
systemctl restart postgresql
```

测试从 vps.example.com 连：
```bash
psql "postgresql://ff_user:密码@8.x.x.x:5432/ff?schema=ff" -c 'SELECT 1'
# 期望返回 1
```

---

## 🚀 步骤 5：本地推代码到 GitHub（10 分钟）

```bash
# 在你本地（不是服务器）
cd /path/to/ff   # 项目根目录

# 添加 remote
git remote add origin git@github.com:cosmowind/ff.git

# 推 main
git push -u origin main

# 期望：GitHub 上能看到 cosmowind/ff 仓库，private
```

---

## 🚀 步骤 6：服务器配 deploy key（5 分钟）

```bash
# SSH 到服务器，切 deploy 用户
ssh root@vps.example.com
sudo -u deploy -H bash

# 生成 key
ssh-keygen -t ed25519 -C "ff-deploy" -N "" -f ~/.ssh/ff_deploy
cat ~/.ssh/ff_deploy.pub
```

复制公钥 → 打开 https://github.com/cosmowind/ff/settings/keys/new
- Title: `ff-prod-server`
- Key: 粘贴
- ✅ Allow write access
- Add key

```bash
# 还在 deploy 用户
ssh-keyscan github.com >> ~/.ssh/known_hosts
chmod 600 ~/.ssh/known_hosts
ssh -i ~/.ssh/ff_deploy -T git@github.com
# 期望：Hi cosmowind/ff! You've been granted access.
```

---

## 🚀 步骤 7：服务器首次部署（手动跑 15 分钟）

```bash
# 还在 deploy 用户
cd /www/wwwroot/projects
git clone git@github.com:cosmowind/ff.git
cd ff

# 复制 .env
cp .env.production.example .env
nano .env   # 填 DATABASE_URL / REDIS_URL / 域名 / Clerk（如已申请）

# 装依赖
pnpm install --frozen-lockfile=false

# 跑 v2 migration（5 张表）
psql "$DATABASE_URL" -f packages/db-schema/src/migrations/v2_frameforge_v2_forms.sql
# 期望：CREATE TABLE 全 ok（如已跑过会 NOTICEs，无害）

# Build
pnpm --filter @ff/shared build
pnpm --filter @ff/web-uploader build
pnpm --filter @ff/web-admin build
pnpm --filter @ff/worker build

# 创建日志目录
mkdir -p logs

# pm2 启动
pm2 start deploy/ecosystem.config.cjs
pm2 save
pm2 list
# 期望：3 个 process 都 online

# 健康检查
curl http://127.0.0.1:3001/api/health    # 200
curl http://127.0.0.1:3002/api/health    # 200
```

---

## 🚀 步骤 8：Nginx 反代（5 分钟）

宝塔面板 → 网站 → ff.your-domain.com → 设置 → 反向代理：
- 名称：`next-uploader`
- 目标 URL：`http://127.0.0.1:3001`
- 发送域名：`$host`

或把 `deploy/nginx-ff.conf` 整段贴到「配置文件」。

---

## 🚀 步骤 9：GitHub Actions Secrets（5 分钟）

打开 https://github.com/cosmowind/ff/settings/secrets/actions/new

逐个加：

| Secret | 值（示例）|
|---|---|
| `VPS_HOST` | `vps.example.com` |
| `VPS_USER` | `deploy` |
| `VPS_PORT` | `22` |
| `VPS_SSH_KEY` | 服务器 `cat ~/.ssh/ff_deploy` 私钥全文 |
| `DEPLOY_PATH` | `/www/wwwroot/projects/ff` |

---

## 🚀 步骤 10：触发第一次自动部署

```bash
# 本地
cd /path/to/ff
# 改个文件，比如 README
echo "" >> README.md
git add README.md
git commit -m "test: 第一次自动部署"
git push origin main
```

打开 https://github.com/cosmowind/ff/actions
- 应该看到「deploy-production」在跑
- 2 步：build → deploy
- 期望 1-2 分钟内全绿

服务器验证：
```bash
ssh deploy@vps.example.com
pm2 list    # 看 3 个 process uptime
pm2 logs web-uploader --lines 50
```

---

## ✅ 步骤 11：手机跨设备测试

1. **手机浏览器**（不是电脑）打开 `https://ff.your-domain.com`
2. 期望看到 FrameForge Uploader 首页
3. 点 **Step 1 · 选设备 + 扫描**
4. 4 设备卡显示
5. 点「📂 选择文件夹」→ 弹手机系统文件夹选择器
6. 选一个含 DCIM/ 或 hmd/ 或 data/ 或 recordings/ 的目录
7. 看到候选列表
8. 勾选 → 下一步

如果 403 / 502 / 证书错误：查 [docs/deploy-production.md §9](deploy-production.md#9-故障排查)

---

## 🎉 完成！

之后 dev 流：
```bash
# 本地
git commit -m "..."
git push origin main
# → 1-2 分钟后 https://ff.your-domain.com 自动生效
```

---

## ❓ 遇到问题

| 卡哪 | 怎么办 |
|---|---|
| SSH 连不上 | 宝塔安全 → 22 端口放行 / 防火墙规则 |
| DNS 不生效 | 等 30 分钟；`nslookup` 检查；不同 DNS 缓存不同 |
| 证书申请失败 | 确认 80 端口可达 + 域名解析正确 + 没被 CDN 拦截 |
| `git clone` Permission denied | deploy key 没加对 / `known_hosts` 没 github.com |
| `pnpm install` 失败 | 检查 Node 版本 v20+；corepack 是否启用 |
| `psql` 连不上 8.x 主机 | 8.x 主机 `pg_hba.conf` 没加 vps.example.com；端口 5432 防火墙 |
| build 失败 | 查 GitHub Actions 日志；本机先 `pnpm typecheck && pnpm build` |
| pm2 起不来 | `pm2 logs` 看错；常见 .env 缺值 / 端口占用 |
| 跨手机访问 502 | 查 `pm2 list`（3 个 online？）；nginx `proxy_pass` 对吗 |
| 上传视频大文件被截 | nginx `client_max_body_size` 调到 10G；reload |

---

## 📋 回滚

服务器事故回滚：
```bash
ssh deploy@vps.example.com
cd /www/wwwroot/projects/ff
pm2 stop all
git log --oneline -10   # 找上一个 good
git checkout <good-sha>
pnpm install
pnpm --filter @ff/* build
pm2 start deploy/ecosystem.config.cjs
```

DB 回滚：v2 migration 全部 IF NOT EXISTS，没法回滚；只能手 SQL 删（**慎用**）。
