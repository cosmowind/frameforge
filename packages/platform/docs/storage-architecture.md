# Storage Architecture — FrameForge (plan2)

> 三层存储 + SCF 跨桶同步 + CDN + Puller + 夸克季度备份。存储实现时必读。

## 总览（plan2 §6）

```
录制员浏览器  ──┐
                │ Step 3 上传
                ▼
        apps/web-uploader (Next.js 15)
                │ cos-js-sdk-v5 直传（multipart + 断点续传）
                ▼
        ┌───────────────────────────────────────────┐
        │   L1: 腾讯云 COS（标准存储）             │
        │   bucket: ff-uploads-1300000000          │
        │   region: ap-shanghai                     │
        │   30 天后自动转 IA（低频）                │
        │   90 天后自动转 Archive                   │
        │   180 天后自动转 DeepArchive              │
        └────┬─────────────────────────┬───────────┘
             │                         │
    cos:ObjectCreated:Put       CDN 回源（puller cron）
             │                         │
             ▼                         ▼
    ┌────────────────────┐    ┌──────────────────────┐
    │ L1.5: 客户 COS     │    │ L2: 本地硬盘          │
    │ (合作结算平台)     │    │ D:/ff-pull          │
    │ SCF 跨桶同步        │    │ Puller 容器拉取       │
    └────────────────────┘    └──────────┬───────────┘
                                         │
                                季度手工 (rclone 10M 限速)
                                         │
                                         ▼
                            ┌──────────────────────┐
                            │ L3: 夸克网盘          │
                            │ /ff-backup           │
                            │ 异地灾备              │
                            └──────────────────────┘
```

## 流转时间线（百 TB/月量级）

| 阶段 | 动作 | 成本/月 |
|---|---|---|
| T+0 | 录制员选设备 + 扫 | 0 |
| T+0 | 选 session + 预览 | 0 |
| T+0 | 填参 + 提交 → COS STS 直传 | 0 |
| T+1s | SCF 触发 → 跨桶到客户 COS | ¥0.0001/次 |
| T+1h | 家里 Puller cron 拉取到本地硬盘 | ¥0.15/GB CDN 回源 |
| T+30d | COS 自动转 IA | -36% 存储费 |
| T+90d | COS 自动转 Archive | -72% 存储费 |
| T+180d | COS 自动转 DeepArchive | -90% 存储费 |
| 季度 | 本地硬盘 → 夸克网盘（rclone 手工触发）| ~¥0.5/GB |

## 1) L1 腾讯云 COS 上传（plan2 §6.3）

```ts
// apps/web-uploader/src/lib/cos-upload.ts
import COS from 'cos-js-sdk-v5'

// 1. 前端调后端拿 STS 临时凭证
const { sts, bucket, region, key } = await api<StsResp>('/api/uploads/sts-credentials', {
  method: 'POST',
  body: { videoRecordId, fileName, fileSize },
})

// 2. 直接 multipart 上传 COS（不经后端）
const cos = new COS({
  SecretId: sts.SecretId,
  SecretKey: sts.SecretKey,
  SecurityToken: sts.SessionToken,
})
cos.uploadFile({
  Bucket: bucket,
  Region: region,
  Key: key,
  Body: file,
  onProgress: (info) => setProgress(info.percent * 100),
})
// 3. 完成后通知后端（POST /api/uploads/complete）
```

## 2) L1 → L1.5 SCF 跨桶同步（plan2 §6.3）

```ts
// 部署在 SCF 的函数代码（不在本仓库）
import { COS } from 'cos-nodejs-sdk-v5'

export async function handler(event) {
  if (event.triggerType !== 'cos') return
  const { bucket, key } = event

  const dst = new COS({
    SecretId: process.env.CLIENT_COS_SECRET_ID,
    SecretKey: process.env.CLIENT_COS_SECRET_KEY,
  })
  await dst.copyObject({
    Bucket: process.env.CLIENT_COS_BUCKET,
    Region: process.env.CLIENT_COS_REGION,
    Key: `partner/${key.replace('videos/', '')}`,
    CopySource: `${bucket}.cos.${region}.myqcloud.com/${key}`,
  })

  // 落 ff_scf_invocations + 更新 ff_file_assets.client_cos_*
  await fetch(`${process.env.WORKER_WEBHOOK}/scf-record`, {
    method: 'POST',
    body: JSON.stringify({ key, status: 'success' }),
  })
}
```

## 3) L2 本地硬盘 Puller（plan2 §6.5）

worker-pull 定时（`0 */1 * * *`）：

```ts
// apps/worker/src/jobs/pull.ts（Phase 1 完整实现）
async processPull({ cosKey, fileHash }) {
  const localPath = path.join(PULLER_LOCAL_ROOT, fileHash)
  // 增量同步：DB 没记录本地拉取的，触发拉取
  const cmd = `rclone sync :cos:${cosKey} ${localPath} --bwlimit ${BANDWIDTH} --transfers 4`
  await exec(cmd)
  // 写 ff_puller_runs + 更新 ff_file_assets.local_*
}
```

## 4) L3 夸克网盘季度备份（plan2 §6.6）

```bash
# 季度手工执行
rclone sync /d/ff-pull quark:/ff-backup --bwlimit 10M --progress \
  --log-file=runtime/logs/quark-backup-$(date +%Y%m%d).log
```

## 5) CDN 加速 + 防盗链（plan2 §6.4）

- CDN 域名：`cdn.ff.example.com`
- URL 鉴权：Referer 白名单 + 签名 URL 5 分钟有效
- 命中率 90%+（命中 CDN 直接返回回源流量降到 13.5 TB/月）

## 12 月成本估算（plan2 §11）

| 项 | 月成本 |
|---|---|
| L1 COS 标准存储 + 低频 + 归档混合 | ~6,500 元 |
| CDN 回源流量 | ~2,000 元 |
| SCF 调用 | ~14 元 |
| L2 本地硬盘折旧 | ~133 元 |
| L3 夸克网盘 | ~4 元 |
| 后端服务器（CVM）| ~200 元 |
| **合计**| **~8,800 元/月** |

（资源包抵扣后降至 ~6,300 元/月）
