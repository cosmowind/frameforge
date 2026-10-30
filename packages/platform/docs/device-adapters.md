# Device Adapters — FrameForge (plan2)

> 4 设备 DeviceAdapter 实现 + 扩展指南。设备适配核心模块。

## 为什么重要（plan2 §5）

> ff 与"通用视频上传工具"的根本区别 —— 业务真相是 4 种异构设备。
> 客户端核心价值 = 降低设备和录制员之间的摩擦。

## 接口（@ff/shared/adapters）

```ts
export interface DeviceAdapter {
  readonly code: string  // 'dji-gopro-dcim' | ...

  // Step 1: 扫描 TF 卡根目录
  scan(rootPath: string): Promise<VideoUnit[]>

  // Step 2: 解析单个 session 的元数据
  parseMetadata(sessionPath: string): Promise<DeviceMetadata>

  // Step 2: 获取预览 handle
  // - native: 文件 URL（浏览器直接播）
  // - worker: 任务 ID（前端轮询或 SSE）
  getPreviewHandle(sessionPath: string): Promise<PreviewHandle>

  // Step 3: 准备上传文件
  // 输出最终上传的 MP4 + 设备元数据
  prepareForUpload(sessionPath: string, workDir: string): Promise<UploadFileRef>
}
```

## 4 设备规格

| code | 物理设备示例 | 根目录 | 会话组织 | 文件 | 预览引擎 | 上传准备 | 工时 | 风险 |
|------|------------|--------|---------|------|---------|---------|------|------|
| `dji-gopro-dcim` | DJI / 早期 GoPro | `DCIM/` | 单文件 | `.mp4` | native | direct | 2-3 天 | 低 |
| `head-mounted-hmd` | 头环版 | `hmd/` | `session_0000x/` | `.hmd` + `.json` | hmd-decoder | extract-hmd | 5-10 天 | **高** |
| `gopro-session-mcap` | 后期 GoPro (MCAP) | `data/` | `session_0000x/` | `.mcap` + `.json` | mcap-extract | extract-mcap | 3-5 天 | 中 |
| `generic-avi-recording` | Generic AVI | `recordings/` | `<date>_<ts>/` | `.avi` × N + `.idx` | native | concat-avi | 2-3 天 | 低 |

## A. DjiGoproDcimAdapter（最简单）

```ts
// packages/adapters/src/device/dji-gopro-dcim.ts
export const DjiGoproDcimAdapter: DeviceAdapter = {
  code: 'dji-gopro-dcim',

  async scan(rootPath) {
    // 列 DCIM/ 下所有 .mp4，按文件名排序
    const files = await fs.readdir(rootPath)
    return files.filter(f => f.endsWith('.mp4')).sort().map(name => ({
      sessionId: name.replace('.mp4', ''),
      displayName: name,
      filePaths: [path.join(rootPath, name)],
      estimatedSize: 0,
      estimatedDuration: 0,
    }))
  },

  async parseMetadata(sessionPath) {
    // fluent-ffmpeg 读时长/分辨率/GPS（worker-device-scan 调）
    return { sessionFolderName: basename(sessionPath), durationSec, resolution, codec }
  },

  async getPreviewHandle(sessionPath) {
    return { kind: 'native', fileUrl: `file://${sessionPath}` }
  },

  async prepareForUpload(sessionPath, _workDir) {
    // 直接传原 MP4，无需处理
    return { preparedPath: sessionPath, fileHash, sizeBytes }
  },
}
```

## B. HeadMountedHmdAdapter（最复杂，**待供应商确认**）

- **scan**：列 `hmd/session_*/` 下所有 `.hmd`
- **parseMetadata**：读同目录 `.json`（设备元数据：姿态 + 传感器时间戳）
- **getPreviewHandle**：HMD 不能浏览器直接播 → worker 异步转 MP4 → `kind: 'worker'` + jobId
- **prepareForUpload**：worker 端调 HMD decoder → 提取视频 + 编码 MP4

**风险与降级**：
- 主路径：调供应商 HMD decoder 工具
- 降级：只上传原 `.hmd` + `.json`，在 `ff_file_assets` 加 `original_only_upload` 标记
- 客户（COS 接收方）自己解析

## C. GoproSessionMcapAdapter

- **scan**：列 `data/session_*/` 下所有 `.mcap` + 读 metadata `.json`
- **parseMetadata**：用 `mcap` CLI 或 Foxglove tools 读 MCAP header + topic 列表
- **getPreviewHandle**：MCAP 不直接播 → worker 提取视频 topic → 转 MP4
- **prepareForUpload**：提取后编码 MP4

**MVP 降级**：如 MCAP 不含视频轨道，只上传原 `.mcap`

## D. Generic AVIRecordingAdapter（多 AVI）

- **scan**：列 `recordings/<date>_<timestamp>/` 下所有 `.avi`（按 part 编号排序）
- **parseMetadata**：读所有 AVI 时长（≤ 3min × N）合并到 session 级别
- **getPreviewHandle**：返回多个 AVI 路径 + 元数据；前端用 HTML5 `<video>` 顺序播放
- **prepareForUpload**：
  ```bash
  ffmpeg -f concat -safe 0 -i /tmp/list.txt -c copy out.mp4
  ```

**前端 UX**：预览时显示 "Part 1/N · 3 段 AVI 共 9 分钟"。

## 注册表（@ff/adapters/registry）

```ts
import { buildAdapterRegistry } from '@ff/adapters'

const REGISTRY = buildAdapterRegistry()
// Map { 'dji-gopro-dcim' => DjiGoproDcimAdapter, ... }

// 通过 code 取
const adapter = REGISTRY.get('head-mounted-hmd')
const units = await adapter.scan('/media/recorder/hmd/')
```

## 扩展新设备（5 步）

1. 在 `ff_device_types` 表 INSERT 一行（DBA 跑 migration 或 Admin 后台）
2. 实现 `XxxAdapter implements DeviceAdapter`
3. `packages/adapters/src/registry.ts` 添加一行注册
4. 前端下拉框自动出现（数据驱动，从 `ff_device_types` 读）
5. 加 e2e 测试

**核心代码不动**：扫描/预览/上传 orchestration 只调 `adapter.scan()` / `getPreviewHandle()` / `prepareForUpload()`。

## 风险与未确认

| 设备 | 关键风险 | 缓解 |
|---|---|---|
| HMD | 私有格式，需供应商 decoder | 降级：上传原 .hmd |
| MCAP | 视频轨道存在性 | 降级：上传原 .mcap |
| Generic AVI | 文件名跨 session 冲突 | 用 `<date>_<timestamp>` 前缀 |
