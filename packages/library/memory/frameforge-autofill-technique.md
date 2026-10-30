---
name: frameforge-autofill-technique
description: publish.example.com CDP自动化核心技术：Chrome启动参数、筛选设置、tile点击（media按钮）、modal检测、分页
metadata:
  type: reference
---

# publish.example.com CDP 自动化操作关键发现

## Chrome 启动参数（完整版）
```
--remote-debugging-port=9222 --user-data-dir=独立目录 --remote-allow-origins=http://localhost:9222 --allow-running-insecure-content --disable-web-security
```
必须用独立 `--user-data-dir` 绕过 SingletonLock，必须 `--disable-web-security` 让 HTTPS 页面能调 HTTP API。

## 筛选设置（全部用 JS evaluate）
- Capture=Stereo：`select.value='stereo' + dispatchEvent('change')`
- Excludes tags：`review_reject` / `vendor-delete` / `wipe` 三个标签 button 依次 click

## Tile 点击
点击 `.vcb-tile` div 本身无效，必须点击 `.vcb-tile-media` 子按钮区域的绝对坐标（`getBoundingClientRect` 获取中心点，用 `page.mouse.click(x,y)` 触发）。

## Modal 检测
点击后 1.2s 用 `document.querySelector('.vcb-modal-overlay')` 检测，modal 文本含 `\d+ missing` 提取缺失数。关闭用 `Escape`。

## Edit metadata 表单
- 字段用 `placeholder` 定位（不是 label）
- React 受控组件写值必须用 `Object.getOwnPropertyDescriptor(proto,'value').set.call(el,value)` + dispatchEvent('input') + dispatchEvent('change')
- Select 下拉用 label 祖先元素定位

## 分页
用 `page.locator('input[type=number]').last.fill('N')` + `page.locator('button:has-text("Go")').last.click()`，不用 URL 避免重置筛选。

## Playwright 限制
publish.example.com 的 React 表单对 Playwright 原生 API（`fill()`/`click()`）有时会报 Connection closed。全部改用 JS evaluate 注入 + mouse.click 坐标点击。
