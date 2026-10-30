# FrameForge 参数自动填充工具

## 概述

批量填充 publish.example.com upload history 中 missing>0 的视频参数。

## 核心脚本

### 1. `batch_autofill_v2.py` — 主要参数批量填充

填充 22 个字段：operator_name, task_description, environment_description, city, state_province, country, location_address, operator_job, age_range, gender, handedness, gloves, workforce_type, role_experience, hand_size_cm, task_difficulty, operator_consent, business_type, business_name 等。

```bash
# 填充所有 missing>0 的记录
python batch_autofill_v2.py

# 只处理前 5 条测试
python batch_autofill_v2.py --limit 5

# 从第 100 条开始
python batch_autofill_v2.py --start-from 100
```

### 2. `fix_three_fields.py` — 三个下拉字段修复

修复 environment, facility_venue, scene 这三个需要点击下拉选项的字段。

```bash
# 修复所有记录
python fix_three_fields.py

# 只修复前 10 条
python fix_three_fields.py --limit 10

# 从第 50 条开始
python fix_three_fields.py --start-from 50
```

### 3. `fix_single_field.py` — 单字段修复

```bash
# 修复 environment 字段
python fix_single_field.py --field environment

# 修复 facility_venue 字段
python fix_single_field.py --field facility_venue

# 修复 scene 字段
python fix_single_field.py --field scene
```

## 前置条件

1. **启动环境**：运行 `start_helper.bat`
   - 自动启动 Chrome（CDP 9222 端口）
   - 自动启动 Flask 后端（5000 端口）
   - 自动设置筛选条件
   - 自动注入 Ctrl+B 快捷键

2. **Chrome 登录**：确保 publish.example.com 已登录

3. **Python 依赖**：playwright, flask

## 技术要点

### 下拉选项填充

environment/facility/scene 等字段是 React 受控组件，必须：
1. 用 `nativeInputValueSetter` 设置值
2. 触发 `input` 和 `change` 事件
3. **点击 `<span>` 下拉选项**才能真正选中

```javascript
// 步骤1：输入值
var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
setter.call(input, 'Industrial Manufacturing');
input.dispatchEvent(new Event('input', {bubbles:true}));

// 步骤2：点击下拉选项
document.querySelectorAll('span').forEach(function(el) {
    if (el.textContent.trim() === 'Industrial Manufacturing') {
        el.click();
    }
});
```

### 翻页定位

page 输入框在页面底部，需要：
1. `window.scrollTo(0, document.body.scrollHeight)` 滚到底部
2. 找 Go 按钮附近的 `input[type=number]`（不是 score 输入框）

### tile 精确匹配

用 session_id 后缀 + date 精确匹配，避免点错视频。

## 文件结构

```
scripts/
├── README_autofill.md          # 本文档
├── batch_autofill_v2.py        # 主要参数批量填充
├── fix_three_fields.py         # 三个下拉字段修复
├── fix_single_field.py         # 单字段修复
├── setup_filters.py            # 筛选条件设置
├── scan_all_videos.py          # 全量扫描视频
├── csv_editor.py               # CSV Web 编辑器（5001端口）
└── temp/                       # 临时测试脚本
```
