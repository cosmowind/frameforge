# FrameForge

**A local-first toolkit for turning raw camera footage into a tagged, searchable, publishable library.**

Most camera-shoot tooling falls into one of two camps: heavyweight NLEs that need a
render farm, or thin uploaders that assume your footage is already organised.
FrameForge is the middle path — a set of small, composable pieces that each solve one
real problem, and a pipeline that wires them together.

```
   SD card / camera            FrameForge                      publishing target
  ┌───────────────┐      ┌──────────────────────────┐      ┌────────────────────┐
  │ DCIM/  data/  │─────▶│ ingest → decode → index  │─────▶│ delivery client    │
  │ hmd/  *.hmd   │      │ library → tag → segment  │      │ (generic adapter)  │
  └───────────────┘      └──────────────────────────┘      └────────────────────┘
```

---

## The packages

| Package | What it does | Stack |
|---|---|---|
| [`packages/codec-hmd`](packages/codec-hmd) | Parses head-mounted dual-camera recordings (`.hmd`), converts to MP4, plays stereo streams **in the browser** with WebCodecs — no server, no upload. Also handles MCAP → MP4. | Node 18+, Python 3.10+, ffmpeg |
| [`packages/library`](packages/library) | The footage library: auto-ingest from removable media, a spreadsheet-style metadata editor served as a web app, thumbnails, gallery, rotate/split tools, CSV ⇄ Postgres. | Flask, Python 3.10+ |
| [`packages/library-legacy`](packages/library-legacy) | The single-file generation of the library app. One `app.py`, one `requirements.txt`, runs anywhere — useful as a reference implementation. | Flask |
| [`packages/platform`](packages/platform) | Multi-tenant upload & management platform: uploader PWA, admin console, BullMQ workers, device adapters, Drizzle schema, Docker Compose. | Next.js 15, Fastify, Postgres, Redis |
| [`packages/delivery-client`](packages/delivery-client) | Generic delivery client: signs parts, uploads a session, reports completion. Ships a schema-faithful but fully synthetic parameter set. | Python, Node |
| [`packages/segmenter-web`](packages/segmenter-web) | Browser-only video cutter using FFmpeg.wasm — trim, split, and re-encode without uploading anything. | React, TypeScript, FFmpeg.wasm |
| [`packages/segmenter-app`](packages/segmenter-app) | The same cutter as a desktop app (Electron), with a visual timeline and smart duration validation. | Electron, React, TypeScript |

---

## Why these pieces together

The individual parts are not unusual. What is unusual is that they were built as **one
pipeline**: the ingest layer knows what the decode layer expects, the library's schema
matches the delivery client's contract, and the segmenter produces exactly the clip
lengths the delivery target will accept.

If you only want one piece, each one stands alone:

### Decode a head-mounted session

```bash
cd packages/codec-hmd
node hmd2mp4.js session_00000/part_000.hmd      # → part_000.mp4
node hmd2mp4.js --dedup --color --h265 --imu session_00000/part_000.hmd
```

```js
const { parse } = require('./hmd-decode.js');
const r = await parse(new Uint8Array(fs.readFileSync('part_000.hmd')));
console.log(r.video[0].hevc);   // raw HEVC bitstream
console.log(r.imu.length);      // IMU sample count
```

Open `packages/codec-hmd/hmd-preview.html` in Chrome 94+ / Edge 88+ to play a stereo
session in-browser — WebCodecs decodes both eyes locally, so the footage never leaves
the machine.

### Run the library

```bash
cd packages/library
pip install -r requirements.txt
python src/run.py            # → http://localhost:5000
```

Point `config.json` at a directory of clips; the app scans it, renders a table, and
lets you tag each row, preview it inline, and export the result as TXT or CSV.

### Run the platform

```bash
cd packages/platform
cp .env.example .env
docker compose up -d          # Postgres + Redis + MinIO
pnpm install
pnpm db:migrate && pnpm db:seed
pnpm dev                      # uploader :3001, admin :3002
```

### Cut a video entirely in the browser

```bash
cd packages/segmenter-web
npm install && npm run dev
```

---

## Design notes

**Local first.** The preview paths — decoding, thumbnailing, trimming, tagging — all run
on your machine. Nothing reaches the network until you explicitly publish.

**Contracts as data.** The delivery client's field dictionary (`stereo-upload-params/`)
is a schema, not hard-coded strings. Swap the JSON and the whole pipeline targets a
different downstream system.

**Plain files, no database required.** The library runs on a CSV. Postgres is optional
and additive — it adds query power without becoming a prerequisite.

**Synthetic by default.** Every sample shipped here is invented. See
[docs/SANITIZATION.md](docs/SANITIZATION.md) for exactly what was removed and how.

---

## Repository layout

```
frameforge/
├── packages/
│   ├── codec-hmd/          head-mounted / MCAP decoding + browser stereo playback
│   ├── library/            footage library (Flask app, services, routes, models)
│   ├── library-legacy/     single-file reference implementation
│   ├── platform/           Next.js monorepo: uploader, admin, worker, schema
│   ├── delivery-client/    generic upload client + parameter schema
│   ├── segmenter-web/      browser FFmpeg.wasm cutter
│   └── segmenter-app/      Electron cutter
├── docs/
│   ├── ARCHITECTURE.md     how the pieces fit together
│   ├── SANITIZATION.md     what was stripped before publication
│   └── MIGRATION.md        legacy name → current name mapping
└── samples/                synthetic sample data
```

---

## Status

This is a **published snapshot** of an internal toolkit. It is complete and runnable,
but it is not a supported product — expect rough edges in the operational scripts.

| Area | State |
|---|---|
| `codec-hmd` | Stable. 12/12 packet self-test passes. |
| `library` | Works. CSV mode is the well-trodden path; Postgres mode is newer. |
| `platform` | Functional. Schema migrations and admin console are solid; worker ops are thin. |
| `delivery-client` | Works against a generic endpoint. The bundled parameters are synthetic. |
| `segmenter-*` | Works. Both variants share the same core logic. |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Short version: keep packages independent, add a
sample for anything that needs a file to exist, and never commit real footage or real
operator data.

## License

MIT — see [LICENSE](LICENSE).

All sample data in this repository is synthetic and carries no third-party rights.
