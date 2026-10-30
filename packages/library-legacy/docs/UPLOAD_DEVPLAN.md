# Video Sort 项目 - 上传下载功能开发计划

## Context

需要为 video-sort 项目添加上传功能，集成 vendor-upload-pkg 项目，实现：
- 一键上传本地视频到 publish.example.com/vendors
- 根据 CSV 字段生成上传命令
- 显示上传进度和结果
- 支持断点续传（失败后重跑同命令即可）

## 上传命令格式

```bash
python D:\sw\offical\vendor-upload-pkg\upload.py \
  --cookie-file D:\sw\offical\vendor-upload-pkg\cookie.txt \
  --file "<视频路径>" \
  --country CN \
  --region Shanghai \
  --recorder "lingxu zhou" \
  --category industrial_manufacturing \
  --subcategory mfg_other \
  --label "<work_content_en>" \
  --notes "<extra_description>"
```

## 实现方案

### 1. 新增 API

**POST /api/upload-batch**
- 输入：选中的行索引列表（或空表示全部本地视频）
- 输出：生成的 cmd 脚本内容，供前端下载

**POST /api/save-upload-log**
- 上传完成后，保存上传结果到 CSV（status, videoId, error）

### 2. 前端新增 UI

**工具栏按钮**：
- "上传选中" - 上传选中的视频
- "上传全部本地" - 上传所有 location_status=local 的视频

**上传结果弹窗**：
- 显示生成的命令
- "复制命令" 按钮
- "打开终端运行" 按钮（下载 .cmd 文件或直接打开 cmd）

**上传结果记录**：
- 表格新增 "上传状态" 列
- 上传成功/失败/已上传 显示不同颜色

### 3. 字段映射

| CSV 字段 | 上传参数 |
|---------|---------|
| path | --file |
| work_content_en | --label |
| extra_description | --notes |
| location_status=local | 待上传 |
| uploaded | 已上传标记（从前端状态更新）|

**固定参数（从 .env 读取）**：
- --country = CN
- --region = Shanghai
- --recorder = lingxu zhou
- --category = industrial_manufacturing
- --subcategory = mfg_other

### 4. 断点续传实现

- 上传脚本已有服务端 dedup，重跑自动跳过已成功的
- 前端只生成命令，cmd 窗口显示实时输出
- 用户可手动重跑命令补传失败的

### 5. 关键文件改动

| 文件 | 改动 |
|------|------|
| `app.py` | 新增 /api/upload-batch, /api/save-upload-log 接口 |
| `index.html` | 新增上传按钮、结果弹窗、上传状态列 |
| `config.json` | 新增 upload_status 字段配置 |

### 6. 上传流程

1. 用户点击 "上传选中" 或 "上传全部本地"
2. 前端发送选中行索引到后端
3. 后端生成上传命令脚本
4. 前端显示脚本内容，提供下载/复制按钮
5. 用户下载 .cmd 文件双击运行，或复制命令到现有终端
6. 上传结果自动写入源目录的 upload-log-*.csv

## 验证步骤

1. 启动应用：`python app.py`
2. 选择几个本地视频，点击 "上传选中"
3. 下载生成的 .cmd 文件
4. 双击运行，验证上传输出
5. 失败的视频重跑同命令，验证断点续传