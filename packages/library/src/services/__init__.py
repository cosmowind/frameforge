"""服务层模块 — 从 app.py 拆分出来的纯业务逻辑。

services/lazy_loader.py  - 工具模块的惰性导入（避免启动循环导入）
services/video.py        - 缩略图、视频帧、HMD 抽帧等媒体处理
services/scan.py         - 目录扫描、预处理状态管理
services/upload.py       - 上传服务（SSE / batch / template）
services/hmd.py          - HMD 文件流、预处理触发、注册
"""
