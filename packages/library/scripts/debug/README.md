# 测试与调试合集

> 项目中所有测试脚本和调试脚本的统一索引。
> 最后更新：2026-07-01

---

## 📋 总览

| 目录 | 脚本数 | 用途 | 运行方式 |
|------|--------|------|---------|
| `scripts/debug/` | 9 | Playwright 自动补录临时调试 | `python scripts/debug/xxx.py` |
| `src/scripts/test_*.py` | 5 | 可复用集成测试 | `python src/scripts/xxx.py` |
| `src/scripts/verify_*.py` | 3 | 端到端验证 | `python src/scripts/xxx.py` |

---

## 🧪 可复用集成测试（`src/scripts/`）

### Flask 路由测试

| 脚本 | 测试目标 | 测试内容 | 运行前提 |
|------|---------|---------|---------|
| `test_flask_routes.py` | Flask 启动 + 基本响应 | 14 个路由冒烟测试（GET/POST） | Flask 运行中 |
| `test_flask_routes2.py` | 写入/扫描/删除路由 | 15 个路由扩展测试 | Flask 运行中 |
| `check_routes.py` | 路由清单 | 列出所有注册的路由和函数 | Flask 运行中 |

### 功能测试

| 脚本 | 测试目标 | 测试内容 | 运行前提 |
|------|---------|---------|---------|
| `test_autofill.py` | 自动补录 API | E2E 测试 auto-fill / clipboard API | Flask + Chrome 9222 |
| `test_scan.py` | 设备监控 | DeviceMonitor 初始化和扫描 | 无 |
| `test_upload.py` | 上传功能 | 上传流程测试 | Flask 运行中 |

### 端到端验证

| 脚本 | 测试目标 | 测试内容 | 运行前提 |
|------|---------|---------|---------|
| `verify_pages.py` | 全端点验证 | 38 个端到端 case（启 Flask + curl 全套端点） | 无（自动启 Flask） |
| `verify_auto_complete.js` | 自动补全 | Node.js E2E 测试 | Flask 运行中 |
| `verify_sort.js` | 排序功能 | Node.js E2E 测试 | Flask 运行中 |

### 诊断工具

| 脚本 | 用途 | 说明 |
|------|------|------|
| `diagnose_form.py` | 上传表单诊断 | 检查表单字段和选项 |
| `check_hmd_cache.py` | HMD 缓存完整性 | 检查缓存文件是否完整 |
| `check_all_cache_integrity.py` | 全量缓存完整性 | 批量检查所有缓存 |
| `check_source_integrity.py` | 源文件完整性 | 检查源视频文件是否存在 |
| `check_routes.py` | 路由清单 | 列出所有路由和函数 |
| `verify_scan_date_protection.py` | scan_date 保护 | 验证 scan_date 不被清空 |

---

## 🔧 临时调试脚本（`scripts/debug/`）

> Playwright 自动补录功能的深度调试脚本。
> 运行前提：Chrome 已通过 `start_helper.bat` 启动（9222 CDP 端口）

**调试对象**：`https://publish.example.com/vendors?tab=upload-history`
**核心功能**：自动补录视频元数据（operator_name / task_description / environment_description）
**依赖**：`src/scripts/auto_fill_helper.py`（注入的 JS 逻辑）

### 流程调试（端到端流程验证）

| 脚本 | 调试目标 | 方法 |
|------|---------|------|
| `temp_autofill_flow.py` | 完整补录流程 | 导航 → 筛选（Capture=Stereo + Excludes 标签）→ 点击 tile → 检查 modal 状态 |
| `temp_autofill_test.py` | JS 注入 + 面板初始化 | 注入 auto_fill_helper.js → 验证 `#autoFillPanel` 存在 → 设置筛选 → 点击 tile |
| `temp_fill_test.py` | 字段填充机制 | 从 `/api/auto-fill` 获取字段 → 生成填充 JS → `page.evaluate` 执行 → 检查结果 |

### Ctrl+B 快捷键调试（键盘触发补录）

| 脚本 | 调试目标 | 方法 |
|------|---------|------|
| `temp_ctrlb_test.py` | Playwright fill + run() | 注入 JS → Playwright fill 3 字段 → 暴露 `run()` 到 `window` → 调用 |
| `temp_ctrlb_test2.py` | JS 直接填充 | 注入 JS → `page.evaluate` 直接填 3 字段（绕过 Playwright fill）→ 点击面板按钮 |
| `temp_test2.py` | keydown 事件派发 | 注入 JS → Playwright fill 3 字段 → `dispatchEvent(keydown, Ctrl+B)` → 检查结果 |

### 线上页面调试（真实页面验证）

| 脚本 | 调试目标 | 方法 |
|------|---------|------|
| `temp_live_test.py` | 线上补录流程 | 注入 JS → `page.evaluate` 填 3 字段 → 点击 `#autoFillMainRow` 触发 → 读取填充结果 |
| `temp_live_test2.py` | 线上上传表单 | 点击 Upload 按钮打开表单 → 注入 JS → 填 3 字段 → 触发补录 |

### 点击交互调试（UI 元素定位）

| 脚本 | 调试目标 | 方法 |
|------|---------|------|
| `temp_click_test.py` | 视频 tile 展开 | `page.mouse.click` 点击第一个 tile → 搜索 "missing" 文本、展开按钮、Edit metadata 元素 |

### 调试技巧

```bash
# 运行任意调试脚本
python scripts/debug/temp_autofill_flow.py

# 调试新场景：复制任一脚本修改即可
```

1. **查看页面状态**：`page.screenshot(path='debug.png')`
2. **检查元素**：`page.evaluate("document.querySelector('#xxx')")`
3. **断点调试**：`input("Press Enter to continue...")`
4. **查看网络请求**：`page.on("request", lambda r: print(r.url))`

### 与正式脚本的关系

| 调试脚本 | 对应的正式脚本 |
|---------|--------------|
| `temp_autofill_*.py` | `src/scripts/auto_fill_helper.py` + `src/scripts/scan_all_videos.py` |
| `temp_ctrlb_*.py` | `src/scripts/auto_fill_helper.py`（Ctrl+B 快捷键逻辑） |
| `temp_fill_test.py` | `src/services/autofill_service.py` + `src/routes/upload_routes.py` |
| `temp_click_test.py` | `src/scripts/scan_all_videos.py`（tile 点击 + missing 检测） |

---

## 🗑 已清理的一次性脚本

以下脚本已完成使命，已删除（可通过 git 历史恢复）：

| 脚本 | 用途 | 删除时间 |
|------|------|---------|
| `fix_single_field.py` | 单字段批量修复（Playwright 深度补录） | 2026-07-01 |
| `fix_three_fields.py` | 三字段批量修复（environment/facility_venue/scene） | 2026-07-01 |
| `scripts/_test_pg_connection.py` | PG 连接 SSL 模式诊断 | 2026-07-01 |
