# Workflow — video-sort-package

> 执行流程 + 质量门禁。AI / 工程师遵守。

---

## 1. 端到端流程

```
接收任务
   ↓
[阶段 0] 读 wcs-manifest.yaml + 任务相关 docs
   ↓
[阶段 1] 制定计划（实现 + 验证 + 文档更新）
   ↓
[阶段 2] 实现（遵循 CODING_STANDARDS）
   ↓
[阶段 3] 验证（curl / 浏览器 / 集成脚本）
   ↓
[阶段 4] 文档同步（按 manifest 的 update_trigger）
   ↓
[阶段 5] 交接
```

---

## 2. 阶段 0：启动与对齐

**必做**：
1. 读 `wcs-manifest.yaml`（~2KB）
2. 根据 `task_mapping` 加载该任务类型的 docs
3. 读 `docs/CODING_STANDARDS.md`
4. 明确功能/缺陷范围 + 验收标准

**跳过**：
- 不要全量读所有 docs（~30KB 浪费）
- 不要从 `templates/index.html` 头开始读（1893 行）

---

## 3. 阶段 1：开发前置门禁

实现前必须答清：

| 问题 | 示例回答 |
|---|---|
| 任务类型 | new_feature / bug_fix / handoff / review / audit |
| 验收标准 | "扫描 codec-hmd 后 CSV 含 3 行 file_type=hmd" |
| 约束 | 浏览器兼容、CSV 向后兼容、性能 |
| 受影响文件 | `app.py` + `templates/index.html` + `config.json` |
| 验证策略 | curl 端点 + 浏览器硬刷新 + 看 csv_backups |
| 回滚方案 | `git checkout HEAD~ -- app.py` 或备份 CSV 还原 |

---

## 4. 阶段 2：实现

**原则**：
- 单一职责：每个函数 / endpoint 只做一件事
- 命名清晰：`scan_hmd_dir` 比 `process1` 好
- 配置外置：路径 / 列定义从 `config.json` 读
- 兼容默认：旧 CSV 13 列不破坏，新字段为空
- diff 聚焦：单 PR 一个能力，不夹带无关重构

**编码检查清单**：
- [ ] 函数 < 50 行（超长拆函数）
- [ ] 命名遵循 CODING_STANDARDS §1
- [ ] 错误处理：try/except 不吞错，至少 log / alert
- [ ] 资源释放：decoder.close() / canvas clear / 视频 src=''
- [ ] 中文注释：解释"为什么"，不是"做了什么"

---

## 5. 阶段 3：验证

### 5.1 后端集成

```bash
cd ./vendor
python -c "from src.app import app; print(len(app.url_map._rules), 'routes')"
# 期望: 30+ routes 无冲突

# 启动
python src/run.py
# 或双击 启动视频管理.bat
# Ctrl+Shift+Esc → 详细信息 → 找 python.exe → EndProcess 杀旧进程
# 端口被占用时: netstat -ano | findstr :5000
```

### 5.2 端点验证（Python + requests）

```python
import requests
r = requests.post('http://localhost:5000/api/scan',
    json={'directory': r'F:\...\codec-hmd'})
print(r.status_code, r.json().get('count'))
```

### 5.3 前端验证

```bash
# 硬刷新: Ctrl+F5（避免浏览器缓存）
# 看 Console: 无 JS 报错
# 测关键路径:
#   1. 扫描 → 表格出现新行
#   2. 点预览 → 视频播放（mp4）或双 canvas（hmd）
#   3. 改字段 → 保存 → CSV 更新
#   4. 上传 → SSE 进度
```

### 5.4 语法检查

```bash
# 提取 inline script 验证（避免改坏 JS）
node -e "
const fs = require('fs');
const html = fs.readFileSync('src/templates/index.html', 'utf8');
const re = /<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi;
let m, idx = 0;
while ((m = re.exec(html)) !== null) {
  idx++;
  fs.writeFileSync('_tmp_' + idx + '.js', m[1]);
}
"
for f in _tmp_*.js; do node --input-type=module --check < "$f"; done
```

---

## 6. 阶段 4：文档同步（WCS）

按 manifest 的 `update_trigger` 决定更新哪些 docs。**禁止**：
- 改代码不动文档（违反 WCS）
- 文档更新不对应代码（违反"事实来源"原则）

| 变更类型 | 必须更新 |
|---|---|
| 新增端点 | `docs/features.md` + `docs/project_status.md` |
| 改 schema（CSV 列 / config） | `docs/structure.md` + `docs/CODING_STANDARDS.md` |
| 修 bug | `docs/error_book.md`（追加 E{n}）+ `docs/dev_log.md` |
| 改流程 | `docs/workflow.md` + `docs/CODING_STANDARDS.md` |
| 新增/删除文件 | `docs/structure.md` + 同步 wcs-manifest.yaml |
| 任务完成 | `docs/dev_plan.md`（✅）+ `docs/dev_log.md` |

---

## 7. 阶段 5：交接

给出可被其他 AI / 工程师接续的清单：

- 任务范围与结果（什么完成 + 什么没做）
- 变更文件清单（绝对路径）
- 验证结果（curl/浏览器输出）
- 已知限制（error_book.md 链接）
- 建议下一步（dev_plan.md 下一个任务）

格式：纯文本 / Markdown bullets，便于复制。

---

## 8. 协作约定

### 多 AI 并行

- 同时只跑一个 AI 在同一分支上
- 改 app.py 前先 `git pull`（避免覆盖）
- WCS 文档更新必须串行（避免 manifest 不一致）

### 多工程师

- CSV 改字段前在 `docs/dev_log.md` 留 entry（记录 schema migration）
- 大改前先建 `csv_backups/manual_<date>.csv` 备份

### 与用户

- 关键决定（删除行、改 schema）必须先确认
- 进度汇报：每完成一个 PR 给一次
- 不要修改用户没要求改的部分（无关重构违反 §4 diff 聚焦）

---

## 9. 常见陷阱（来自 error_book）

| 陷阱 | 防范 |
|---|---|
| WebCodecs "key frame required" | configure 后第一帧必须是 IDR |
| Flask reloader 子进程残留 | 改完代码 netstat 看 LISTEN 数 |
| HMD duration 不可靠 | metadata.frame_counts 为空，靠客户端回填 |
| scan 扩散 | `scope=current`（默认） |
| JS 残留代码块 | 大段重写用 read+replace 整段，改完 node --check |
| Linux 无 WebCodecs | 启动检测，不可用时禁 HMD 按钮 |
| HEVC fps 硬编码 30 | 容器不携带，待 PR 加 SPS vui 解析 |
| **docstring 中 `\u` Unicode 转义** | docstring/f-string 中避免裸反斜杠路径，用正斜杠或 raw string |
| **CJS require 无法加载 ESM** | 必须 CJS wrapper + `import()` 桥接 |
| **HMD 设备无 RTC** | 文件时间戳默认 2021-01-01；用 metadata.start_time 或目录名 MMDD 推断 |
| **Windows ctime ≠ 录制时间** | ctime 是复制时间；用 ffprobe creation_time 或 mtime |