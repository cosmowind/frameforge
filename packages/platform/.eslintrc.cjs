/* eslint-env node */
// FrameForge plan2 ESLint config — 防 E6/E15/E14
// 跨 web-uploader/web-admin/worker/packages 共享规则

module.exports = {
  root: true,
  parser: '@typescript-eslint/parser',
  parserOptions: { ecmaVersion: 'latest', sourceType: 'module' },
  ignorePatterns: [
    'dist',
    'build',
    'node_modules',
    'runtime',
    '.debug',
    '*.min.js',
    '.next',
    'out',
    '.eslintrc.cjs',
    'postcss.config.cjs',
    'next.config.ts',
    'drizzle.config.ts',
    'apps/**/migrations/**',
    'apps/**/dist/**',
  ],
  plugins: ['@typescript-eslint'],
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'prettier',
  ],
  rules: {
    '@typescript-eslint/no-floating-promises': 'error',
    '@typescript-eslint/no-misused-promises': 'error',
    '@typescript-eslint/no-unused-vars': [
      'warn',
      { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
    ],
    '@typescript-eslint/no-explicit-any': 'warn',
    'no-template-curly-in-string': 'off',
  },
  overrides: [
    {
      files: ['*.cjs'],
      env: { node: true, browser: false },
      rules: { '@typescript-eslint/no-var-requires': 'off' },
    },
    {
      files: ['apps/web-uploader/**/*.{ts,tsx}', 'apps/web-admin/**/*.{ts,tsx}'],
      extends: ['next/core-web-vitals'],
    },
  ],
}
