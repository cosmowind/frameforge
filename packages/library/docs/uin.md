# UIN — AI 协作提示与约束

> AI 接手本项目时的注意事项。按优先级排列。

---

## 硬性约束

1. **不破坏现有功能** — 任何改动前确认理解原逻辑，改动后验证功能不变
2. **数据安全** — runtime/data/ 下的 CSV 和 config.json 是用户数据，不可丢失
3. **单文件上限** — 新代码不超过 500 行理想，1000 行硬上限；超大文件优先拆分
4. **文档同步** — 改了代码必须同步更新对应文档

## 项目特殊性

### 视频格式
- **MP4**：标准格式，FFprobe 提取时长
- **HMD**：自研立体视频格式，HEVC 编码，需要 WebCodecs 解码
- HMD 预处理流程：`.hmd` → `splitStereo` → `left.h265` → `ffmpeg` → `left.mp4` + 帧 + 封面
- 预处理完成后自动删除 `.h265` 节省空间（~50%），`check_fast_done()` 接受此状态

### 数据存储
- **PostgreSQL 云数据库**：主存储（2026-06-30 全面上线）
- **CSV 本地备份**：`runtime/data/video_manager.csv`，正常流程不再读写
- **内存缓存**：`models/cache.py`，视频列表 30s TTL、维表 60s TTL，写操作自动失效
- 写入方式：UPSERT（以 path 为唯一键），非 TRUNCATE + INSERT

### 设备监控
- Windows 平台，`GetLogicalDrives` 扫描可移动设备
- 支持 DJI（DCIM）、GoPro（MP_ROOT）、索尼（PRIVATE）目录结构
- HMD session 复制后自动添加设备 ID 前缀 + MMDD 日期前缀

### 上传器
- **主力**：`src/auto_upload.py`（Playwright 自动化，3895 行）
- **备用**：`src/vendor-upload-pkg/`（供应商版，当前未启用）
- 上传后支持 `--delete-local` 释放空间

## 常用命令

```bash
# 启动
python src/run.py
# 或双击 启动视频管理.bat

# 测试
python src/scripts/verify_pages.py    # 38 个端到端 case
python src/scripts/test_flask_routes.py  # 路由冒烟测试

# 打包
打包备份.bat  # 或 pack.ps1
```

## 文件分类约定

| 目录 | 用途 | 维护方式 |
|------|------|---------|
| `src/` | 核心源码 | 改动需验证 + 文档同步 |
| `src/scripts/` | 离线运维脚本 | 可独立运行，不影响主服务 |
| `src/tools/` | 外部工具/数据提取 | 调试和逆向工程用 |
| `src/vendor-upload-pkg/` | 供应商版上传包 | 备用方案，当前未启用 |
| `scripts/` | 项目级辅助脚本 | pg_backup、generate_task_list 等 |
| `scripts/temp/` | 临时测试脚本 | 调试用，可归档 |
| `runtime/` | 运行时数据 | git ignored，不可删除 |
| `docs/done/` | 历史文档归档 | 已完成的任务文档 |

## 路由架构说明

- `app.py` 创建 Flask 应用并注册 6 个蓝图（misc/data/dim/video/hmd/upload）
- 蓝图路由在 `src/routes/` 下定义，通过 `register_blueprint` 注册
- **注意**：`app.py` 中仍保留部分路由装饰器（历史遗留），与蓝图路由存在重复定义
- 实际运行时蓝图路由优先（先注册先匹配）

## Git 提交规范

```
feat: 新功能
fix: 修复
refactor: 重构（不改变行为）
docs: 文档更新
perf: 性能优化
chore: 杂项（配置、脚本等）
```
