import type { NextConfig } from 'next'

const config: NextConfig = {
  transpilePackages: ['@ff/shared', '@ff/db-schema'],
  experimental: {
    serverActions: { bodySizeLimit: '2mb' },
  },
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: false },
}

export default config