# CODING STANDARDS — codec-hmd

> 本项目编码规范章程。所有 PR / commit 都要符合。修改本文件需要先改 wcs-manifest.yaml 的 update_trigger。

## 1. 文件命名

| 类型 | 规则 | 例 |
|------|------|-----|
| 源代码（JS） | kebab-case 或 short_name | `hmd-decode.js`, `hmd2mp4.js` |
| HTML | kebab-case | `hmd-preview.html`, `side-by-side.html` |
| 文档 | kebab-case | `dev-plan.md`, `error-book.md` |
| 测试 | `verify_<scope>.{js,py}` | `verify_hmd_packets.js` |

## 2. JavaScript 风格

### 2.1 模块系统
- Node CLI 用 **CommonJS** (`require` / `module.exports`)
- 浏览器用 **ES module** (`<script type="module">` / `import` / `export`)
- 同一份源码不写两份：导出两套 entry（`hmd-decode.js` CJS, `hmd-decode.esm.js` ESM），逻辑共用

### 2.2 严格模式
- 所有 JS 文件顶部 `"use strict";`
- 优先 `const`，避免 `var`
- 函数式风格：避免修改入参

### 2.3 异步
- I/O 用 `async/await`，不用 `.then()` 链
- 大文件解析必须分批 + 进度回调（`onProgress`）

### 2.4 错误处理
- 解析失败抛 Error 并附 `cause` 链
- 不静默吞错（`catch {}` 禁止），至少 `console.warn` + 记入 stats

### 2.5 注释
- 顶层模块注释 = 用途 + 用法 + 已知限制
- 关键算法注释解释"为什么"而不是"做了什么"
- 危险操作（位运算、字节序）必须加注释

## 3. 字节序与编码

- 多字节整数统一用 **`DataView` + u32 LE**，禁止用 `buf[i] | buf[i+1] << 8` 这种隐式转换
- 字符串写入显式 `utf8` 编码
- HEVC Annex-B start code = `00 00 00 01`；AVCC 长度前缀 = u32 BE

## 4. 测试

- 每个 verify 脚本 **0 退出码 = 通过**；非 0 = 失败
- verify 脚本开头 `#!/usr/bin/env node` 或 `#!/usr/bin/env python3`
- 中文 console 输出 GBK 兼容：`process.stdout.write(Buffer.from('...', 'utf8'))` 或 `sys.stdout.reconfigure(encoding='utf-8')`
- 单元测试用 `node:test` 或自写 assertion 库都行；禁止引入新依赖

## 5. 提交规范

| 类型 | 触发 | 例 |
|------|------|-----|
| `feat` | 新能力 | `feat: HMD 解析支持 3 字节零判别符` |
| `fix` | bug 修复 | `fix: 修正包边界检测丢 99% 数据` |
| `refactor` | 重构无功能变化 | `refactor: 拆 findPackets 为两遍扫` |
| `docs` | 文档 | `docs: 新增 wcs-manifest 与基线` |
| `test` | 测试 | `test: 新增 verify_hmd_packets.js` |

格式：`<type>: <subject>`（subject 中文 50 字内）

## 6. 严禁

- ❌ 引入新 npm/pip 依赖（除非 prompt 明确要）
- ❌ 改 API 不更新 verify 脚本
- ❌ 删测试断言让它"通过"
- ❌ commit 不通过的代码
- ❌ 写两份相同逻辑（DRY 原则）

## 7. Python 风格（重构后 video-sort-package 共用）

- PEP 8，4 空格缩进
- 类型提示必填（函数签名）
- 错误用自定义异常类，不直接 `raise Exception`
- CSV 读写用标准库 `csv`，数据库用 `sqlite3` 标准库
- 路径拼接用 `os.path.join`，禁止字符串拼接
- HTTP 端点统一 `/api/<resource>/<action?>` 风格
