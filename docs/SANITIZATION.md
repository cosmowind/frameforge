# Sanitization

This repository is a **published snapshot of internal tooling**. It was assembled from
a working commercial codebase and stripped of everything that identified the client,
the engagement, the devices, the people, or the downstream platform.

Everything here is synthetic. Nothing here is real footage, real operator data, or a
real credential.

## What was removed

| Category | Examples |
|---|---|
| **Third-party brand** | The name of the downstream publishing platform, its domain, its API route prefixes, its cookie names, and its database schema prefixes. |
| **Client identity** | The client organisation's name, its region names, its product catalogue, its task taxonomy, its street address. |
| **Proprietary format name** | The name of a head-mounted camera container format was renamed throughout — code identifiers, file names, database enums, env vars, and prose. |
| **Internal product acronym** | Replaced by `ff` (package names, database schema, table prefix `ff_*`, env prefix `FF_*`, bucket names) and `FrameForge` (prose). |
| **Role vocabulary** | The role that referred to the people gathering footage was renamed to *recorder*, and the Chinese term for collection was replaced with one for ingest/entry. |
| **Live credentials** | A hard-coded provider API key, several `.env` files with a live database DSN, a session-cookie file, and two production server IPs. |
| **Personal & device data** | Operator rosters with phone numbers, SD-card volume serials, device IDs, hostnames, session metadata, and per-session work records. |
| **Machine traces** | Absolute paths under the author's home and cloud-storage account, drive letters, LAN addresses, local usernames. |
| **Bulk media** | ~24 GB of footage, camera captures, thumbnails of real frames, screenshots of a real portal, and the generated preview cache. |
| **Scraped reference data** | HTML snapshots and option lists harvested from the live publishing portal. |

## What was kept

The actual engineering: the decoders, the Flask services and routes, the Next.js apps,
the Drizzle schema, the BullMQ workers, the device adapters, the delivery client, the
two segmenters, and the test scripts.

The code still runs. The schema still matches. The sample data still has the right
shape — only the values are invented.

## Synthetic samples

| File | What it replaces |
|---|---|
| `packages/library/src/data/recorders.csv` | The operator roster. |
| `packages/library/src/data/devices.csv` | The SD-card / device inventory. |
| `packages/library/src/data/tasks.csv` | The task catalogue. |
| `packages/library/src/data/library.csv` | The library index. |
| `packages/codec-hmd/samples/session_00000/metadata.json` | A captured session's metadata. |
| `packages/delivery-client/stereo-upload-params/*.zh-CN.json` | The field contract and scene taxonomy. |

The taxonomy keeps its original schema — `_note`, `values[]`, `id`, `label.{en,zh-CN}`,
`subcategories[]` — so anything consuming it keeps working. The values are invented:
4 top-level scene categories instead of the original 21, and generic manufacturing
scenes instead of the client's own.

## Upstream bugs found and fixed

Three classes of pre-existing syntax defect were found during verification and repaired
in the published copy. The upstream working copies were left untouched.

| File | Defect |
|---|---|
| `library/src/services/{cache,device,migration,translation}_service.py` | The body of the module's single function lost its indentation, so the module could not be parsed at all. |
| `library/src/services/startup_service.py` | Same, plus a flattened module-level `if/else` block whose nested `if` and trailing `print` sat at column 0. |
| `library/src/scripts/auto_fill_helper.py` | A duplicated closing triple-quote turned the following 18 lines into a string literal, so the next Chinese text was parsed as code. |
| `library/scripts/debug_sessions.py` | A Python keyword was used as a variable name. |
| `library/src/static/js/dim-table-crud.js` | A single-quoted string literal was split across two lines, so the file failed to parse. |

## Rotating the exposed credentials

These were live at the time of publication and must be treated as compromised. The
values themselves are deliberately not reproduced here.

| Credential | Scope | Action |
|---|---|---|
| Provider API key (`sk-…`) | A JSON config file in the legacy package | **Rotate.** Blanked in the published copy. |
| Postgres password | Several `.env` files under the platform package | **Rotate.** Files excluded. |
| Production database host | Several `.env` files and examples | **Rotate + firewall.** Replaced with `db.example.com`. |
| Production server host | The platform's production deploy example and CI workflow | **Rotate + firewall.** Replaced with `vps.example.com`. |
| Session cookies | The delivery client's cookie file | **Revoke the session.** File excluded; only the template survives. |

## Verifying a change

The same scan that gated the initial publication:

```bash
# legacy identifiers that must not reappear
grep -rniE 'legacy-format-name|legacy-brand|legacy-acronym' . --exclude-dir=.git

# credentials
grep -rniE 'sk-[A-Za-z0-9_-]{32,}|gh[pousr]_|AKID[A-Za-z0-9]{10,}|-----BEGIN' .

# absolute local paths
grep -rniE '[A-Za-z]:[/\\](Users|sys)' .

# public IP addresses
grep -rnoE '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b' . --exclude-dir=.git
```

Run all four before every push.
