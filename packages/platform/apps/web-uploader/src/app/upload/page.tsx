'use client'
// /upload — v2 上传主对话框（占位）
// 事实层：docs/v2-forms-spec.md 5. ff_video_uploads
// 前端调试参考：docs/前端调试参考/上传页面0714.txt
// 表已落库：ff.ff_video_uploads
// 占位阶段只画 UI 骨架；下一步会：① GET 拉 scenes/operators/locations 选项
// → ② 拖完文件走 /api/uploader/video-uploads/preview（task_description 可空）
// → ③ 点「上传到服务器」走 /api/uploader/video-uploads（zod 强校验 task_description）
import Link from 'next/link'

const SOURCES = ['HMD 分段', 'MCAP + 元数据', 'PICO/OAK mcap', 'Fisheye MP4'] as const
const CAPTURE_MODES = ['双目', '三目', '单目'] as const

export default function UploadPage() {
  return (
    <main className="mx-auto max-w-4xl p-4">
      {/* 头部 */}
      <header className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">📤 上传视频（v2）</h1>
          <p className="text-sm text-slate-500">
            数据源：<code className="font-mono">ff.ff_video_uploads</code> · 字段定义见{' '}
            <span className="text-blue-600 underline" title="docs/v2-forms-spec.md §5">
              docs/v2-forms-spec.md §5
            </span>
          </p>
        </div>
        <Link
          href="/"
          className="rounded border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100"
        >
          ← Uploader 首页
        </Link>
      </header>

      {/* 状态条 */}
      <div className="mb-4 rounded border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
        🟩 <strong>占位阶段</strong> — UI 骨架就位；表单字段、scene/operator/location 选择器、上传走 COS 尚未接。
        下一步会：① GET /api/uploader/options?kind=scenes|operators|locations → ② 拖文件触发 preview（不写 task_description）
        → ③ 点「上传到服务器」走 /api/uploader/video-uploads 强校验 task_description。
      </div>

      {/* 接入模式 + 来源 */}
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <span className="text-xs font-semibold tracking-wider text-slate-500 uppercase">接入模式</span>
            <span className="text-[11px] text-slate-400">必填</span>
          </div>
          <div className="mb-3 inline-flex items-center gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm font-medium text-slate-700">
            双目
            <span className="text-[11px] font-normal text-slate-400">· set by project</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase">来源</span>
            <div className="inline-flex overflow-hidden rounded-md border border-slate-300">
              {SOURCES.map((s, i) => (
                <button
                  key={s}
                  type="button"
                  className={`border-r border-slate-300 px-3 py-1 text-xs font-medium transition-colors last:border-r-0 ${
                    i === 0
                      ? 'bg-emerald-600 text-white'
                      : 'bg-white text-slate-700 hover:bg-slate-50'
                  }`}
                  disabled
                  title="占位：表单提交尚未接"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
          <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-[11px] text-amber-900">
            <div className="mb-1 font-semibold">小提示</div>
            <ul className="ml-3 list-disc space-y-0.5">
              <li>HMD 分段：浏览器转成 MCAP（OPFS 流式）。</li>
              <li>MCAP + session.json：多个分段按文件名合并后上传。</li>
              <li>上传完后到「上传记录」挑要保留的片段。</li>
            </ul>
          </div>
        </div>

        {/* 预览 */}
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <span className="text-xs font-semibold tracking-wider text-slate-500 uppercase">预览</span>
            <span className="text-[11px] text-slate-400">拖入 = 先暂存到本地</span>
          </div>
          <div className="flex min-h-[140px] flex-col items-center justify-center rounded-lg border-2 border-dashed border-emerald-200 bg-white px-4 py-6 text-center">
            <div className="text-sm font-semibold text-emerald-800">把文件夹拖到这里预览</div>
            <div className="mt-1 text-[11px] text-slate-500">一个文件夹，里面是 .hmd 分段 + metadata.json。</div>
          </div>
          <button
            type="button"
            className="mt-2 w-full rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
            disabled
            title="占位：表单提交尚未接"
          >
            选择 双目 来预览
          </button>
        </div>
      </section>

      {/* 任务属性 */}
      <section className="mt-4 rounded-lg border border-slate-200 bg-white p-3">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-semibold tracking-wider text-slate-500 uppercase">任务属性</span>
          <span className="text-[11px] font-medium text-amber-600" title="Location, Operator">
            ⚠ 还有 2 项必填
          </span>
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {/* 地点 */}
          <div className="rounded-md border border-slate-200 bg-white p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
                地点 <span className="text-red-500">*</span>
              </span>
              <Link
                href="/upload/location"
                className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
              >
                <span aria-hidden>+</span> 新建地点
              </Link>
            </div>
            <div className="relative mb-2">
              <input
                placeholder="搜索你的地点…"
                className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 pl-8 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
                disabled
              />
            </div>
            <div className="px-1 py-2 text-xs text-slate-400">暂无已保存的地点 —— 新建一个。</div>
          </div>

          {/* 操作员 */}
          <div className="rounded-md border border-slate-200 bg-white p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
                操作员 <span className="text-red-500">*</span>
              </span>
              <Link
                href="/upload/operator"
                className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
              >
                <span aria-hidden>+</span> 新建操作员
              </Link>
            </div>
            <div className="relative mb-2">
              <input
                placeholder="搜索你的操作员…"
                className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 pl-8 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
                disabled
              />
            </div>
            <div className="px-1 py-2 text-xs text-slate-400">暂无已保存的操作员 —— 新建一个。</div>
          </div>
        </div>

        {/* 任务描述 */}
        <label className="mt-3 flex flex-col gap-1">
          <span className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
            任务描述 <span className="text-red-500">*</span>
          </span>
          <textarea
            rows={3}
            maxLength={500}
            placeholder="任务描述"
            className="w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-blue-500 focus:ring-1 focus:ring-blue-500 focus:outline-none"
            disabled
          />
        </label>

        {/* 上传按钮 + 申请新 scene 入口 */}
        <div className="mt-3 border-t border-slate-100 pt-3">
          <button
            type="button"
            disabled
            title="请先在预览框里拖入一个文件"
            className="w-full rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            上传到服务器（请先拖入文件）
          </button>
          <div className="mt-1 text-center text-[11px] text-slate-400">
            把文件拖到上方预览框里就能上传了。
          </div>

          {/* 场景不在白名单时 — 申请新 scene 入口 */}
          <div className="mt-3 rounded-md border border-dashed border-amber-300 bg-amber-50 px-3 py-2 text-[11px] text-amber-900">
            想要的 scene 不在白名单？ →{' '}
            <Link href="/upload/scene-apply" className="font-semibold text-blue-700 underline">
              申请新 scene
            </Link>{' '}
            （dr 未开通时走 draft → submitted_to_dr 流程）
          </div>
        </div>
      </section>

      {/* 字段速查 */}
      <details className="mt-4 rounded border border-slate-200 bg-white p-3 text-xs text-slate-600">
        <summary className="cursor-pointer font-semibold text-slate-700">
          字段速查（ff_video_uploads）
        </summary>
        <div className="mt-2 grid grid-cols-1 gap-1 md:grid-cols-2">
          <div>
            <strong>B 类（zod min(1) on 提交）：</strong>source_format / capture_mode / project_code /
            scene_id / operator_id / location_id / <strong>task_description</strong>
          </div>
          <div>
            <strong>N 类（非业务必填）：</strong>notes / recorded_at / duration_seconds /
            score_composite / uploaded_at / file_size_bytes / fps / frame_count
          </div>
          <div>
            <strong>A 类（系统必填）：</strong>path / business_key / uploaded / storage_provider /
            is_active / version / created_at / updated_at
          </div>
          <div>
            <strong>CHECK：</strong>
            <code className="ml-1 font-mono">business_key = path</code>（强制一致）
          </div>
        </div>
      </details>
    </main>
  )
}
