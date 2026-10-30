# mcap2mp4-web 部署说明

一个 FastAPI + 原生 JS 前端的「浏览器上传 → 云端转码 → 下载 mp4」服务。复用
`mcap2mp4_app.py` 的 `parse / compute_new_name / process_session`。

服务端自带 `Dockerfile` + `deploy/mcap2mp4.service`（systemd）+ `deploy/nginx.conf.example`。

---

## 包结构

```
mcap2mp4-web/
├── server.py            # FastAPI 后端（上传 / 转换 / 状态 / 下载 / 删除）
├── mcap2mp4_app.py      # 同目录下原样复制，未做改动（仅 import 复用）
├── static/
│   └── index.html       # 单页前端：webkitdirectory + XHR + 轮询
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── deploy/
│   ├── mcap2mp4.service # systemd unit
│   └── nginx.conf.example
└── DEPLOY.md
```

---

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET  | `/`                                        | 单页前端 |
| GET  | `/api/health`                              | 健康检查 |
| POST | `/api/jobs`                                | 建新 job，返回 `{id, root, max_upload_mb}` |
| GET  | `/api/jobs`                                | 列出所有 job（精简） |
| POST | `/api/jobs/{id}/upload`                    | multipart 上传单个文件；表单字段 `relpath` + `file`；**流式写盘，不一次进内存** |
| POST | `/api/jobs/{id}/convert`                   | 后台线程启动转码 |
| GET  | `/api/jobs/{id}/status`                    | 进度 / 日志 / 已生成 mp4 列表 |
| GET  | `/api/jobs/{id}/files/{name}`              | 下载 mp4（`video/mp4`，`Accept-Ranges: bytes`，attachment） |
| DELETE | `/api/jobs/{id}`                          | 清理一个 job（uploads + out + 内存条目） |

环境变量：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `HOST`              | `0.0.0.0`        | 监听地址 |
| `PORT`              | `8756`           | 监听端口 |
| `MCAP_DATA_ROOT`    | `/tmp/mcap2mp4_jobs` | job 工作目录根；Docker 镜像里是 `/data/mcap2mp4_jobs` |
| `JOB_TTL_HOURS`     | `48`             | 完成后 TTL（小时），到时被清理 |
| `JOB_MAX_KEEP`      | `50`             | 最多保留多少个 job（超出最旧的会清） |
| `MAX_UPLOAD_MB`     | `8192`           | 单文件大小上限 MB；nginx 上限须 ≥ 此值 |

---

## 方案 A：Docker（推荐）

```bash
cd mcap2mp4-web

# 构建（av 自带 ffmpeg，无需 apt 装）
docker build -t mcap2mp4-web:latest .

# 起容器；外部走 nginx，建议只暴露给 nginx
docker run -d \
  --name mcap2mp4-web \
  --restart unless-stopped \
  -p 127.0.0.1:8756:8756 \
  -v /opt/mcap2mp4-data:/data/mcap2mp4_jobs \
  -e MAX_UPLOAD_MB=8192 \
  mcap2mp4-web:latest

# 验证
curl http://127.0.0.1:8756/api/health
```

可选编排（`docker-compose.yml`，不放进包）：

```yaml
version: "3.8"
services:
  web:
    build: .
    restart: unless-stopped
    volumes:
      - ./jobs-data:/data/mcap2mp4_jobs
    environment:
      MAX_UPLOAD_MB: 8192
      JOB_TTL_HOURS: 72
  nginx:
    image: nginx:1.27-alpine
    ports: ["80:80"]
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/mcap2mp4.conf:ro
    depends_on: [web]
```

---

## 方案 B：systemd（裸 Python）

适合不想用 Docker 的 Linux 服务器。

```bash
# 1) 准备用户和目录
sudo useradd -r -s /usr/sbin/nologin mcap || true
sudo install -d -o mcap -g mcap /opt/mcap2mp4-web /var/lib/mcap2mp4/jobs

# 2) 拷贝包
sudo cp -r . /opt/mcap2mp4-web/
sudo chown -R mcap:mcap /opt/mcap2mp4-web

# 3) 装依赖（av 自带 ffmpeg，无需 apt 装 ffmpeg）
cd /opt/mcap2mp4-web
sudo -u mcap python3 -m venv .venv
sudo -u mcap .venv/bin/pip install -U pip
sudo -u mcap .venv/bin/pip install -r requirements.txt

# 4) 安装 systemd unit
sudo cp deploy/mcap2mp4.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mcap2mp4
sudo systemctl status mcap2mp4

# 5) nginx 反代（可选；改 deploy/nginx.conf.example 为你的域名）
sudo cp deploy/nginx.conf.example /etc/nginx/conf.d/mcap2mp4.conf
sudo nginx -t && sudo systemctl reload nginx
```

> 调整 `Environment=` 行覆盖 `PORT / MCAP_DATA_ROOT / MAX_UPLOAD_MB` 后需要 `systemctl restart mcap2mp4`。

---

## 关键注意事项

### 1. 大文件上传

- 单个 mcap 可能 2 GB+。
- nginx 必须：
  - `client_max_body_size 20g;`（或更大）
  - `proxy_request_buffering off;` `proxy_buffering off;`（**不要**让 nginx 把上传落临时盘，否则 8GB 缓存能轻松把磁盘写爆）
  - `proxy_send_timeout` / `proxy_read_timeout` / `client_body_timeout` 调到 `3600s` 或更高
- 后端 `MAX_UPLOAD_MB`（默认 8GB）。如果想完全不限，set `0`（不推荐）或者改代码 `> max_bytes` 那行。
- 前端用 XMLHttpRequest（不是 fetch stream），兼容 Win7 上的 Chrome / Firefox ESR。

### 2. HEVC 在浏览器里预览不了

- 服务端输出是 **标准 H.265/HEVC + MP4 容器**（mp4box / VLC / PotPlayer / ffmpeg 都能直接放）。
- **Chrome / Edge / Firefox 浏览器原生对 HEVC 支持很差**（Safari 仅在 macOS / iPad 能放）。前端用 `<video>` 预览常常失败。
- 服务只保证 **下载到本地用播放器看是通的**。前端在第 4 块已经用黄色提示明确说明。

### 3. 浏览器兼容性（Win7 老浏览器）

页面里**只用**了以下 API，全部在 Win7 上的 Chrome 109 / Firefox ESR 里有：

- `XMLHttpRequest`（含 `upload.onprogress`）—— Win7 Chrome 49+ / Firefox ≥ 3.5 都有
- `FormData`、`<input type=file webkitdirectory>` —— Chrome 30+；Firefox 要 `dom.webkit.dir.enabled` (约 Firefox 42 ESR+)，未开启时退化为「选单个文件」
- 不使用 fetch stream、AbortSignal、WebSocket、ES Modules、Tailwind 之类

如果 Win7 上 firefox 没启用 `dom.webkit.dir.enabled`，会弹不出文件夹选择（只是降级，不影响换 Chrome）。

### 4. 安全建议

- 公网不要直接暴露 `8756`，**一定走 nginx** 并按需加 basic auth / 客户端证书 / IP 白名单
- 不要把容器端口 8756 映射到 `0.0.0.0`
- 单 job 单 session；多用户同时上传不同 session 是安全的（每个 job 一个 uuid 子目录，路径穿越已防）
- MAX_UPLOAD_MB 是单文件硬上限，超出直接 413；如业务更大改此值 + nginx 的 `client_max_body_size`
- 想更严格：在 FastAPI 加 `app.add_middleware(HTTPSRedirectMiddleware)` + 注册 `TrustedHostMiddleware`

### 5. 存储与清理

- `JOB_TTL_HOURS`（默认 48h）：完成后超过这么久会被清理（包括磁盘目录和内存记录）
- `JOB_MAX_KEEP`（默认 50）：同时存在的 job 超过该值，最旧的会被清理
- 强制清理可以随时 `curl -X DELETE http://127.0.0.1:8756/api/jobs/{id}`
- 当前实现是 in-memory 索引；**重启服务会让运行中任务丢失**（磁盘文件还在，但前端看不到）。要做 HA 请把 job 状态放到 SQLite / Redis（已在 TODO 列表里）

---

## 本机自检

```bash
python3 server.py          # 默认 0.0.0.0:8756
curl http://127.0.0.1:8756/api/health

# 建 job
JOB=$(curl -s -X POST http://127.0.0.1:8756/api/jobs | python -c "import json,sys;print(json.load(sys.stdin)['id'])")
echo "job=$JOB"

# 上传（form 字段：relpath + file）
curl -X POST http://127.0.0.1:8756/api/jobs/$JOB/upload \
  -F "relpath=sample_session_00000/session.json" \
  -F "file=@sample_session_00000/session.json"
curl -X POST http://127.0.0.1:8756/api/jobs/$JOB/upload \
  -F "relpath=sample_session_00000/ego_0000.mcap" \
  -F "file=@sample_session_00000/ego_0000.mcap"

# 转码
curl -X POST http://127.0.0.1:8756/api/jobs/$JOB/convert

# 轮询状态
for i in $(seq 1 60); do
  STATE=$(curl -s http://127.0.0.1:8756/api/jobs/$JOB/status | python -c "import json,sys;print(json.load(sys.stdin)['state'])")
  echo "$i: $STATE"
  [ "$STATE" = "done" ] && break
  sleep 2
done

# 下载
curl -OJ http://127.0.0.1:8756/api/jobs/$JOB/files/0104-4d94ca-session-00000.mp4

# 验
python -c "import av; f=av.open('0104-4d94ca-session-00000.mp4'); v=f.streams.video[0]; print(v.codec_context.name, v.codec_context.width,'x',v.codec_context.height,'frames=',v.frames)"
```