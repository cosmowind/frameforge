# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Electron desktop app for splitting MP4 videos into 5-25 second segments. Built with Electron + React + TypeScript + Vite.

## Commands

```bash
npm run dev           # Start dev mode (Vite + Electron concurrently)
npm run dev:renderer  # Vite dev server only (port 3000)
npm run dev:main      # Compile main process TS then launch Electron
npm run build         # Build renderer (Vite) then main (tsc)
npm run lint          # ESLint on .ts/.tsx
npm run format        # Prettier
npm run dist          # Build + electron-builder (Windows NSIS installer)
```

No test framework is configured. No test commands exist.

## Architecture

### Process Split

- **Main process** (`src/main/main.ts`): Electron BrowserWindow, IPC handlers, FFmpeg/FFprobe execution for video info extraction and lossless splitting (`-c copy`)
- **Renderer process** (`src/renderer/`): React UI, all business logic runs in the browser

### IPC Bridge

`src/main/preload.ts` exposes `window.electronAPI` via context bridge. Uses `ipcRenderer.invoke`/`ipcMain.handle` for request-response, `ipcRenderer.on` for progress streaming during video splitting.

### Renderer Layers

- **Components**: `SegmentationView` (main editing), `ReviewView` (audit), `VideoPlayer` (HTML5 `<video>`), `Timeline` (canvas-based with drag handles), `SegmentControls` (segment list CRUD), `RulesPanel` (reference panel)
- **Services**: `SegmentManager` (segment CRUD, sort, index maintenance), `ValidationService` (duration 5-25s, overlap, index continuity), `MetadataService` (JSON save/load/export), `VideoService` (file selection, ffprobe wrapper)
- **Store**: Single Zustand store at `store/useAppStore.ts` — all app state, actions, and undo history (50 entries max)
- **Types**: Core models in `types/index.ts` — `SegmentPoint`, `VideoSegment`, `SegmentMetadata`, `VideoInfo`

### Data Flow

User loads video → ffprobe extracts metadata → segments created on canvas timeline → metadata saved as JSON → FFmpeg splits into `{original}-{index}.mp4` in `{original}-result/` folder.

## Key Conventions

- Path alias `@` maps to `src/renderer` (configured in vite.config.ts)
- Two tsconfigs: `tsconfig.json` (renderer, ESNext modules, noEmit) and `tsconfig.main.json` (main, CommonJS, outputs to `dist/main`)
- Styling: Tailwind CSS + Ant Design components
- Prettier: single quotes, semicolons, 100 char width, 2 spaces
- npm registry configured for npmmirror.com (Chinese mirror in `.npmrc`)
- `video.js` is listed as a dependency but is not used — VideoPlayer uses native HTML5 `<video>`
