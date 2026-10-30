# CODING STANDARDS — video-sort-package

> 项目代码规范纲领。AI 编码前必读。

---

## 1. 命名

### Python

- 函数/变量：`snake_case`
- 类：`PascalCase`
- 常量：`UPPER_SNAKE_CASE`（如 `SESSION_MARKER`）
- 私有：前缀 `_`（如 `_fmt_duration`）
- 模块级：`lowercase.py` 或 `snake_case.py`

### JavaScript（前端 / ESM）

- 函数/变量：`camelCase`（如 `openHmdPreviewInline`）
- 常量：`UPPER_SNAKE_CASE`（如 `HMD_FILE_EXTS`）
- ESM 模块：`export const fnName` 优先于 `export default`
- DOM 元素 id：`camelCase`（如 `hmdLeftCanvas`）

### 文件 / 目录

- 模板：`templates/<name>.html`
- 静态：`static/<module>/<file>.js`
- CSV：`snake_case.csv`（如 `video_manager.csv`）
- 文档：`docs/<name>.md`

---

## 2. 项目结构

```
app.py                       # 单文件后端（不分子模块，未来评估）
templates/index.html        # 单 SPA
templates/hmd_preview.html   # 独立预览页
static/hmd/*.esm.js          # HMD 浏览器模块
device_monitor.py            # 独立进程/线程模块
docs/                        # WCS 基线文档
config.json                  # 列定义
video_manager.csv            # 主数据
```

**禁止**：
- 把 JS 拆到 `static/js/*.js` 多文件（除非真的需要模块化）
- 把 Python 拆到 `app/` 包（除非超过 3000 行）
- 把 CSV 字段硬编码在多个地方（统一从 `DEFAULT_FIELDNAMES` 读）

---

## 3. CSV 读写

### 写入（`write_csv` / `_atomic_write`）

```python
# 1. 自动备份 10 份到 csv_backups/
# 2. 原子写：先写 .tmp，再 os.replace
# 3. 字段顺序由 get_fieldnames() 返回（合并 DEFAULT_FIELDNAMES）
```

**禁止**：
- 直接 `open(CSV_PATH, 'w')` 不备份
- 写后 `os.remove(.tmp)` 不 replace（崩溃会留垃圾）
- 字段顺序硬编码（用 `fieldnames` 参数）

### 读取（`read_csv`）

```python
with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    return [row for row in reader]
```

**统一编码**：所有 CSV 用 `utf-8-sig`（带 BOM，Excel 兼容）。

---

## 4. 后端 API 设计

### 端点命名

- 资源：`/api/<resource>`（如 `/api/hmd/scan`）
- 子资源：`/api/<resource>/<id>`（如 `/api/dim/<table>`）
- 动词仅用于非 CRUD 操作（`/api/upload-run`）

### 响应格式

- 成功：`{"ok": true, ...data}` 或 `[...]`
- 错误：`{"error": "msg"}` + HTTP 4xx/5xx

### 请求体

- JSON：`request.get_json(silent=True) or {}` 容错
- 路径参数：`request.args.get("path", "").strip()`
- 必填项缺失：返回 400 + 明确错误信息

### 文件流

- 支持 Range：`send_file(path, conditional=True)`
- 仅服务 `.hmd` / `.mp4`：`path.lower().endswith(...)` 检查
- 路径遍历防护：`os.path.normpath` 后 `startswith(parent_dir)`

---

## 5. 前端代码组织

### 单文件原则

`templates/index.html` 是单 SPA，所有 CSS / JS / HTML 在一个文件里。
**禁止**：
- 拆到 `static/css/*.css` 多文件
- 拆到 `static/js/*.js` 多文件（除非 ESM 模块如 `hmd-decode.esm.js`）
- 用外部 React/Vue（保持零依赖 + 单文件可调试）

### JS 模块

- 顶部 `let tableData = []` 等全局变量
- 函数用 `function name() {}` 声明（不用箭头除非回调）
- 异步：`async function name() {}` + `await`
- DOM 操作：`document.getElementById('xxx')`（不缓存，复用低）
- 错误：`try { ... } catch (e) { alert(...); }` 或 `setHmdErr(...)`

### 列类型扩展

新增列类型时：
1. 加到 `config.json` 的 `columnTypes`
2. 在 `preview()` 渲染表单的 `if/else` 链里加分支
3. 在 `renderTable()` 单元格渲染里加分支

---

## 6. WebCodecs / HEVC

### 必须遵守

- **`configure()` / `flush()` 后第一帧必须是 IDR**（NAL type 19/20）
- **时间戳单调递增**（不复用 0）
- **每个 frame NAL 独立 AVCC 包装**（4 字节大端长度 + body）
- **解码器配置**：build hvcC description（22 字节头 + VPS/SPS/PPS arrays）

### 推荐模式

```js
// 找最近 IDR
function findIdrAtOrBefore(nals, targetIdx) {
  let idr = 0;
  for (let k = 0; k < targetIdx && k < nals.length; k++) {
    if (nals[k].type === 19 || nals[k].type === 20) idr = k;
  }
  return idr;
}
// 单调时间戳
function feedFrame(dec, nal, frameIdx) {
  dec.decode(new EncodedVideoChunk({
    type: nal.type === 19 ? 'key' : 'delta',
    timestamp: frameIdx * FRAME_US,
    duration: FRAME_US,
    data: avccWrap(nal),
  }));
}
```

---

## 7. 测试与验证

### 当前没有单元测试

用以下方式验证：
- **集成**：curl 调端点，检查响应码 + JSON 内容
- **前端**：浏览器手动测试（无 headless 测试）
- **静态分析**：`node --input-type=module --check < extracted.js`

### 提交前必做

1. `python -c "import app"` — 模块能加载（27+ 路由无冲突）
2. `curl /api/scan` — 扫描正常
3. 浏览器硬刷新（Ctrl+F5）— 前端资源更新
4. CSV 写入后看 `csv_backups/` 有新备份

---

## 8. 文档同步（WCS）

改完代码后，**按 manifest 的 `update_trigger`** 更新对应 docs：

| 变更类型 | 更新文档 |
|---|---|
| 新增/删除模块 | `docs/structure.md`, `docs/project_status.md` |
| 新增能力 | `docs/features.md` |
| 缺陷修复 | `docs/error_book.md`, `docs/dev_log.md` |
| 流程变更 | `docs/workflow.md` |
| 规范修订 | 本文件 |
| 用户可见变化 | `README.md` |

禁止：
- 在文档中粘贴大量代码（用链接引用）
- 写流水账（dev_log 只记事实 + 验证依据）

---

## 9. 提交规范

格式：`<type>: <summary>`

- `feat`: 新功能
- `fix`: 修 bug
- `refactor`: 重构
- `docs`: 文档
- `chore`: 杂项

建议单 PR 聚焦一个能力（如 "PR 1: HMD 集成基础"），避免混改。

---

## 10. 性能 / 安全

- **不要**在请求中调用 `ffprobe` 大文件（已有限时 15s）
- **不要**直接服务用户提供的任意路径（必须 normpath + startswith 检查）
- **不要**在 CSV 中存敏感信息（password / cookie）
- 跨域：暂未启用 CORS（本地工具，部署时再加）