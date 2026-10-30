// Uploader SPA 入口 — Step 1 占位
// 3 步流程：Step1 选设备+扫 / Step2 预览 / Step3 填参+上传
// v2 上传：/upload 主对话框（v2-forms-spec §5 ff_video_uploads）+ 3 个 quick modal
import Link from 'next/link'
import { DEVICE_TYPE_CODES } from '@ff/shared/constants'

const STEPS = [
  { code: 'login', href: '/login', title: '👤 录制员登录', desc: '关联 Clerk / 选 recorder（dev 模式）' },
  { code: 'devices', href: '/devices', title: '📷 设备 / 环境登记', desc: '选 4 种设备 + env + 元信息 → 写 videos 行' },
  { code: 'tasks', href: '/tasks', title: '📋 任务登记', desc: '为已登记的视频选 task_id（工序/工具/难度）' },
  {
    code: 'upload',
    href: '/upload',
    title: '📤 上传视频 (v2)',
    desc: 'v2 上传对话框 · ff.ff_video_uploads · 含 3 个 quick modal（operator/location/scene-apply）',
    highlight: true,
  },
  { code: 'step1', href: '/step1-scan', title: 'Step 1 · 选设备 + 扫描', desc: '选 4 种设备类型之一，扫描 TF 卡根目录' },
  { code: 'step2', href: '/step2-preview', title: 'Step 2 · 预览', desc: '从扫描结果选一个 session 预览视频' },
  { code: 'step3', href: '/step3-fill-upload', title: 'Step 3 · 填参 + 上传', desc: '选录制员/工序/环境 + 任务描述，上传 COS' },
  { code: 'library', href: '/library', title: '我的视频库', desc: '查看已上传的视频、修改任务说明' },
  { code: 'fill', href: '/library/fill', title: '⚠️ 视频信息补全', desc: '为未填全的视频补 recorder / task / env / 上传标记', highlight: true },
]

export default function Home() {
  return (
    <main className="mx-auto max-w-3xl p-4">
      <h1 className="text-3xl font-bold tracking-tight">FrameForge Uploader</h1>
      <p className="text-slate-600 mb-6">
        视频录入员 SOP 工具 · plan2 Phase 0 骨架 ·{' '}
        <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs text-emerald-800">
          v2 上传对话框 + 3 quick modal 占位已就绪
        </span>
      </p>
      <section className="grid gap-3">
        {STEPS.map((step) => (
          <Link
            key={step.code}
            href={step.href}
            className={`block rounded border p-4 hover:border-slate-300 ${
              'highlight' in step && step.highlight
                ? 'border-amber-300 bg-amber-50'
                : 'border-slate-200 bg-white'
            }`}
          >
            <div className="font-medium">{step.title}</div>
            <div className="text-sm text-slate-500">{step.desc}</div>
          </Link>
        ))}
      </section>
      <section className="mt-8">
        <h2 className="text-lg font-semibold mb-2">已注册设备（4 种）</h2>
        <ul className="text-sm text-slate-600 space-y-1">
          <li>· <code className="font-mono">{DEVICE_TYPE_CODES.DJI_GOPRO_DCIM}</code> — DCIM/ 单 .mp4</li>
          <li>· <code className="font-mono">{DEVICE_TYPE_CODES.HEAD_MOUNTED_HMD}</code> — hmd/session_*/ .hmd + .json</li>
          <li>· <code className="font-mono">{DEVICE_TYPE_CODES.GOPRO_SESSION_MCAP}</code> — data/session_*/ .mcap + .json</li>
          <li>· <code className="font-mono">{DEVICE_TYPE_CODES.GENERIC_AVI_RECORDING}</code> — recordings/&lt;date&gt;_&lt;ts&gt;/ 多 .avi</li>
        </ul>
      </section>
    </main>
  )
}
