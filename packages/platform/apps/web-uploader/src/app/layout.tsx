import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'FrameForge Uploader',
  description: '视频录入员 SOP 工具',
}

const BUILD = `${new Date().toISOString().slice(0, 10)}-phase0-skeleton`

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <head>
        <meta name="build" content={BUILD} />
      </head>
      <body className="bg-slate-50 text-slate-900 antialiased">{children}</body>
    </html>
  )
}