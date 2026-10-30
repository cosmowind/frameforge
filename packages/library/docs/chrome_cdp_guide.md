# Chrome CDP 自动化操作指南

## 1. Chrome 启动参数（关键）

```bat
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --remote-debugging-port=9222 ^
  --user-data-dir=%LOCALAPPDATA%\chrome_auto_fill_profile ^
  --remote-allow-origins=http://localhost:9222 ^
  --allow-running-insecure-content ^
  --disable-web-security ^
  "https://publish.example.com/vendors?tab=upload-history"
```

**必须参数：**
- `--remote-debugging-port=9222` — 开启 CDP 调试端口
- `--user-data-dir=...` — 独立 Profile，绕过 SingletonLock 冲突
- `--remote-allow-origins=http://localhost:9222` — 允许 WebSocket 握手
- `--allow-running-insecure-content` — 允许 HTTPS 页面调 HTTP API
- `--disable-web-security` — 禁用 Web 安全（同源策略）

**启动后验证：**
```bash
curl http://localhost:9222/json/version
# 应返回 {"Browser": "Chrome/149...", "webSocketDebuggerUrl": "ws://..."}
```

## 2. Playwright 连接 Chrome

```python
from playwright.sync_api import sync_playwright

pw = sync_playwright().start()
browser = pw.chromium.connect_over_cdp('http://localhost:9222')
page = browser.contexts[0].pages[0]
```

**注意：** `page.locator().fill()` 在某些 publish.example.com 表单上会导致 Connection closed，**全部用 `page.evaluate()` + JS 注入代替 Playwright 原生 API**。

## 3. 筛选条件设置（每次启动后必做）

```javascript
// Capture → Stereo
var selects = document.querySelectorAll("select");
for (var i = 0; i < selects.length; i++) {
    var opts = Array.from(selects[i].options).map(function(o){ return o.textContent.trim(); });
    if (opts.some(function(o){ return o.indexOf("Stereo") >= 0; })) {
        selects[i].value = "stereo";
        selects[i].dispatchEvent(new Event("change", {bubbles:true}));
        break;
    }
}

// Excludes tags → review_reject / vendor-delete / wipe
var btns = document.querySelectorAll("button");
for (var i = 0; i < btns.length; i++) {
    if ((btns[i].textContent || "").indexOf("Excludes") >= 0) {
        btns[i].click(); break;
    }
}
// 等 500ms 后依次点击三个标签
for (var tag of ["review_reject", "vendor-delete", "wipe"]) {
    var tagBtns = document.querySelectorAll("button");
    for (var i = 0; i < tagBtns.length; i++) {
        if ((tagBtns[i].textContent || "").indexOf(tag) >= 0) {
            tagBtns[i].click(); break;
        }
    }
    // 等 200ms
}
// 按 ESC 关闭下拉
page.keyboard.press("Escape");
```

## 4. 视频卡片定位与点击

**关键发现：** 点击 `.vcb-tile` div 本身无效，**必须点击 `.vcb-tile-media` 按钮区域**。且必须先 `scrollIntoView` 使 tile 可见，否则坐标偏移。

```javascript
// 先滚动到 tile 可见，再取坐标点击
var tiles = document.querySelectorAll('.vcb-tile');
var tile = tiles[idx];
var media = tile.querySelector('.vcb-tile-media');
media.scrollIntoView({behavior: 'instant', block: 'center'});
var r = media.getBoundingClientRect();
var cx = Math.round(r.x + r.width / 2);
var cy = Math.round(r.y + r.height / 2);
// scrollIntoView 后等 300ms 再点击
time.sleep(0.3)
page.mouse.click(cx, cy);
```

**原因分析：** `.vcb-tile` 的点击事件被内部 `.vcb-tile-media` button 拦截，只有点击 media 区域才能打开 modal。下方 tile 不在视口内时坐标计算错误。

## 5. Modal 检测与 missing 数量

点击 tile 后 1.2 秒检查 modal：

```javascript
// 检测 modal 是否出现
var modal = document.querySelector('.vcb-modal-overlay');
if (!modal) return {error: 'no modal'};

// 从 modal 文本提取 missing 数量
var txt = modal.textContent || '';
var m = txt.match(/(\d+)\s*missing/);
return m ? parseInt(m[1]) : 0;  // 0 = 无 missing（已填完）

// 关闭 modal
page.keyboard.press("Escape");
```

**Modal 结构：** 点击 tile 后出现 `.vcb-modal-overlay`，包含 `Task attributes` 文字和 `Edit metadata` 按钮（如果有 missing）。

## 6. Edit Metadata 表单

**点击 Edit metadata 按钮：**

```javascript
var modal = document.querySelector('.vcb-modal-overlay');
var btns = modal.querySelectorAll('button');
for (var i = 0; i < btns.length; i++) {
    var txt = (btns[i].textContent || '').trim();
    if (txt.indexOf('Edit') >= 0 || txt.indexOf('metadata') >= 0) {
        btns[i].click();
        break;
    }
}
```

**表单字段定位（使用 placeholder）：**

```javascript
function findVisibleInput(ph) {
    var phL = ph.toLowerCase();
    return Array.from(document.querySelectorAll('input')).find(function(el) {
        if (!isVisible(el)) return false;
        return (el.getAttribute('placeholder') || '').toLowerCase().includes(phL);
    }) || null;
}

function isVisible(el) {
    if (!el) return false;
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && r.x >= 0 && r.y >= 0;
}
```

**publish.example.com 表单字段 placeholder 列表（第一批）：**

| 字段 key | placeholder 关键词 |
|----------|-----------------|
| operator_name | `Operator name` |
| task_description | `Task description` |
| environment_description | `Environment` |
| Standard occupation | `Standard occupation` |
| Scene / workstation | `Scene / workstation` |
| Facility type | `Facility type` |
| Environment category | `Environment category` |
| Stable site | `Stable site` |
| Latitude | `Latitude` |

**下拉 Select 定位（用 label 祖先元素）：**

```javascript
function findVisibleSelect(labelText) {
    var lower = labelText.toLowerCase();
    return Array.from(document.querySelectorAll('select')).find(function(el) {
        if (!isVisible(el)) return false;
        var lbl = el.closest('label');
        return lbl && (lbl.textContent || '').toLowerCase().includes(lower);
    }) || null;
}

function setSelectValue(sel, value) {
    var opts = Array.from(sel.options);
    var vLower = String(value).toLowerCase();
    for (var i = 0; i < opts.length; i++) {
        if (opts[i].value.toLowerCase() === vLower ||
            (opts[i].textContent || '').toLowerCase().includes(vLower)) {
            sel.value = opts[i].value;
            sel.dispatchEvent(new Event('change', {bubbles: true}));
            return true;
        }
    }
    return false;
}
```

**React 受控组件写值（必须用 native value descriptor）：**

```javascript
function setReactValue(el, value) {
    var proto = Object.getPrototypeOf(el);
    var desc = Object.getOwnPropertyDescriptor(proto, 'value');
    if (desc && desc.set) { desc.set.call(el, value); }
    else { el.value = value; }
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
}
```

## 7. 分页操作

**翻页方法（不走 URL，避免重置筛选）：**

用 JS 填页码（React 受控 input，Playwright `fill()` 不触发 change 事件），再用 JS 点击 Go 按钮（Playwright 认为 button disabled）：

```python
# 用 JS native value setter 填页码
page.evaluate(f"""
(() => {{
    var inputs = document.querySelectorAll('input[type=number]');
    var target = inputs[inputs.length - 1];
    if (!target) return;
    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, 'value'
    ).set;
    nativeInputValueSetter.call(target, '{page_num}');
    target.dispatchEvent(new Event('input', {{ bubbles: true }}));
    target.dispatchEvent(new Event('change', {{ bubbles: true }}));
}})()
""")
time.sleep(0.5)

# 用 JS 点击 Go 按钮
page.evaluate("""
(() => {
    var btns = document.querySelectorAll('button');
    for (var i = 0; i < btns.length; i++) {
        if ((btns[i].textContent || '').trim() === 'Go') {
            btns[i].click(); return;
        }
    }
})()
""")
time.sleep(2)
wait_for_tiles(page)
```

**注意：** `page.locator().fill()` 虽然能填入值，但 `button:has-text("Go")` 的 click 会超时（Go 按钮始终 disabled）。**必须用 JS click**。

**等待 tiles 渲染：**

```python
def wait_for_tiles(page, min_count=1, timeout=15000):
    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        count = page.evaluate("document.querySelectorAll('.vcb-tile').length")
        if count >= min_count:
            return count
        time.sleep(0.5)
    return page.evaluate("document.querySelectorAll('.vcb-tile').length")
```

## 8. Autofill JS 注入（Ctrl+B 快捷键）

`INJECT_INIT_JS` 包含：
- 面板插入（`#autoFillPanel` 固定右下角）
- `findOperatorInput()` / `findTaskInput()` / `findEnvInput()` 定位器
- `run()` — 读3字段 → POST `/api/auto-fill` → 填20+字段
- Ctrl+B 快捷键监听（编辑框内不触发）

**触发方式：** 面板按钮点击 `document.querySelector('#autoFillMainRow').click()`

**状态读取：** `document.getElementById('autoFillStatus').textContent`

## 9. 已知问题与 Workaround

| 问题 | 原因 | Workaround |
|------|------|-----------|
| `page.locator().fill()` 报 Connection closed | publish.example.com React 表单拦截 | 全部改用 JS `setReactValue()` |
| 页面加载后 Playwright 连接不稳定 | CDP 连接在页面重载时中断 | 每次操作前 `time.sleep()` 等页面稳定 |
| `page.mouse.click()` 坐标不对 | tile 不在视口内 | 先 `scrollIntoView({behavior:'instant',block:'center'})` + `time.sleep(0.3)` |
| Go 按钮始终 disabled | React 受控 input 不触发 change | 用 JS native value setter + JS click Go 按钮 |
| tile click 无反应 | 点击了 tile 本身而非 media 子元素 | 只能通过 `.vcb-tile-media` 按钮坐标点击 |
| `page.locator('button').filter(text=...)` 语法错误 | Playwright API 用法错误 | 用 `locator('button').all()` 遍历 + `text_content()` 匹配 |
| 413 REQUEST ENTITY TOO LARGE | Flask 表单数据太大 | 用 JSON 发送单行数据，不发整个表单 |

## 10. 视频唯一标识

**推荐 UID：`session_id + date`**（例：`0622_4aa45c_session_00000|6月26日 19:25`）

- `session_id` = `.vcb-tile-title` 的 `textContent` 和 `title` 属性
- `date` = `.vcb-tile-meta` 中匹配 `\d月\d+日` 的文本
- 组合后全局唯一（同一 session 同一日期不会有重复）
