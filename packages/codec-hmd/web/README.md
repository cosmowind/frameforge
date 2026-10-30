# web/  —  mcap2mp4 本地 web 服务

一个跑在本机（或局域网）的 FastAPI 服务，复用 `mcap2mp4_app.py` 里的
`parse / compute_new_name / process_session / run`（仅作为模块 import，不修改源文件）。

## 设计要点

- **不在浏览器里上传几个 GB 的 mcap**。用户在网页里填一个**服务器端能访问的文件夹路径**（就像 exe 的命令行参数那样），后端就地扫描 + 重命名 + 转码。
- 转码后台线程跑，前端通过 `/api/status` 轮询显示进度（每个 session 完成 / 失败时实时更新）。
- 输出目录里现成的 mp4 提供下载（`/api/files/{name}`）和 HTML5 预览（`/api/preview/{name}`，FastAPI 的 `FileResponse` 已支持 HTTP Range，可流式 seek）。HEVC 在浏览器里大概率放不了，下载到本地用 VLC / PotPlayer / ffmpeg 播放即可。

## 启动

```bash
# 进入仓库根目录
cd ./workspace

# 直接跑（默认端口 8756）
python web/server.py

# 或显式指定端口
set PORT=8765
python web/server.py

# 也可以 uvicorn 起
uvicorn web.server:app --host 127.0.0.1 --port 8756
```

打开 <http://127.0.0.1:8756/> 即可。

> 依赖：`fastapi`、`uvicorn`、`av`、`mcap`（都已装）。若没装：`pip install fastapi uvicorn av mcap`。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET  | `/`                       | 单页前端 |
| GET  | `/api/health`             | 健康检查 `{ok, version}` |
| POST | `/api/convert`            | 启动转换。body `{input_dir, output_dir?}` |
| GET  | `/api/status`             | 轮询任务进度 + 最近日志 + 输出目录里的 mp4 |
| GET  | `/api/outputs?dir=...`    | 列某目录里的 mp4 |
| GET  | `/api/files/{name}`       | 下载 mp4（`Content-Disposition: attachment`） |
| GET  | `/api/preview/{name}`     | 预览 mp4（`Content-Disposition: inline`，Range 支持） |
| POST | `/api/reset`              | 清空任务状态（任务进行中时返回 409） |

## 已知限制

- **HEVC 在浏览器 `<video>` 里预览不了** —— 这是浏览器侧解码限制，不是服务问题。HEVC 在 Chrome / Firefox 上默认不支持（即使支持也通常需要硬件解码器），Safari 在 Apple 平台可以。**下载后用 VLC / PotPlayer / ffmpeg 看完全没问题**（输出就是标准 H.265 + MP4 容器）。
- 单任务模型：同一时刻只跑一个 job，避免并发把磁盘 / IO 打满。再次启动会返回 409；要么等它结束，要么先 `/api/reset`。
- 没有断点续传：转换被打断后已完成的 session 不会被自动跳过（再次启动会重做）。可手动从 `/api/outputs` 看哪些 mp4 已经存在并提前移走。