# Architecture

FrameForge is five layers. Each one only talks to the layer below it through a
**contract**, so you can replace any of them without touching the others.

```
┌─────────────────────────────────────────────────────────────────────┐
│  delivery-client          packages/delivery-client                  │
│  Signs parts, uploads a session, reports completion.                │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ stereo-upload-params/*.zh-CN.json
                               │ (the field contract)
┌──────────────────────────────┴──────────────────────────────────────┐
│  platform                packages/platform                          │
│  uploader PWA · admin console · BullMQ workers · Drizzle schema     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ REST + Postgres
┌──────────────────────────────┴──────────────────────────────────────┐
│  library                 packages/library                           │
│  ingest · index · tag · thumbnail · gallery · rotate · split        │
│  (CSV is the source of truth; Postgres is optional)                 │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ files on disk
┌──────────────────────────────┴──────────────────────────────────────┐
│  codec-hmd                packages/codec-hmd                        │
│  .hmd → MP4 · MCAP → MP4 · browser stereo playback (WebCodecs)      │
└─────────────────────────────────────────────────────────────────────┘

      segmenter-web / segmenter-app sit alongside: they consume the
      library's output and produce clips that satisfy the delivery
      contract's duration and size limits.
```

## The contract is the contract

`packages/delivery-client/stereo-upload-params/params.zh-CN.json` defines every field,
its label in two languages, whether it is required, and the server-side limits
(part size, max file bytes, max files per batch, filename pattern).

Everything else derives from it:

- `platform` generates the upload form and the Drizzle columns from the same shapes.
- `library` fills the form from its CSV columns.
- `delivery-client` validates against it before uploading.

If you change one of those three, change the JSON and the other two follow.

## Device adapters

`platform/packages/adapters` implements one adapter per capture device family:

| Code | Layout on the card | Preview strategy | Delivery preparation |
|---|---|---|---|
| `dji-gopro-dcim` | `DCIM/` | native HTML5 | direct |
| `head-mounted-hmd` | `hmd/` with `part_*.hmd` | hmd decoder | extract-hmd |
| `gopro-session-mcap` | `data/` with `*.mcap` | mcap extractor | extract-mcap |
| `generic-avi` | `recordings/<date>_<ts>/` | native + sequential JS playback | concat-avi |

Each adapter answers three questions: what does this device look like on disk, how do we
preview it, and what has to be transformed before delivery.

## Storage tiers

`platform` treats storage as three tiers with different failure tolerances:

- **L1** — object storage (S3/COS-compatible), written directly by the uploader.
- **L2** — a local disk pulled on a schedule.
- **L3** — offsite backup on a coarse rotation.

Records move through explicit states so a failure is visible rather than silent:
`SCANNED → UPLOADING → UPLOADED → LOCAL_DELETED → ARCHIVED`.
