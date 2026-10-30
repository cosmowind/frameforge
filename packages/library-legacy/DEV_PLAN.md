# DEV PLAN — 2026-06-09

> 当次会话的目标、进度、待办。Context 满了之后可凭此继续。

---

## ✅ 已完成

### 1. AI 翻译 → 中英自动补全（替换 MiniMax）
- **删除**：`/api/translate` 路由 + `translate_text` 函数（app.py -68 行）
- **删除**：`config.json.translate` 段（含泄露的 API key，已 [REDACTED]）
- **删除**：`templates/index.html` 中"译"按钮、`.btn-translate` CSS、`translateCell()` 函数
- **新增**：`pickCanonicalEnglish(cn, excludeIndex)` 4 条规则
  1. 1 条 → 用自己
  2. 2 条 → 用"另一条"
  3. > 2 条 → 出现最多的
  4. 并列最多 → 随机 + Toast 提示加 `-1/-2/-3` 后缀
- **新增**：`handleCellEdit` 拆为两个：
  - `handleCellEditLive`（input 事件）— 实时写回 + 中文自动补全，**不弹框**
  - `handleCellEditCommit`（change/INPUT blur）— 离焦后才问"应用到全部"
- **新增 UI**：弹框 `#applyAllDialog`、toast `#toast`、CSS `.toast`
- **测试**：`verify_auto_complete.js`（16/16 通过，含 Case F：连续 5 次 input 弹 0 次框 + blur 弹 1 次）
- **README** 更新：AI 翻译段替换为"中英自动补全"
- **docs/minimax接入参考.txt** 替换为废弃说明

### 2. 📁 目录选择按钮
- **后端**：`/api/pick-directory` 用 `tkinter.filedialog.askdirectory()` 子进程（不阻塞 Flask）
- **前端**：`<input id="dirPath">` 旁加 `<button id="btnPickDir">📁 选择</button>` + `pickDirectory()` 函数
- **测试**：POST `/api/pick-directory` 返回 `{"path":null}`（用户取消）

### 3. 日期字段反填 bug 修复
- **Bug**：`scan_date`（录入日期）被错填为文件创建时间；`original_history_date`（原始日期）始终空
- **修复**（app.py `scan_directory` + device_monitor.py `register_to_csv`）：
  - `scan_date = datetime.now().strftime("%Y-%m-%d")` ← 今天
  - `original_history_date = _get_file_date(path)` ← 文件创建时间
- **迁移**：`POST /api/fix-dates` 端点，一次性把旧数据修正
  - 测试结果：`{"moved":10, "today":"2026-06-09"}` 然后 `{"moved":0}` 幂等

### 4. 录入日期保护（双保险）— ✅ 验证完成
- **前端**：`scan_date` 单元格默认 `readonly`，`✏️` 按钮 → `toggleScanDateLock()` 解锁/重锁
- **后端**：`/api/save` 读取旧 CSV，若新数据中某行 `scan_date` 为空而旧 CSV 中有值，则回填旧值
  ```python
  if not cleaned_row.get("scan_date"):
      old = existing_by_path.get(cleaned_row.get("path", ""))
      if old and old.get("scan_date"):
          cleaned_row["scan_date"] = old["scan_date"]
          protected += 1
  ```
  返回 JSON 多了 `"protected": <int>` 字段
- **测试**：`verify_scan_date_protection.py` 4 个用例全过（清空/正常编辑/显式改/还原）

### 5. 排序重做（3 状态循环 + 多列优先级）— ✅ 完成
- **旧实现 bug**：
  - 只有 2 状态切换（升/降），无"无排序"恢复
  - 多列排序：第二次点击会**覆盖**第一次（用 `sortColumn` 单变量）
  - 数字/日期/字符串比较混在一个函数
- **新设计**：
  - `sortStack = [{col, dir}, ...]`，数组末尾 = 最高优先级
  - 3 状态循环：未在栈 → push asc；asc → splice+push 改 desc（升为第一优先）；desc → splice 移除
  - `compareSingle(a, b)` 拆出：数字 → 数字比较；`YYYY-MM-DD...` → 日期比较；其他 → `localeCompare`（zh-Hans-CN）
  - `compareRows(a, b)` 遍历 sortStack 逐级比较
- **UI 反馈**：
  - 表头标题旁：未排序列灰色 ▲；已排序列蓝色 ▲/▼；多列时加 `<sup>1</sup>` `<sup>2</sup>` 角标表示优先级
  - `title` 提示："点击切换：无 → 升序 → 降序"
- **持久化**：
  - `saveColConfig` 同时发 `sortStack` + 兼容旧字段 `sortColumn`/`sortDirection`
  - `loadConfig` 优先读 `sortStack`，旧字段回填
  - 后端 `/api/config` 白名单加 `sortStack`（L136）
- **测试**：`verify_sort.js` 19 个断言全过（3 状态循环 / 多列优先级 / 比较结果 / 类型支持 / 持久化兼容）

---

## ✅ 当前状态：全部完成

| 任务 | 状态 |
|------|------|
| AI 翻译 → 自动补全 | ✅ 16/16 |
| 目录选择按钮 | ✅ |
| 日期字段反填 bug | ✅ |
| 录入日期双层保护 | ✅ 4/4 |
| 排序 3 状态 + 多列 | ✅ 19/19 |
| CSV 修复（`/api/fix-empty-scan-dates` 一次迁移 1 行）| ✅ |
| 测试脚本 emoji GBK | ✅（`sys.stdout.reconfigure(encoding='utf-8')`）|

---

## 🆕 排序设计（已完成归档 — 见上文"### 5. 排序重做"段）

**需求回顾**：
1. **3 状态循环**：点击列头在 `无 → 升序 → 降序 → 无` 之间循环 ✅
2. **多列排序**：先点 A → A 升序；再点 B → B 升序为**第一优先级**、A 降为第二优先级（最后点的最优先）✅
3. **解决原版"一直有问题"** ✅

**最终实现摘要**（详见"### 5. 排序重做"段）：
- `sortStack` 数组 + `compareSingle` 拆数字/日期/字符串三类
- `verify_sort.js` 19/19 断言全过

---

## 📁 项目结构变更清单（相对 .claude 上下文开始时）

| 文件 | 状态 |
|------|------|
| `app.py` | -68 行（删 translate_text）+ ~25 行（save 保护 + fix-dates + pick-directory）|
| `templates/index.html` | -45 行（删 translate）+ ~80 行（自动补全 + 弹框 + toast + 路径选择 + 锁定切换）|
| `config.json` | -5 行（删 translate 段）|
| `docs/minimax接入参考.txt` | 整文件替换为废弃说明 |
| `README.md` | AI 翻译段 → 中英自动补全段 |
| `OPTIMIZATIONS.md` | 未变 |
| `verify_auto_complete.js` | **新增**：16 个单元测试 |
| `verify_scan_date_protection.py` | **新增**：4 个端到端测试（emoji 修了，全过）|
| `verify_sort.js` | **新增**：19 个端到端断言（3 状态循环 + 多列优先级 + 类型 + 持久化）|
| `DEV_PLAN.md` | **本文件** |

## 🧪 测试方法

```bash
# 启动
cd "./workspace"
python run.py

# 端到端（全部应通过）
node verify_auto_complete.js          # 16/16
python verify_scan_date_protection.py # 4/4
node verify_sort.js                   # 19/19

# API
curl -X POST http://localhost:5000/api/fix-dates
curl -X POST http://localhost:5000/api/fix-empty-scan-dates
curl -X POST http://localhost:5000/api/pick-directory -H 'Content-Type: application/json' -d '{}'
curl -X POST http://localhost:5000/api/translate -d '{}'  # 应 404
```

## 🔑 关键代码位置

- `app.py:136` — /api/config 白名单加 sortStack
- `app.py:188` — 扫描时 scan_date = today
- `app.py:241-243` — merge_history 两日期都用 hist_date（未动）
- `app.py:321-352` — save_data 保护 scan_date
- `app.py:1249-1266` — /api/fix-empty-scan-dates 一次迁移
- `app.py:1267+` — /api/pick-directory
- `device_monitor.py:268-281` — register_to_csv scan_date = today
- `templates/index.html:360-372` — sortStack 全局 + loadConfig 恢复（含旧字段兼容）
- `templates/index.html:420-477` — toggleSort 3 状态循环 + compareSingle + compareRows
- `templates/index.html:556-580` — saveColConfig 发 sortStack + 兼容字段
- `templates/index.html:695-715` — 表头渲染：箭头 + 优先级角标
- `templates/index.html:720-730` — scan_date 默认只读 + ✏️ 按钮
- `templates/index.html:785-820` — handleCellEditLive / handleCellEditCommit 拆分
- `templates/index.html:822-850` — pickCanonicalEnglish 4 条规则
- `templates/index.html:855-880` — 弹框 + Toast

## 📌 启动器 `启动视频管理.bat` — 未触碰

内容确认：仅 `chcp 65001 → python --version → pip show flask → python run.py → pause`，无 translate/MiniMax 引用。
