import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'FrameForge Admin',
  description: 'FrameForge 管理员后台',
}

const BUILD = `${new Date().toISOString().slice(0, 10)}-phase0-skeleton`

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Phase 1 用户申请 Clerk keys 后再加回 <ClerkProvider>
  return (
    <html lang="zh-CN">
      <head>
        <meta name="build" content={BUILD} />
      </head>
      <body className="bg-slate-100 text-slate-900 antialiased">{children}</body>
    </html>
  )
}