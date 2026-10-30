# mcap2mp4left

将 MCAP 文件中的 foxglove.CompressedVideo (H.265) 轨道转换为 MP4，仅提取 camera/0，每个 session 输出一个合并后的完整 MP4。

## 依赖

```bash
pip install av
```

- **av** (PyAV) — 用于 H.265 ES 流解析与 MP4 remux
- Python 3.8+
- ffmpeg（需在 PATH 中）

## 用法

```bash
python mcap2mp4left.py <data0706_dir>
```

**示例：**
```bash
python mcap2mp4left.py ./data0706
```

## 输出

在 `<data0706_dir>` 同级目录下生成：
- `session_XXXXX_merged.mp4` — 每个 session 一个合并后的视频
- 中间临时文件写入 `C:\temp_hmd\`，处理完后自动清理

## 工作流程

1. 扫描 session 文件夹（如 `session_00030/`）
2. 读取该 session 下所有 `ego_XXXX.mcap` 文件
3. 提取每个文件中的 camera/0 数据，按时间戳全局排序
4. 合并写入单个 `_merged.mp4` 文件

## 其他脚本

| 脚本 | 说明 |
|------|------|
| `mcap_to_mp4.py` | 原版，支持 `--camera 0/1` 指定单边 |
| `merge_mp4.py` | 合并已转换的 mp4 分段，按 session 分组 |
| `batch_convert_single.ps1` | PowerShell 批处理脚本（单 camera/0）|
