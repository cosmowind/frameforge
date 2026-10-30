# 代码优化建议清单（提高可理解性 + 精简度）

> 范围：项目根目录下 6 个 Python 主文件 + 1 个前端 HTML。
> 评级：🔴 高优先级（影响可维护性）/ 🟡 中（可读性）/ 🟢 低（风格）。
> 所有建议都**不改变行为**，可分批合入。

---

## 📊 总体规模速览

| 文件 | 行数 | 主要问题 |
|------|------|---------|
| `app.py` | 1285 | 单文件超长、4 个 200+ 行函数、4 个全局可变状态、零类设计 |
| `device_monitor.py` | 696 | `DeviceMonitor.register_to_csv` 136 行（God Method） |
| `rotate_video.py` | 336 | 类过大、ffmpeg 调用内联 |
| `split_video.py` | 186 | 已较合理，但可抽公共 ffmpeg 工具 |
| `_upload_now.py` | 316 | 重复出现 CSV 读写工具（与 app.py 重叠） |
| `copy_progress_window.py` | 282 | Tk 线程样板可抽出 |
| `templates/index.html` | ~52KB | 单文件 1800+ 行 JS、12 个 fetch 散落 |

---

## 🔴 高优先级

### 1. `app.py` 必须拆分（影响最大）
**现状**：1285 行单文件，零类设计，**4 个全局可变状态**（`UPLOAD_PKG_DIR`、`UPLOAD_CONFIG`、`UPLOAD_PY`、`UPLOAD_CFG`）。

**建议拆成 5 个子模块**：
```
app/
├── __init__.py            # 创建 Flask app，注册 blueprints
├── config.py              # 加载 config.json（取代全局 UPLOAD_* 变量）
├── csv_store.py           # read_csv / write_csv / get_fieldnames / _get_video_duration
├── routes/
│   ├── core.py            # /, /api/data, /api/scan, /api/save, /api/delete, /api/video
│   ├── export.py          # /api/export
│   ├── history.py         # /api/merge-history
│   ├── translate.py       # /api/translate
│   └── upload.py          # /api/upload-* 全部（含 _generate_upload_runner 单独文件）
└── utils.py               # _escape_py_str / _resolve_row_range 等
```

**收益**：每个文件 100-300 行，职责单一；单元测试可针对模块；不再需要全局状态。

### 2. 拆掉两个超长函数
| 函数 | 行数 | 位置 | 拆分方案 |
|------|------|------|---------|
| `upload_run` | 265 | L662-L927 | 拆 `prepare_session` / `run_one_video` / `stream_progress` 三个函数 |
| `generate`（嵌套在 upload_run 内） | 225 | L692-L917 | 拆 `run_upload_subprocess` / `parse_upload_log_line` / `update_csv_status` |
| `_generate_upload_runner` | 243 | L962-L1205 | 把嵌入的 Python 脚本字符串**移到独立模板文件** `_upload_runner_template.py.j2` 或 `.txt`，用 `string.Template` 渲染（`$video_json` 占位）。`app.py` 不该有 200 行的字符串字面量 |
| `upload_run_cmd` | 59 | L514-L573 | 拆 `build_cmd_for_session` / `launch_detached` |
| `merge_history` | 74 | L201-L275 | 拆 `parse_history_date_from_filename`（**已存在**！应外提）+ `merge_records` |
| `translate_text` | 66 | L1215-L1281 | 拆 `build_messages` / `call_anthropic_api` / `parse_translation` |

### 3. `device_monitor.py` 拆 `register_to_csv`（136 行 God Method）
- 内部混合了：CSV 字段推断、ffprobe 调时长、缩略图路径、记录去重 — 4 件事
- 建议拆 `infer_category_from_path` / `ensure_csv_header` / `append_or_update_row`
- 同样 `copy_files`（84 行）和 `clear_source_directory`（62 行）都有多职责

### 4. `_upload_now.py` 与 `app.py` 重复的 CSV 工具
两处都实现了 `read_csv / write_csv / get_fieldnames / mark_uploaded`，行为不完全一致（`_upload_now._get_fieldnames` 注释说"avoid dropping columns"，和 `app.get_fieldnames` 走不同代码路径）。

**建议**：抽到 `csv_store.py`（见 #1），两边都用。

### 5. 去掉 4 个全局可变字典
- `UPLOAD_PKG_DIR`、`UPLOAD_CONFIG`、`UPLOAD_PY`、`UPLOAD_CFG` 在路由处理函数里被反复 mutate
- 建议：放进 `config.UploadConfig` 单例（用 `@dataclass(frozen=True)`），路由只读不写；要写时调 `update_upload_config(new_dict)`

---

## 🟡 中优先级（可读性）

### 6. 重复 import / 重复工具
**`app.py` 实测**：
- `datetime` import 2 次
- `json`、`shutil` 各 import 2 次
- 16 个 `try` 块 / 17 个 `except` — 错误处理散落
- 建议：加 `from __future__ import annotations`，顶部一次性 import；统一 `_safe_call(func, default=None)` 包装

### 7. 统一命名
- `get_fieldnames` vs `get_fieldnames_cached` — 为什么不直接全 cache？
- `_get_video_duration` / `_get_file_date` / `parse_history_date_from_filename` / `_resolve_row_range` / `_escape_py_str` / `_generate_upload_runner` — 私有函数命名不一致（部分 `_` 前缀 + 名词短语，部分动词起头）
- 建议统一 `verb_object` 风格（`read_fieldnames_cached` / `parse_video_duration` / …）

### 8. 添加类型注解
所有顶层函数都缺类型注解。`upload_run` 接收 `session_id: str` 返回 `Response` 都不知道。引入 `mypy` / `pyright` 检查后可发现 #9、#10 之类 bug。

### 9. `_generate_upload_runner` 用 `os.path` 还是 `pathlib` 不统一
项目内 `pathlib.Path`（device_monitor.py）和 `os.path`（app.py、_upload_now.py）混用。建议全选 `pathlib` 并封装到 `utils.paths`。

### 10. `templates/index.html` 拆成多文件
**实测**：单文件 52KB，1800+ 行 JS，20 个按钮散落，12 个 `fetch` 散落。

**建议**：
- 抽出 `static/css/main.css`、`static/js/api.js`（12 个 fetch 抽成 `api.scan() / api.save() / api.uploadBatch() ...`）、`static/js/table.js`（列宽/列序拖拽）、`static/js/preview.js`（视频预览）
- 引入 `type="module"` + ES module，告别全局变量污染
- 用 `<script type="module" src="/static/js/main.js">` 引入

### 11. `split_video.py` / `rotate_video.py` 重复 `subprocess.Popen` + ffmpeg
两个文件各自实现了 ffmpeg 调用，错误处理和进度解析各写一份。建议抽 `tools/ffmpeg.py`：
```python
def run_ffmpeg(args, on_line: Callable[[str], None] = None) -> int: ...
def probe_duration(path: Path) -> float: ...
def probe_keyframes(path: Path) -> list[float]: ...
```

### 12. `device_monitor.py` 把 Windows API 调用隔离
- `ctypes` / `kernel32.GetLogicalDrives` / `GetDriveType` 直接散在 `get_available_drives` / `_is_removable_or_external`
- 建议抽 `platform/windows_drives.py`（接口 `list_removable_drives() -> list[DriveInfo]`），未来加 Linux/macOS 时只换实现

### 13. 抽常量到独立文件
- 上传参数（`--country CN --region Shanghai --recorder "lingxu zhou"`）硬编码在 `app.py` 路由里
- `devicePatterns`（`["DCIM", "MP_ROOT", "PRIVATE"]`、`["DJI_001", ...]`）在 `config.json` 里有，但默认值散在 `_load_scan_directory` 里
- 建议集中到 `defaults.py`

---

## 🟢 低优先级（风格）

### 14. 补充 docstring / 类型注解覆盖率
- `app.py` 17 个路由只有 6 个有 docstring
- `device_monitor.py` 20 个方法只有 6 个有 docstring
- 引入 `interrogate`（docstring 覆盖率工具）作为 CI 检查

### 15. 加 `pyproject.toml` + `ruff` + `black` + `mypy`
- 统一 `import` 顺序、字符串引号、缩进
- 替代分散的 `from datetime import datetime` 风格

### 16. `launcher.py` 和 `run.py` 二选一
- `launcher.py` 只做"设置工作目录 + import run.main"
- `run.py` 的 main 才是入口
- 建议：合并到 `run.py`，spec 改指向 `run.py`

### 17. 加 `__all__` 导出
- `app.py` 暴露 28 个顶层函数/符号但 `__all__ = [...]` 不存在
- `device_monitor.py` 暴露 9 个顶层符号同上

### 18. `__pycache__/` 目录被错误追踪
目录里有 `__pycache__/` 但 `.gitignore` 缺少 `__pycache__/` 规则（已检查 `.gitignore` 79 字节）。建议补：
```
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
```

### 19. Magic strings 集中
- "yes" / "no" 散在上传和 CSV 标记里（"Yes"/"No" 大小写不一致）
- "uploaded" / "local" / "failed" 状态字符串
- 建议：抽 `Status` Enum

### 20. 超长行
`app.py:896` 有 169 字符一行（f-string 写日志）。拆成多行 + 显式 `.format()` 或变量。

---

## 🎯 推荐落地顺序

| 阶段 | 改动 | 工作量 | 收益 |
|------|------|--------|------|
| **Sprint 1** | 抽 `csv_store.py` + `config.py`（去 4 个全局状态）+ 统一 CSV 工具 | 0.5d | 消灭重复，app.py -150 行 |
| **Sprint 2** | 拆 `app.py` 成 blueprints / 抽 `upload.py` routes 单独文件 | 1d | 1285 → 5×250 行 |
| **Sprint 3** | 拆 `device_monitor.register_to_csv` / 抽 `platform/windows_drives.py` / 抽 `tools/ffmpeg.py` | 1d | device_monitor -200 行、消除跨平台硬编码 |
| **Sprint 4** | 拆 `templates/index.html` 为 ES module（api.js / table.js / preview.js）| 1.5d | 单文件 → 7 个 <300 行模块 |
| **Sprint 5** | 加 ruff + mypy + interrogate + pyproject.toml | 0.5d | CI 长期保质 |

合计 **~4.5 天**，代码量减少约 30%，可理解性显著提升。

---

## 📌 单条快速可做的"立即见效"改动（30 分钟）

如果只能做一件：

1. 把 `app.py:1-30` 顶部 4 个全局 `UPLOAD_*` 替换为 `config.UploadConfig` dataclass
2. 删掉重复的 `import json / import shutil` 各 1 次
3. 删掉重复的 `from datetime import datetime` 1 次
4. 给 `app.py` 顶部加 `from __future__ import annotations`
5. 抽 `app.csv_helpers.py` 装 `read_csv / write_csv / get_fieldnames`，`app.py` 和 `_upload_now.py` 共同引用

这 5 步 30 分钟内能改完，不破坏行为，但立刻带来"不重复"、"无全局可变状态"、"两条路径共享同一 CSV 实现"的好处。
