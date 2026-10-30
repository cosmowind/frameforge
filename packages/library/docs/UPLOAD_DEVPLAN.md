# Video Sort 项目 - 上传功能文档

> 更新时间: 2026-06-24

## 概述

`auto_upload.py` 是 FrameForge 视频上传的核心脚本，位于 `src/auto_upload.py`。通过 Playwright 模拟浏览器操作，自动填写 21 个表单字段并上传 HMD 会话视频。

---

## 快速开始

### 单视频上传

```bash
# 从项目根目录运行
cd ./vendor
python src/auto_upload.py --row-index 3
```

### 上传并自动清理本地文件

```bash
python src/auto_upload.py --row-index 3 --delete-local
```

### 批量上传（循环调用）

```python
import subprocess
import sys

indices = [3, 4, 5]  # 要上传的视频索引
for idx in indices:
    result = subprocess.run(
        [sys.executable, "src/auto_upload.py", "--row-index", str(idx), "--delete-local"],
        cwd="./vendor"
    )
    if result.returncode != 0:
        print(f"Index {idx} 上传失败，停止批量上传")
        break
```

---

## 命令行参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--row-index <n>` | CSV 中的行索引（从0开始） | `--row-index 3` |
| `--video <path>` | 直接指定视频文件路径（需配合 --data） | `--video "/media/test.mp4"` |
| `--data <json>` | JSON 格式的上传模板数据 | `--data '{"operator_name":"op4",...}'` |
| `--dump-form` | 抓取页面表单元素到 diagnose_form.json | `--dump-form` |
| `--no-submit` | 只填写表单不提交，保持浏览器打开供检查 | `--no-submit` |
| `--delete-local` | 上传成功后删除本地文件（HMD分片、预览视频、封面图、预览帧） | `--delete-local` |

---

## --delete-local 清理范围

上传成功后自动删除以下文件以释放本地存储空间：

| 类型 | 路径 | 说明 |
|------|------|------|
| HMD 分片 | `/media\0619\hmd\9df5dc_session_00001\*.hmd` | 原始录制分片文件 |
| 元数据 | `/media\0619\hmd\9df5dc_session_00001\metadata.json` | HMD session 元数据 |
| 预览视频 | `runtime\hmd_cache\<date>\<session>\left.mp4` | 预处理生成的 mp4 文件 |
| 预览视频 | `runtime\hmd_cache\<date>\<session>\right.mp4` | 预处理生成的 mp4 文件 |
| H265 原始 | `runtime\hmd_cache\<date>\<session>\left.h265` | 未编码的原始流 |
| 预览帧 | `runtime\hmd_cache\<date>\<session>\frames\*.jpg` | 帧提取生成的图片 |
| 缩略图 | `runtime\thumbnails\<session>_*.jpg` | 视频封面图 |

**注意**：缩略图和预览帧删除后，前端页面将无法显示该视频的预览，但不影响已上传到 FrameForge 的视频。

---

## CSV 数据文件

视频信息存储在 `runtime/data/video_manager.csv`，列说明：

| 列名 | 说明 |
|------|------|
| `path` | HMD session 目录路径 |
| `uploaded` | `Yes`=已上传，`No`=未上传 |
| `recorder_id` | 录入员ID，对应 `recorders.csv` |
| `task_id` | 任务ID，对应 `tasks.csv` |
| `device_id` | 设备ID，对应 `sd_cards.csv` |
| `file_type` | `hmd` 或 `data` |
| `extra_description` | HMD session 描述（如分片数量、大小） |

---

## 二次开发指南

### 1. 添加新的上传字段

编辑 `src/auto_upload.py` 中的 `FIELD_SELECTORS` 字典：

```python
FIELD_SELECTORS: dict[str, list[str]] = {
    # 添加新字段
    "new_field_name": [
        "input[placeholder*='New field placeholder']",
        "label:has-text('new field') input",
        "[data-field='new_field']",
    ],
}
```

然后在 `FILL_ORDER` 列表中添加字段key。

### 2. 修改上传完成检测

上传完成检测逻辑在 `_wait_for_completion()` 方法中（行 ~1508），通过检测 "In flight" 区块消失和 "Recent uploads" 列表来确认上传成功。

### 3. 集成到 Flask API

参考 `app.py` 中的 `/api/auto-upload-start` 接口：

```python
@app.route("/api/auto-upload-start", methods=["POST"])
def auto_upload_start():
    body = request.get_json()
    row_index = body.get("row_index")
    # 启动 subprocess 运行 auto_upload.py
    proc = subprocess.Popen([
        sys.executable, "src/auto_upload.py",
        "--row-index", str(row_index)
    ], cwd=BASE_DIR, ...)
```

---

## 数据目录结构

```
video-sort-package/
├── src/
│   ├── auto_upload.py       # 上传核心脚本
│   ├── config.py            # 路径配置（从 RUNTIME_DIR 读取）
│   └── ...
├── runtime/
│   ├── data/
│   │   ├── video_manager.csv    # 视频列表
│   │   ├── recorders.csv       # 录入员信息
│   │   ├── tasks.csv           # 任务信息
│   │   ├── sd_cards.csv        # SD卡信息
│   │   └── config.json         # 上传配置
│   ├── hmd_cache/             # 预处理缓存
│   │   └── <date>/
│   │       └── <session_name>/
│   │           ├── left.mp4
│   │           ├── right.mp4
│   │           └── frames/
│   ├── thumbnails/            # 缩略图
│   └── logs/                 # 上传日志
└── browser_data/             # Playwright Chrome 数据
```

---

## 故障排查

### 1. "行索引超出范围"

确保 `video_manager.csv` 路径正确，脚本从 `RUNTIME_DIR/data/video_manager.csv` 读取。

### 2. 上传页面检测失败

使用 `--dump-form` 参数运行，生成 `diagnose_form.json` 分析页面元素结构。

### 3. 登录状态丢失

`auto_upload.py` 会自动检测登录状态，如果掉线会等待用户手动登录。