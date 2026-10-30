# Video Sort

视频文件管理工具，用于扫描目录、整理视频元数据、记录上传状态并支持导出。

## 功能概览

### 视频目录扫描
- 输入本地目录路径，扫描目录下所有 `.mp4` 文件
- 自动读取已存在的 CSV 记录（`video_manager.csv`），保留历史编辑数据
- 新发现的视频自动创建空白记录，已存在的保留原数据

### 元数据管理
每条视频记录包含以下字段：

| 字段 | 说明 |
|------|------|
| path | 视频文件完整路径 |
| work_content_cn | 工作内容（中文） |
| work_content_en | 工作内容（英文） |
| category | 类别 |
| recorder | 录制者 |
| upload_feasibility | 上传可行性（高/中/低） |
| uploaded | 是否已上传（Yes/No） |
| extra_description | 额外描述 |
| score | 得分 |

### 表格操作
- **列显示控制**：点击顶部列标签 chip 可切换显示/隐藏列
- **列宽拖动调整**：拖动列头右侧边缘调整列宽
- **列顺序拖动调整**：拖动列头可重新排列列顺序
- **行预览**：点击"预览"按钮直接播放视频，预览区支持上一个/下一个导航
- **实时编辑**：表格和预览区的编辑均实时同步到内存

### 保存
- 点击"保存全部"将当前所有数据写回 `video_manager.csv`
- 支持快捷键 `Ctrl+S` 保存

### 导出 TXT
- 支持选择任意列导出
- 支持选择行（默认全部）
- 导出格式：n×m 矩阵导出 n×m 行，每行一个单元格值
- 分隔符字段当前保留（暂无功能作用）

## 技术栈

- **后端**：Python Flask
- **前端**：原生 HTML/CSS/JavaScript（无框架）
- **数据存储**：CSV（`video_manager.csv`）
- **配置存储**：JSON（`config.json`）

## 快速启动

```bash
python app.py
```

访问 http://localhost:5000

## 文件结构

```
├── app.py              # Flask 后端服务
├── video_manager.csv   # 视频数据存储
├── config.json         # 列配置（显示/顺序/宽度）
├── templates/
│   └── index.html      # 前端页面
└── docs/
    ├── README.md        # 项目说明文档（本文件）
    └── EXPORT.md        # 导出功能详解
```