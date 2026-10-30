'use client'
// /step1-scan — Step 1：选设备类型 + 扫描（plan2 §2.1）
// 工作流（手机/电脑通用）：
//   1. 4 设备卡单选（DjiGoPro / HeadMountedUmi / GoproSessionMcap / Generic AVIRecording）
//   2. 「选择文件夹」按钮 → <input type="file" webkitdirectory> 触发（手机/Android Chrome/iOS Safari 13.4+ 全支持）
//   3. JS 遍历 FileList，按 webkitRelativePath 建虚拟目录树，按设备 pattern 找候选目录
//   4. 用户勾选 1+ 候选 → 「下一步」→ 写入 localStorage + 跳 /step2-preview
//
// 浏览器限制说明：
//   - webkitdirectory：拿不到全文件路径（沙箱隔离），但能拿到 webkitRelativePath（如 "DCIM/100GOPRO/GOPR0001.MP4"）
//   - File System Access API（showDirectoryPicker）：仅 Chrome/Edge 桌面端，不支持手机
//   - 真传文件得用 File 对象（FileReader / arrayBuffer），所以 step3 上传时再读
//
// 事实层：docs/v2-forms-spec.md §5.3 设备代码 = packages/shared/src/constants.ts DEVICE_TYPE_CODES
import Link from 'next/link'
import { useCallback, useMemo, useRef, useState } from 'react'
import { DEVICE_TYPE_CODES } from '@ff/shared/constants'

// ============== 4 设备 pattern 配置 ==============
type DeviceCode =
  | 'dji-gopro-dcim'
  | 'head-mounted-hmd'
  | 'gopro-session-mcap'
  | 'generic-avi-recording'

interface DeviceConfig {
  code: DeviceCode
  label: string
  emoji: string
  desc: string
  /** 匹配相对目录前缀（"" 表示根目录） */
  matchDir: string
  /** 该目录下需包含的文件扩展名（候选目录至少含 1 个） */
  matchExts: string[]
  /** 多 part 模式（如 Generic AVI 多 AVI 合并） */
  multiPart?: boolean
}

const DEVICES: DeviceConfig[] = [
  {
    code: 'dji-gopro-dcim',
    label: 'DJI / GoPro',
    emoji: '🎥',
    desc: 'DCIM/ 下单 .mp4（部分相机嵌套 DCIM/100GOPRO/）',
    matchDir: 'DCIM',
    matchExts: ['.mp4'],
  },
  {
    code: 'head-mounted-hmd',
    label: 'Head Mounted HMD',
    emoji: '🥽',
    desc: 'hmd/session_*/ 下 .hmd + 同名 .json',
    matchDir: 'hmd',
    matchExts: ['.hmd'],
  },
  {
    code: 'gopro-session-mcap',
    label: 'GoPro Session MCAP',
    emoji: '📡',
    desc: 'data/session_*/ 下 .mcap + 同名 .json',
    matchDir: 'data',
    matchExts: ['.mcap'],
  },
  {
    code: 'generic-avi-recording',
    label: 'Generic AVI Recording',
    emoji: '👓',
    desc: 'recordings/<日期>_<时间戳>/ 下多 .avi',
    matchDir: 'recordings',
    matchExts: ['.avi'],
    multiPart: true,
  },
]

// ============== 扫描结果类型 ==============
interface CandidateDir {
  /** 相对路径（如 "DCIM/100GOPRO" 或 "hmd/session_2025_07_15_14_30"） */
  relPath: string
  files: Array<{ name: string; size: number; ext: string; file: File }>
  totalSize: number
}

// ============== 工具函数 ==============
function getExt(name: string): string {
  const i = name.lastIndexOf('.')
  return i < 0 ? '' : name.slice(i).toLowerCase()
}

function splitPath(relPath: string): string[] {
  return relPath.split('/').filter(Boolean)
}

/**
 * 扫 FileList（webkitdirectory 拿到的），按 device config 找候选目录
 * 候选 = 以 matchDir 开头、叶子目录（该目录下有 matchExts 文件）
 */
function findCandidates(files: File[], device: DeviceConfig): CandidateDir[] {
  // 1. 把 files 按目录分组（dir path → files[]）
  const dirMap = new Map<string, File[]>()
  for (const f of files) {
    const rel = f.webkitRelativePath || f.name
    const parts = splitPath(rel)
    if (parts.length < 2) continue // 跳过根目录顶层文件
    const dir = parts.slice(0, -1).join('/')
    if (!dirMap.has(dir)) dirMap.set(dir, [])
    dirMap.get(dir)!.push(f)
  }

  // 2. 找以 matchDir 开头的目录
  const matchDirLower = device.matchDir.toLowerCase()
  const candidates: CandidateDir[] = []
  for (const [dir, dirFiles] of dirMap) {
    const dirLower = dir.toLowerCase()
    if (!dirLower.startsWith(matchDirLower + '/') && dirLower !== matchDirLower) continue
    // 该目录至少含 1 个 matchExts 文件
    const matched = dirFiles
      .filter((f) => device.matchExts.includes(getExt(f.name)))
      .map((f) => ({
        name: f.name,
        size: f.size,
        ext: getExt(f.name),
        file: f,
      }))
    if (matched.length === 0) continue

    // 叶子目录判定：如果该目录下所有文件都和该目录的父目录（matchDir）下的其他文件混在一起，
    // 仍算 1 个候选。对 Generic AVI recordings/<date>_<ts>/ 这种嵌套结构，
    // 每个 <date>_<ts> 是 1 个候选。
    candidates.push({
      relPath: dir,
      files: matched,
      totalSize: matched.reduce((s, f) => s + f.size, 0),
    })
  }

  // 按 relPath 排序
  candidates.sort((a, b) => a.relPath.localeCompare(b.relPath))
  return candidates
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
}

// ============== 主组件 ==============
export default function Step1ScanPage() {
  const [deviceCode, setDeviceCode] = useState<DeviceCode>('dji-gopro-dcim')
  const [files, setFiles] = useState<File[]>([])
  const [rootName, setRootName] = useState<string>('')
  const [scanning, setScanning] = useState(false)
  const [scanErr, setScanErr] = useState<string | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [picking, setPicking] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const device = useMemo(() => DEVICES.find((d) => d.code === deviceCode)!, [deviceCode])
  const candidates = useMemo(() => findCandidates(files, device), [files, device])

  // 切换设备时清空选择（候选集变了）
  const onPickDevice = (code: DeviceCode) => {
    setDeviceCode(code)
    setSelected(new Set())
  }

  const onChooseFolder = useCallback(() => {
    setPicking(true)
    setScanErr(null)
    fileInputRef.current?.click()
  }, [])

  const onFilesChosen = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setPicking(false)
    setScanning(true)
    setScanErr(null)
    setSelected(new Set())
    // 用 setTimeout 让 UI 先转到「扫描中」再同步算（大目录）
    setTimeout(() => {
      try {
        const fl = e.target.files
        if (!fl || fl.length === 0) {
          setScanning(false)
          return
        }
        const arr = Array.from(fl)
        setFiles(arr)
        // rootName = 第一个文件 path 的第一段
        const first = arr[0]?.webkitRelativePath ?? arr[0]?.name ?? ''
        setRootName(first.split('/')[0] ?? '')
      } catch (err) {
        setScanErr((err as Error).message)
      } finally {
        setScanning(false)
      }
    }, 0)
  }, [])

  const onReset = () => {
    setFiles([])
    setRootName('')
    setSelected(new Set())
    setScanErr(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const toggleCandidate = (relPath: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(relPath)) next.delete(relPath)
      else next.add(relPath)
      return next
    })
  }

  const onNext = () => {
    if (selected.size === 0) return
    // 暂存到 localStorage（key：ff.step1），step2 / step3 读
    const payload = {
      deviceCode,
      deviceLabel: device.label,
      deviceEmoji: device.emoji,
      rootName,
      // 存 relPath 和对应文件（File 不能 JSON 化，所以只存 relPath，
      // 真实文件在 files[] 里按顺序对得）
      selectedRelPaths: Array.from(selected),
      fileNamesByPath: candidates
        .filter((c) => selected.has(c.relPath))
        .map((c) => ({
          relPath: c.relPath,
          names: c.files.map((f) => f.name),
          totalSize: c.totalSize,
        })),
      scannedAt: new Date().toISOString(),
    }
    try {
      localStorage.setItem('ff.step1', JSON.stringify(payload))
      // File 对象也暂存到 sessionStorage 的索引里（key=fileIdx）；实际 File 仍保留在内存
      // step2 / step3 重新触发 input 不现实，所以只传 metadata，文件传时再让用户重选（或 OPFS 暂存）
      // 简化：先 metadata，文件保留在内存（react state）；跨页签会丢
      // 实际生产方案：上传时让用户重选同一文件夹（保存 relPath，跨页可对比）
      window.location.href = '/step2-preview'
    } catch (err) {
      setScanErr(`写入 localStorage 失败：${(err as Error).message}`)
    }
  }

  return (
    <main className="mx-auto max-w-2xl p-4">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Step 1 · 选设备 + 扫描</h1>
        <Link href="/" className="text-sm text-slate-500 hover:text-slate-900">
          ← 返回首页
        </Link>
      </div>

      <p className="mb-4 text-sm text-slate-600">
        先选设备类型 → 在弹窗里挑 TF 卡/手机存储的<strong>根目录</strong> → 浏览器自动扫视频目录 →
        勾选候选 → 下一步。文件本体留在浏览器内存，不上传服务器（直到 Step 3 确认）。
      </p>

      {/* 设备选择 */}
      <section className="mb-4 rounded border border-slate-200 bg-white p-3">
        <h2 className="mb-2 text-sm font-semibold text-slate-700">① 选设备类型</h2>
        <div className="grid grid-cols-2 gap-2">
          {DEVICES.map((d) => {
            const active = d.code === deviceCode
            return (
              <button
                key={d.code}
                type="button"
                onClick={() => onPickDevice(d.code)}
                className={`rounded border p-3 text-left transition ${
                  active
                    ? 'border-emerald-500 bg-emerald-50'
                    : 'border-slate-200 bg-white hover:border-slate-300'
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-lg">{d.emoji}</span>
                  <span className="text-sm font-medium text-slate-800">{d.label}</span>
                  {active && <span className="ml-auto text-xs text-emerald-600">✓</span>}
                </div>
                <div className="mt-1 text-[11px] text-slate-500">{d.desc}</div>
              </button>
            )
          })}
        </div>
      </section>

      {/* 文件夹选择 */}
      <section className="mb-4 rounded border border-slate-200 bg-white p-3">
        <h2 className="mb-2 text-sm font-semibold text-slate-700">② 选文件夹（手机/电脑通用）</h2>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <button
            type="button"
            onClick={onChooseFolder}
            disabled={picking || scanning}
            className="rounded bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {picking ? '选择中…' : '📂 选择文件夹'}
          </button>
          {files.length > 0 && (
            <>
              <span className="text-xs text-slate-600">
                根：<code className="font-mono">{rootName}</code> · 共 {files.length} 个文件
              </span>
              <button
                onClick={onReset}
                className="rounded border border-slate-300 px-2 py-0.5 text-[11px] text-slate-700 hover:bg-slate-50"
              >
                重新选择
              </button>
            </>
          )}
        </div>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={onFilesChosen}
          {...({ webkitdirectory: '', directory: '' } as Record<string, string>)}
        />
        <p className="mt-2 text-[11px] text-slate-400">
          弹窗里挑「TF 卡根目录」或「内部存储根目录」（手机）或磁盘根目录（电脑）。挑完会自动列候选。
        </p>
        {scanErr && (
          <div className="mt-2 rounded border border-red-300 bg-red-50 px-2 py-1 text-xs text-red-800">
            ❌ {scanErr}
          </div>
        )}
      </section>

      {/* 候选列表 */}
      {scanning && (
        <div className="rounded border border-slate-200 bg-white p-4 text-center text-sm text-slate-500">
          扫描中…
        </div>
      )}

      {!scanning && files.length > 0 && (
        <section className="mb-4 rounded border border-slate-200 bg-white p-3">
          <h2 className="mb-2 text-sm font-semibold text-slate-700">
            ③ 候选目录（设备：{device.emoji} {device.label}，pattern：{device.matchDir}/…）
          </h2>
          {candidates.length === 0 ? (
            <div className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              没找到 <code className="font-mono">{device.matchDir}/</code> 下的{' '}
              {device.matchExts.join(' / ')} 文件。可能挑错设备或文件夹了。
            </div>
          ) : (
            <>
              <p className="mb-2 text-xs text-slate-500">
                找到 <strong>{candidates.length}</strong> 个候选 · 已选{' '}
                <strong>{selected.size}</strong> 个
              </p>
              <ul className="space-y-1">
                {candidates.map((c) => {
                  const isSel = selected.has(c.relPath)
                  return (
                    <li key={c.relPath}>
                      <label
                        className={`flex cursor-pointer items-start gap-2 rounded border px-2 py-1.5 text-xs transition ${
                          isSel
                            ? 'border-emerald-400 bg-emerald-50'
                            : 'border-slate-200 bg-white hover:bg-slate-50'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={isSel}
                          onChange={() => toggleCandidate(c.relPath)}
                          className="mt-0.5"
                        />
                        <div className="min-w-0 flex-1">
                          <div className="truncate font-mono font-semibold text-slate-800">
                            {c.relPath}
                          </div>
                          <div className="text-[10px] text-slate-500">
                            {c.files.length} 个文件 · {formatSize(c.totalSize)}
                            {device.multiPart && c.files.length > 1 && ' · 多 part'}
                          </div>
                        </div>
                      </label>
                    </li>
                  )
                })}
              </ul>
            </>
          )}
        </section>
      )}

      {/* 下一步 */}
      {files.length > 0 && (
        <div className="flex items-center justify-end gap-2">
          <Link
            href="/"
            className="rounded border border-slate-300 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50"
          >
            取消
          </Link>
          <button
            type="button"
            onClick={onNext}
            disabled={selected.size === 0}
            className="rounded bg-emerald-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 disabled:bg-slate-300"
          >
            下一步 → /step2-preview ({selected.size})
          </button>
        </div>
      )}

      {/* 调试 / 知识块 */}
      <details className="mt-6 rounded border border-slate-200 bg-white p-3 text-[11px] text-slate-600">
        <summary className="cursor-pointer font-semibold text-slate-700">技术说明</summary>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>
            <strong>浏览器沙箱</strong>：网页不能读任意本地路径，只能读用户主动挑的文件夹（webkitdirectory）或
            用户授权过的子文件（File System Access API）
          </li>
          <li>
            <strong>跨页签</strong>：File 对象在 React state，刷新或换页会丢。生产方案 = 上传时让用户再选同一根目录（localStorage
            存「上次目录指纹 + 选中文件相对路径」做对比）
          </li>
          <li>
            <strong>4 设备 pattern</strong>：对齐{' '}
            <code className="font-mono">@ff/shared/constants DEVICE_TYPE_CODES</code> + v2-forms-spec §5
          </li>
          <li>
            <strong>大目录性能</strong>：浏览器读 N 个 File 对象只走 metadata（webkitRelativePath + size + name），
            不读文件内容；千级文件 1-2 秒
          </li>
        </ul>
      </details>
    </main>
  )
}

// 防 unused 警告
void DEVICE_TYPE_CODES
