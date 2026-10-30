# Naming and migration

This repository was consolidated from several internal projects that were developed
independently and later merged. The original names were implementation details and, in
several cases, tied to a specific client engagement, so they were replaced.

## Why the names changed

Three things had to be true for the merged repository to be publishable:

1. **No third-party brand.** The downstream platform this tooling fed is a different
   company. Its name, domain, API routes, cookie names and database prefixes were
   replaced with neutral equivalents (`publish.example.com`, `/api/deliveries/…`,
   `ff_*`).
2. **No proprietary format name.** The head-mounted camera container format has a
   vendor-specific name. It was renamed to **HMD** across code identifiers, file
   names, database enums, environment variables and prose, so the repository reads as
   a general tool rather than as somebody's client work.
3. **No client vocabulary.** The role that referred to the people gathering footage
   was renamed to *recorder*, and the client-specific terms for regions, products and
   task categories were replaced with generic ones.

## Name mapping

| Concept | Current name | Applies to |
|---|---|---|
| Head-mounted camera container | **HMD** (`.hmd`) | Identifiers, file names, database enums, env vars, prose |
| The decoder | `hmd-decode.*` | `.js`, `.cjs`, `.esm.js` |
| The converter CLI | `hmd2mp4.js` | codec package |
| The browser players | `hmd-player*.html`, `hmd-preview.html` | codec package |
| The preview cache | `hmd_cache/` | on-disk cache directory |
| The library routes | `hmd_routes.py`, `hmd_fast/` | library services |
| The container → MCAP bridge | `hmd_to_mcap.js` | delivery client |
| The product | `ff` (packages) / **FrameForge** (prose) | package names, DB schema, table prefix (`ff_*`), env prefix (`FF_*`), bucket names |
| The role | `recorder` / `录入员` | role vocabulary, CSV columns, route names |
| The library app | `library`, `library-legacy` | package layout |
| The cutters | `segmenter-web`, `segmenter-app` | package layout |
| The downstream platform | `publish.example.com` | endpoints, cookie names, schema prefixes |
| The head-mounted device code | `head-mounted-hmd` | device adapter registry |

## Project lineage

The packages were not written in this order. The timeline, oldest first:

1. **`library-legacy`** — a single-file Flask app that scanned a directory of clips and
   maintained the index in a CSV.
2. **`codec-hmd`** — the decoder for head-mounted recordings, developed alongside the
   library so previews could be produced without a server round-trip.
3. **`library`** — the library refactored into services, routes and models, with
   Postgres added as an optional backend.
4. **`platform`** — the multi-tenant upload and management platform, replacing the
   single-operator model.
5. **`delivery-client`** — the vendor-side upload client, split out of the library once
   delivery became a separate concern.
6. **`segmenter-web` / `segmenter-app`** — the cutters, first as a browser tool, then
   wrapped as a desktop app.

## Environment variable changes

Every environment variable, database schema and table prefix was renamed in the same
pass. The published names are the `FF_*` / `ff` / `ff_*` family:

| Purpose | Current |
|---|---|
| Service ports | `FF_PORT`, `FF_WORKER_PORT` |
| Database schema | `DATABASE_SCHEMA=ff` |
| Table prefix | `ff_users`, `ff_devices`, `ff_video_records`, … |
| Decoder path | `HMD_DECODER_PATH` |
| Object-storage bucket | `ff-uploads-<id>` |

The exact previous identifiers are not reproduced here — this repository is public,
and the old names carried the engagement's context. Anyone migrating an existing
deployment will have them in their own configuration.

## Migration checklist for an existing deployment

- [ ] Rename the database schema to `ff`:
      `ALTER SCHEMA <old> RENAME TO ff;`
- [ ] Rename every `<old>_*` table to `ff_*`:
      `ALTER TABLE <old>_users RENAME TO ff_users;`
- [ ] Replace the old container file extension with `.hmd`, and rename the preview
      cache directory to `hmd_cache/`.
- [ ] Update the `FF_*` environment variables and the schema parameter in
      `DATABASE_URL`.
- [ ] Re-point the delivery client's base URL and cookie file at your own endpoint.
- [ ] Replace the bundled `stereo-upload-params/` with your own parameter set — the
      published one is synthetic and will not match any real backend.
