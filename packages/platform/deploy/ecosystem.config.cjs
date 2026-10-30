// pm2 ecosystem 配置 — 3 进程（web-uploader / web-admin / worker）
// 服务器路径：/www/wwwroot/projects/ff/deploy/ecosystem.config.cjs
// 启动：pm2 start deploy/ecosystem.config.cjs
// 状态：pm2 list / logs

module.exports = {
  apps: [
    {
      name: 'web-uploader',
      cwd: '/www/wwwroot/projects/ff/apps/web-uploader',
      script: 'node_modules/next/dist/bin/next',
      args: 'start -p 3001',
      env: { NODE_ENV: 'production' },
      max_memory_restart: '512M',
      out_file: '/www/wwwroot/projects/ff/logs/web-uploader.out.log',
      error_file: '/www/wwwroot/projects/ff/logs/web-uploader.err.log',
      merge_logs: true,
    },
    {
      name: 'web-admin',
      cwd: '/www/wwwroot/projects/ff/apps/web-admin',
      script: 'node_modules/next/dist/bin/next',
      args: 'start -p 3002',
      env: { NODE_ENV: 'production' },
      max_memory_restart: '512M',
      out_file: '/www/wwwroot/projects/ff/logs/web-admin.out.log',
      error_file: '/www/wwwroot/projects/ff/logs/web-admin.err.log',
      merge_logs: true,
    },
    {
      name: 'worker',
      cwd: '/www/wwwroot/projects/ff/apps/worker',
      script: 'dist/index.js',
      env: { NODE_ENV: 'production' },
      max_memory_restart: '512M',
      out_file: '/www/wwwroot/projects/ff/logs/worker.out.log',
      error_file: '/www/wwwroot/projects/ff/logs/worker.err.log',
      merge_logs: true,
    },
  ],
}
