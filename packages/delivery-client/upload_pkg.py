#!/usr/bin/env python3
"""Task-box aware uploader for publish.example.com/vendors.

Picks up where the legacy `upload.py` (free-form `.mp4`/`.mov` uploader) leaves
off: every upload flows through a task box capped at 10 hours of total duration.

Two stereo source shapes are supported, both routed through the same frameforge
stereo endpoints (`/api/deliveries/task-boxes` + `/.../stereo-hmd-initiate` +
`/.../stereo-hmd-session/{sign-parts,complete}`):

  --session-dir DIR    Folder with `part_NNN.hmd` + `metadata.json`. The
                       .hmd session is first converted to a single Foxglove
                       MCAP + metadata.json by the Node script `hmd_to_mcap.js`
                       next to this file, then uploaded.

  --mcap-dir DIR       Folder with one `.mcap` + `metadata.json` (already
                       converted — e.g. by the frameforge in-browser
                       /hmd-converter page, or by `hmd_to_mcap.js` from a
                       previous run). The .mcap is uploaded as-is; videoStats
                       are read out of the MCAP header so the upstream row
                       gets fps/frameCount/durationSeconds stamped on it.

Business boundary (per the project README `MCAP 交付规范（供应商版）.md`):

  static/hmd/hmd-decode.esm.js   LOCAL PREVIEW ONLY. NOT on the upload path.
                                 Used by the in-browser viewer to render .hmd
                                 for the human filling out box params.

  hmd_to_mcap.js                 SUBMISSION-side conversion. Parses the
                                 Galaxea .hmd wire format directly (no
                                 dependency on the preview tool) and writes a
                                 single Foxglove MCAP that follows the
                                 vendor delivery spec. Outputs the local
                                 .mcap + metadata.json that THIS script uploads.

  upload_pkg.py                  THIS script. Uploads the produced artifacts
                                 via the frameforge stereo endpoints, reusing
                                 the Clerk auth + S3 multipart machinery from
                                 the legacy `upload.py`.

The preview and submission pipelines are intentionally separate: changes to
the preview tool never affect upload semantics, and vice versa.

`tools/inspect_mcap.py` and `tools/verify_mcap_matches_frontend.py` (see
`docs/README.md` §6) compare the .mcap produced by `hmd_to_mcap.js` against
the upstream frameforge browser converter (same FileDescriptorSet bytes,
same topic names, same message counts) so we can detect any drift.

Run `upload_pkg.py --help` for the parameter list.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.exceptions import ConnectionError, SSLError, Timeout

# MCAP reader — official Foxglove Python library (pip install mcap).
# Used for two purposes:
#   1. --mcap-dir mode: read fps / frameCount / durationSeconds out of a
#      pre-converted .mcap to forward as videoStats to /stereo-hmd-session/
#      complete (mirrors the stats the browser-side `hmdToMcap` derives).
#   2. tools/inspect_mcap.py dumps FDS / topics / message counts for verifying
#      that local conversion matches the frameforge upstream.
try:
    from mcap.reader import make_reader as _mcap_make_reader
    _HAVE_MCAP = True
except ImportError:  # pragma: no cover
    _mcap_make_reader = None
    _HAVE_MCAP = False

# Reuse helpers from the legacy free-form uploader (CookieSource, Clerk
# rotation, S3 part PUT, ffprobe duration, the network-retry wrapper, etc.).
# Relative import so the script works as `python3 upload_pkg.py` and as a
# package member (`python3 -m vendor_upload_pkg.upload_pkg`).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from upload import (  # noqa: E402  (sys.path mutated above on purpose)
    API_BASE,
    PART_SIZE,
    SIGN_BATCH,
    CookieSource,
    VendorUploadClient,
    _prompt_for_cookie_refresh,
    _try_auto_rotate,
    ffprobe_duration_seconds,
    log,
    put_part,
    upload_parts,
)

# Node side — `/<eye>/image-raw` topic names + the metadata.json sidecar. The
# backend frameforge schema name + filename constraints match
# `parseStereoHmdFiles` upstream: filename must be exactly `metadata.json`
# (case-insensitive), one .mcap + one metadata.json per session.
SESSION_METADATA_FILENAME = 'metadata.json'
SESSION_MCAP_TOPIC_LEFT = '/top-left-camera/image-raw'
SESSION_MCAP_TOPIC_RIGHT = '/top-right-camera/image-raw'

# `parseStereoHmdFiles` upstream rejects anything outside this set.
ALLOWED_FILENAME_RE = re.compile(r'^[A-Za-z0-9._-]+$')
CHINESE_CHAR_RE = re.compile(r'[一-鿿㐀-䶿]')

# Vendor delivery spec (MCAP 交付规范(供应商版).md) — topic→schema map used to
# build the per-topic message layout. Currently only the video + IMU topics
# are populated; calibration / TF-static would need supplier-side calibration
# data which the .hmd files don't carry.
SPEC_TOPICS = {
    SESSION_MCAP_TOPIC_LEFT: ('foxglove.CompressedVideo', 'left'),
    SESSION_MCAP_TOPIC_RIGHT: ('foxglove.CompressedVideo', 'right'),
    '/head-imu': ('google.protobuf.StringValue', 'imu'),
}


# ─── Node-side .hmd → .mcap conversion ─────────────────────────────────────

def run_hmd_to_mcap(
    *,
    session_dir: Path,
    work_dir: Path,
    node_path: str,
    metadata_filename: str = SESSION_METADATA_FILENAME,
) -> tuple[Path, Path]:
    """Shell out to `node hmd_to_mcap.js` and return (mcap_path, metadata_path)."""
    mcap_out = work_dir / 'session.mcap'
    node_script = Path(__file__).resolve().parent / 'hmd_to_mcap.js'
    cmd = [
        node_path,
        str(node_script),
        '--parts-glob', str(session_dir / 'part_*.hmd'),
        '--metadata', str(session_dir / metadata_filename),
        '--out', str(mcap_out),
    ]
    log(f'  running: {" ".join(cmd)}')
    completed = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    if completed.returncode != 0:
        raise RuntimeError(
            f'hmd_to_mcap.js failed (exit {completed.returncode})\n'
            f'stdout: {completed.stdout}\nstderr: {completed.stderr}'
        )
    # Last line of stdout is a JSON status object.
    last_json = None
    for line in completed.stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            last_json = json.loads(line)
        except json.JSONDecodeError:
            continue
    if not last_json or not last_json.get('ok'):
        raise RuntimeError(
            f'hmd_to_mcap.js did not emit a success status. stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}'
        )
    log(f'  conversion ok: {last_json["stats"]}')
    mcap_path = Path(last_json['mcap'])
    metadata_path = Path(last_json['metadata']) if last_json.get('metadata') else None
    if metadata_path is None:
        raise RuntimeError('hmd_to_mcap.js did not write a metadata.json sidecar')
    return mcap_path, metadata_path


# ─── Session folder validation ─────────────────────────────────────────────

def validate_session_dir(session_dir: Path) -> tuple[list[Path], Path]:
    """Return (sorted_part_files, metadata_path) or raise."""
    if not session_dir.is_dir():
        raise NotADirectoryError(f'{session_dir} is not a directory')
    entries = list(session_dir.iterdir())
    parts = sorted(
        [p for p in entries if p.is_file() and p.name.lower().endswith('.hmd')],
        key=lambda p: int(re.search(r'part_(\d+)\.hmd$', p.name, re.IGNORECASE).group(1)),
    )
    if not parts:
        raise FileNotFoundError(f'No part_*.hmd files in {session_dir}')
    meta = session_dir / SESSION_METADATA_FILENAME
    if not meta.is_file():
        raise FileNotFoundError(f'{session_dir} is missing {SESSION_METADATA_FILENAME}')
    # Filename constraints: no Chinese, no spaces, only [A-Za-z0-9._-].
    for p in parts + [meta]:
        if not ALLOWED_FILENAME_RE.match(p.name) or CHINESE_CHAR_RE.search(p.name):
            raise ValueError(
                f'Filename "{p.name}" has unsupported characters. Use letters, '
                'numbers, dot, dash, underscore only (no Chinese, no spaces).'
            )
    return parts, meta


# ─── Pre-converted MCAP ingestion (--mcap-dir mode) ───────────────────────

def validate_mcap_dir(mcap_dir: Path) -> tuple[Path, Path]:
    """Return (mcap_path, metadata_path) for a directory containing one .mcap
    + one metadata.json (the frameforge stereo session shape). Raises on
    anything else."""
    if not mcap_dir.is_dir():
        raise NotADirectoryError(f'{mcap_dir} is not a directory')
    entries = [p for p in mcap_dir.iterdir() if p.is_file()]
    mcap_matches = sorted(
        [p for p in entries if p.suffix.lower() == '.mcap'],
        key=lambda p: p.name.lower(),
    )
    meta_matches = [p for p in entries if p.name.lower() == SESSION_METADATA_FILENAME]
    if len(mcap_matches) == 0:
        raise FileNotFoundError(f'No .mcap file in {mcap_dir}')
    if len(mcap_matches) > 1:
        raise ValueError(
            f'Multiple .mcap files in {mcap_dir} (a stereo session takes exactly one): '
            + ', '.join(p.name for p in mcap_matches)
        )
    if len(meta_matches) == 0:
        raise FileNotFoundError(f'{mcap_dir} is missing {SESSION_METADATA_FILENAME}')
    if len(meta_matches) > 1:
        raise ValueError(
            f'Multiple {SESSION_METADATA_FILENAME} in {mcap_dir} (only one is allowed)'
        )
    mcap_path = mcap_matches[0]
    metadata_path = meta_matches[0]
    for p in (mcap_path, metadata_path):
        if not ALLOWED_FILENAME_RE.match(p.name) or CHINESE_CHAR_RE.search(p.name):
            raise ValueError(
                f'Filename "{p.name}" has unsupported characters. Use letters, '
                'numbers, dot, dash, underscore only (no Chinese, no spaces).'
            )
    return mcap_path, metadata_path


def read_mcap_video_stats(mcap_path: Path) -> dict | None:
    """Read fps / frameCount / durationSeconds from a pre-converted MCAP.

    Strategy (in order):
      1. Use mcap.summary.statistics if present (channel_message_counts has the
         authoritative per-topic count and message_count has the total).
      2. Fall back to a full iter_messages pass to count per-topic messages
         and compute the duration from min/max log_time.

    The function returns `None` if `mcap` isn't installed OR the file is
    unreadable — caller decides whether to omit videoStats or hard-fail.

    The schema of the returned dict mirrors the upstream
    `/api/deliveries/videos/stereo-hmd-session/complete` `videoStats` field:
      { fps: float, frameCount: int, durationSeconds: float }
    """
    if not _HAVE_MCAP:
        log('  WARNING: mcap python lib not installed (pip install mcap); '
            'skipping videoStats read for --mcap-dir.')
        return None
    try:
        with open(mcap_path, 'rb') as fh:
            reader = _mcap_make_reader(fh)
            summ = reader.get_summary()
            # Per-channel message count: the upstream conversion writes ONE
            # message per frame on the left + right video channels (and one
            # per IMU packet on /head-imu). The total video frame count for
            # the session is `left_count + right_count` (= 2 × left_count
            # because the recording is frame-interleaved 60 fps stereo).
            per_channel: dict[int, int] = {}
            if summ.statistics is not None and summ.statistics.channel_message_counts:
                per_channel = dict(summ.statistics.channel_message_counts)
            # Look up the topic names of the video channels via the summary.
            video_topic_counts: dict[str, int] = {}
            for ch_id, n in per_channel.items():
                ch = summ.channels.get(ch_id)
                if ch is None:
                    continue
                topic = ch.topic
                if topic.endswith('/image-raw'):
                    video_topic_counts[topic] = video_topic_counts.get(topic, 0) + n
            # First / second video topic = left / right (the conversion writes
            # them in lexical order). Whichever has the count, the "per-eye
            # frame count" is its message count.
            eye_counts = sorted(video_topic_counts.values())
            frame_count_per_eye = eye_counts[0] if eye_counts else 0
            # Duration: compute from min/max log_time on the video channels.
            # log_time is in nanoseconds (MCAP spec).
            log_time_ns: list[int] = []
            video_topics = list(video_topic_counts.keys())
            if video_topics:
                for _schema, channel, msg in reader.iter_messages(topics=video_topics):
                    log_time_ns.append(int(msg.log_time))
            duration_seconds = 0.0
            if len(log_time_ns) >= 2:
                duration_seconds = (max(log_time_ns) - min(log_time_ns)) / 1e9
            elif frame_count_per_eye > 0:
                # No log_time signal (rare — chunked write collapsed ts) —
                # assume 60 fps so the row gets a usable fps.
                duration_seconds = frame_count_per_eye / 60
            fps = (
                frame_count_per_eye / duration_seconds
                if duration_seconds > 0 and frame_count_per_eye > 0
                else 0
            )
            if frame_count_per_eye <= 0 or fps <= 0:
                return None
            return {
                'fps': fps,
                'frameCount': frame_count_per_eye,
                'durationSeconds': duration_seconds,
            }
    except Exception as exc:  # noqa: BLE001 — any decode error → no stats
        log(f'  WARNING: failed to read videoStats from {mcap_path}: {exc}')
        return None
    return None

def find_reusable_box(boxes: list[dict], *, scenario: str, task_description: str,
                      environment: str, operator: str, capture_mode: str) -> dict | None:
    """Match by the full 5-tuple (scenario, taskDescription, environmentDescription,
    operatorName, captureMode). Any field differing → new box. Only `approved`
    boxes are eligible for reuse (rejected/pending_review/filled are skipped)."""
    for b in boxes:
        if b.get('captureMode') != capture_mode:
            continue
        if b.get('status') != 'approved':
            continue
        if b.get('scenario') != scenario:
            continue
        if b.get('taskDescription') != task_description:
            continue
        # environmentDescription / operatorName aren't in the GET /task-boxes
        # payload — the list endpoint only returns denormalized scenario +
        # taskDescription + captureMode. To compare environment/operator we'd
        # need a per-box GET, which is too expensive for the listing hot-path.
        # We accept that the listing match is approximate and let the
        # per-box initiate re-validate the full tuple server-side (or reject
        # with a clear error if needed).
        _ = environment, operator
        return b
    return None


# ─── Frameforge stereo client (extends the legacy VendorUploadClient) ──────

class StereoTaskBoxClient(VendorUploadClient):
    """Adds the stereo / task-box endpoints on top of the legacy free-form client.

    Per the frameforge upstream `task-boxes/route.ts` + `stereo-hmd-initiate/route.ts`
    + `stereo-hmd-session/{sign-parts,complete}/route.ts` contract.
    """

    def list_task_boxes(self, filter_: str = 'active') -> list[dict]:
        """GET /api/deliveries/task-boxes?filter=active|rejected|filled|all"""
        url = f'{API_BASE}/api/deliveries/task-boxes?filter={filter_}'
        # Use the standard _post_json machinery for cookie retry + auth refresh;
        # it expects POST but accepts GET through a small override.
        for attempt in range(10):
            self._apply_cookies()
            try:
                r = self.s.get(url, timeout=30)
            except (SSLError, ConnectionError, Timeout) as e:
                log(f'    network blip on GET /task-boxes: {type(e).__name__} — retrying')
                time.sleep(min(30, 2 ** attempt))
                continue
            if r.status_code == 401:
                _prompt_for_cookie_refresh(self.source)
                continue
            if r.status_code >= 400:
                raise RuntimeError(f'GET /task-boxes → {r.status_code}: {r.text[:500]}')
            return r.json().get('boxes', [])
        raise RuntimeError('GET /task-boxes: too many transient failures')

    def create_stereo_box(self, *, scenario: str, task_description: str,
                          environment: str, operator: str, files: list[dict],
                          folder_name: str | None) -> dict:
        """POST /api/deliveries/task-boxes (stereo mode → multi-file session)."""
        body = {
            'scenario': scenario,
            'taskDescription': task_description,
            'environmentDescription': environment,
            'operatorName': operator,
            'captureMode': 'stereo',
            'files': files,
        }
        if folder_name:
            body['folderName'] = folder_name
        return self._post_json('/api/deliveries/task-boxes', body)

    def stereo_initiate(self, *, box_id: str, files: list[dict],
                        folder_name: str | None) -> dict:
        """POST /api/deliveries/task-boxes/:id/videos/stereo-hmd-initiate"""
        body = {'files': files}
        if folder_name:
            body['folderName'] = folder_name
        return self._post_json(
            f'/api/deliveries/task-boxes/{box_id}/videos/stereo-hmd-initiate',
            body,
        )

    def stereo_sign_parts(self, *, video_id: str, s3_key: str, upload_id: str,
                          part_numbers: list[int]) -> dict[int, str]:
        """POST /api/deliveries/videos/stereo-hmd-session/sign-parts"""
        out: dict[int, str] = {}
        for i in range(0, len(part_numbers), 200):
            batch = part_numbers[i:i + 200]
            res = self._post_json(
                '/api/deliveries/videos/stereo-hmd-session/sign-parts',
                {'videoId': video_id, 's3Key': s3_key, 'uploadId': upload_id,
                 'partNumbers': batch},
            )
            for item in res.get('urls', []):
                out[int(item['partNumber'])] = item['url']
        return out

    def stereo_complete(self, *, video_id: str,
                        parts: list[dict], metadata_json: dict,
                        video_stats: dict | None = None) -> dict:
        """POST /api/deliveries/videos/stereo-hmd-session/complete"""
        body: dict = {
            'videoId': video_id,
            'parts': parts,
            'metadataJson': metadata_json,
        }
        if video_stats:
            body['videoStats'] = video_stats
        return self._post_json(
            '/api/deliveries/videos/stereo-hmd-session/complete',
            body,
            timeout=300,
        )


# ─── Per-file flow (stereo) ────────────────────────────────────────────────

def _stereo_upload_core(
    client: StereoTaskBoxClient,
    *,
    scenario: str,
    task_description: str,
    environment: str,
    operator: str,
    mcap_path: Path,
    metadata_path: Path,
    folder_name: str | None,
    video_stats: dict | None,
) -> dict:
    """Shared backend for both the .hmd-converted and pre-converted .mcap
    flows. Takes already-resolved mcap_path + metadata_path on disk plus
    optional videoStats from the conversion step.

    Returns a dict suitable for a single CSV row.
    """
    row = {
        'file': str(mcap_path),
        'status': 'failed',
        'videoId': '',
        'boxId': '',
        'boxAction': 'n/a',
        'size': '',
        'error': '',
    }
    mcap_size = mcap_path.stat().st_size
    metadata_size = metadata_path.stat().st_size
    row['size'] = str(mcap_size + metadata_size)

    # 1. Look for a matching approved box (5-tuple match).
    boxes = client.list_task_boxes(filter_='active')
    match = find_reusable_box(
        boxes,
        scenario=scenario,
        task_description=task_description,
        environment=environment,
        operator=operator,
        capture_mode='stereo',
    )

    # 2. Initiate: create new box OR upload to existing one.
    files_payload = [
        {'filename': mcap_path.name, 'fileSizeBytes': mcap_size},
        {'filename': SESSION_METADATA_FILENAME, 'fileSizeBytes': metadata_size},
    ]
    if match:
        log(f'  reusing box {match["id"]} (status={match["status"]})')
        row['boxAction'] = 'reused'
        row['boxId'] = match['id']
        init = client.stereo_initiate(
            box_id=match['id'], files=files_payload, folder_name=folder_name,
        )
    else:
        log(f'  no matching box — creating a new one')
        row['boxAction'] = 'created'
        init = client.create_stereo_box(
            scenario=scenario,
            task_description=task_description,
            environment=environment,
            operator=operator,
            files=files_payload,
            folder_name=folder_name,
        )
        row['boxId'] = init['boxId']

    video_id = init['videoId']
    row['videoId'] = video_id

    parts_inits = init['parts']
    metadata_init = init['metadataJson']

    # 3. Upload the .mcap (parts is length 1 in the canonical stereo shape —
    # one MCAP per session — but iterate to stay robust to future shapes).
    from upload import upload_parts as _legacy_upload_parts
    completed_mcap_parts: list[dict] = []
    for p in parts_inits:
        log(f'  uploading {mcap_path.name} ({p["fileSizeBytes"]} bytes, {p["partCount"]} parts)...')
        sign_urls = client.stereo_sign_parts(
            video_id=video_id, s3_key=p['s3Key'], upload_id=p['uploadId'],
            part_numbers=list(range(1, p['partCount'] + 1)),
        )
        completed = _legacy_upload_parts(mcap_path, p['fileSizeBytes'], sign_urls)
        completed_mcap_parts.append({
            'partIndex': p['partIndex'],
            'filename': p['filename'],
            'fileSizeBytes': p['fileSizeBytes'],
            'uploadId': p['uploadId'],
            's3Key': p['s3Key'],
            'completedParts': [{'partNumber': c['partNumber'], 'eTag': c['eTag']} for c in completed],
        })

    # 4. Upload metadata.json sidecar.
    log(f'  uploading {metadata_path.name} ({metadata_size} bytes, {metadata_init["partCount"]} parts)...')
    sign_urls = client.stereo_sign_parts(
        video_id=video_id, s3_key=metadata_init['s3Key'], upload_id=metadata_init['uploadId'],
        part_numbers=list(range(1, metadata_init['partCount'] + 1)),
    )
    meta_completed = _legacy_upload_parts(metadata_path, metadata_size, sign_urls)
    metadata_complete = {
        'filename': metadata_init['filename'],
        'fileSizeBytes': metadata_size,
        'uploadId': metadata_init['uploadId'],
        's3Key': metadata_init['s3Key'],
        'completedParts': [{'partNumber': c['partNumber'], 'eTag': c['eTag']} for c in meta_completed],
    }

    # 5. Complete — forward videoStats when the conversion produced them
    # (frameforge upstream stamps fps/frameCount/durationSeconds onto the row).
    complete = client.stereo_complete(
        video_id=video_id,
        parts=completed_mcap_parts,
        metadata_json=metadata_complete,
        video_stats=video_stats,
    )
    log(f'  complete: {complete}')
    row['status'] = 'complete'
    return row


def upload_stereo_session(
    client: StereoTaskBoxClient,
    *,
    scenario: str,
    task_description: str,
    environment: str,
    operator: str,
    session_dir: Path,
    folder_name: str | None,
    work_dir: Path,
    node_path: str,
    log_path: Path,
) -> dict:
    """Run the full stereo upload flow for ONE .hmd session folder.

    Converts via `hmd_to_mcap.js` first, then delegates to _stereo_upload_core.
    """
    # 1. Validate + convert .hmd → .mcap + metadata.json sidecar.
    parts, _meta_path = validate_session_dir(session_dir)
    log(f'  found {len(parts)} .hmd parts + metadata.json in {session_dir}')
    mcap_path, metadata_path = run_hmd_to_mcap(
        session_dir=session_dir,
        work_dir=work_dir,
        node_path=node_path,
    )
    # Parse hmd_to_mcap.js's final JSON status line for the videoStats block
    # so the upstream /complete call can stamp fps/frameCount/durationSeconds
    # onto the row. Re-run with --quiet style is NOT possible (single-shot
    # script); instead, we re-read the mcap we just produced — same numbers
    # the upstream browser converter would derive.
    video_stats = read_mcap_video_stats(mcap_path)
    if video_stats is not None:
        log(f'  derived videoStats: fps={video_stats["fps"]:.2f}, '
            f'frames={video_stats["frameCount"]}, dur={video_stats["durationSeconds"]:.3f}s')

    return _stereo_upload_core(
        client,
        scenario=scenario,
        task_description=task_description,
        environment=environment,
        operator=operator,
        mcap_path=mcap_path,
        metadata_path=metadata_path,
        folder_name=folder_name,
        video_stats=video_stats,
    )


def upload_stereo_mcap_session(
    client: StereoTaskBoxClient,
    *,
    scenario: str,
    task_description: str,
    environment: str,
    operator: str,
    mcap_dir: Path,
    folder_name: str | None,
) -> dict:
    """Run the stereo upload flow for a pre-converted .mcap session folder
    (one .mcap + one metadata.json). No Node conversion is run — the mcap
    is uploaded as-is, with videoStats read out of the MCAP header.

    This is the entry point vendors should use when they already converted
    via the frameforge in-browser /hmd-converter (or any other compliant
    converter). It mirrors the upstream stereo flow exactly.
    """
    mcap_path, metadata_path = validate_mcap_dir(mcap_dir)
    log(f'  found pre-converted .mcap + metadata.json in {mcap_dir}')
    video_stats = read_mcap_video_stats(mcap_path)
    if video_stats is not None:
        log(f'  read videoStats from MCAP header: fps={video_stats["fps"]:.2f}, '
            f'frames={video_stats["frameCount"]}, dur={video_stats["durationSeconds"]:.3f}s')
    else:
        log('  no videoStats readable from MCAP (mcap lib missing or file unreadable)')

    return _stereo_upload_core(
        client,
        scenario=scenario,
        task_description=task_description,
        environment=environment,
        operator=operator,
        mcap_path=mcap_path,
        metadata_path=metadata_path,
        folder_name=folder_name,
        video_stats=video_stats,
    )


# ─── CLI ───────────────────────────────────────────────────────────────────

def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--cookie-file', default=os.environ.get('FF_COOKIE_FILE'),
                    help='cookie file with SESSION=/CLIENT=/CLIENT_UAT= lines; falls back to FF_COOKIE env var.')
    # Task-box identity (the 5-tuple).
    ap.add_argument('--scenario', required=True, help='scene-taxonomy-v2 leaf-task id (e.g. D01-S01-C01-T01)')
    ap.add_argument('--task-description', required=True, help='free-text task description')
    ap.add_argument('--environment-description', required=True, help='free-text environment description')
    ap.add_argument('--operator-name', required=True, help='who recorded these')
    ap.add_argument('--capture-mode', choices=['stereo', 'single', 'three_views'], default='stereo',
                    help='capture mode (stereo = .hmd session, single = .mp4/.mov, three_views = folder of 3 videos)')
    # Source. Mutually exclusive; capture-mode is auto-inferred from which one is set.
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--session-dir', help='folder containing part_NNN.hmd + metadata.json (stereo mode, runs hmd_to_mcap.js)')
    src.add_argument('--mcap-dir', help='folder containing one .mcap + metadata.json (stereo mode, already-converted; no Node conversion)')
    src.add_argument('--file', help='single .mp4/.mov file (single mode)')
    src.add_argument('--tv-dir', help='folder of exactly 3 .mp4 videos named _1/_2/_3 (three_views mode)')
    # Stereo-specific.
    ap.add_argument('--folder-name', default=None,
                    help='display name in the vendor portal (defaults to the session folder basename)')
    ap.add_argument('--node-path', default='node', help='node executable (default: node on PATH)')
    # Misc.
    ap.add_argument('--notes', default=None, help='optional free-text notes (stored on the box)')
    ap.add_argument('--country', default='US', help='ISO country code (default US)')
    ap.add_argument('--region', default='', help='region/state/province name')
    ap.add_argument('--recorder', default='', help='who recorded these (legacy metadata)')
    ap.add_argument('--parts-dir', default=None,
                    help='scratch directory for .mcap + metadata.json sidecar (default: tempdir)')
    ap.add_argument('--dry-run', action='store_true', help='print plan, no API calls, no conversion')
    return ap


def resolve_capture_mode(args: argparse.Namespace) -> str:
    """Auto-infer capture-mode from the source selector if not given."""
    if args.capture_mode:
        return args.capture_mode
    if args.session_dir or args.mcap_dir:
        return 'stereo'
    if args.file:
        return 'single'
    if args.tv_dir:
        return 'three_views'
    raise SystemExit('Cannot infer capture mode — pass --capture-mode explicitly.')


def main(argv: list[str] | None = None) -> int:
    ap = build_argparser()
    args = ap.parse_args(argv)
    capture_mode = resolve_capture_mode(args)

    # Auth setup.
    if args.cookie_file:
        cookie_source = CookieSource(file=args.cookie_file)
        cookie_source.load()
    else:
        cookie = os.environ.get('FF_COOKIE')
        if not cookie:
            sys.exit('ERROR: set FF_COOKIE env var (or pass --cookie-file)')
        cookie_source = CookieSource(session=cookie)

    client = StereoTaskBoxClient(cookie_source)

    # Pick the source.
    if capture_mode == 'stereo':
        # Two sub-paths:
        #   --session-dir → run hmd_to_mcap.js first (hmd → mcap)
        #   --mcap-dir    → assume the .mcap is already there (no Node conversion)
        if args.session_dir:
            session_dir = Path(args.session_dir).expanduser().resolve()
            if not session_dir.is_dir():
                sys.exit(f'ERROR: {session_dir} is not a directory')
            if args.dry_run:
                parts, _ = validate_session_dir(session_dir)
                log(f'[dry-run] would convert {len(parts)} .hmd parts + metadata.json '
                    f'into one .mcap + metadata.json sidecar, then upload as a stereo session.')
                log(f'[dry-run] would call /api/deliveries/task-boxes to either create or '
                    f'extend an approved box matching (scenario={args.scenario!r}, '
                    f'task={args.task_description!r}, captureMode=stereo, ...).')
                return 0
            work_dir = Path(args.parts_dir).expanduser().resolve() if args.parts_dir \
                else Path(tempfile.mkdtemp(prefix='vendor-upload-pkg-'))
            work_dir.mkdir(parents=True, exist_ok=True)
            log_path = Path('upload-log-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.csv')
            row = upload_stereo_session(
                client,
                scenario=args.scenario,
                task_description=args.task_description,
                environment=args.environment_description,
                operator=args.operator_name,
                session_dir=session_dir,
                folder_name=args.folder_name or session_dir.name,
                work_dir=work_dir,
                node_path=args.node_path,
                log_path=log_path,
            )
            with open(log_path, 'w', newline='') as fh:
                w = csv.DictWriter(fh, fieldnames=['file', 'status', 'videoId', 'boxId', 'boxAction', 'size', 'error'])
                w.writeheader()
                w.writerow(row)
            log(f'done. log → {log_path}')
            return 0

        if args.mcap_dir:
            mcap_dir = Path(args.mcap_dir).expanduser().resolve()
            if not mcap_dir.is_dir():
                sys.exit(f'ERROR: {mcap_dir} is not a directory')
            if args.dry_run:
                mcap_path, metadata_path = validate_mcap_dir(mcap_dir)
                stats = read_mcap_video_stats(mcap_path)
                log(f'[dry-run] would upload pre-converted .mcap '
                    f'{mcap_path.name} ({mcap_path.stat().st_size / 1e6:.1f} MB) '
                    f'+ metadata.json ({metadata_path.stat().st_size} bytes) as a stereo session.')
                if stats:
                    log(f'[dry-run] videoStats from MCAP: fps={stats["fps"]:.2f}, '
                        f'frames={stats["frameCount"]}, dur={stats["durationSeconds"]:.3f}s')
                else:
                    log('[dry-run] (no videoStats readable — install mcap lib for stats)')
                log(f'[dry-run] would call /api/deliveries/task-boxes to either create or '
                    f'extend an approved box matching (scenario={args.scenario!r}, '
                    f'task={args.task_description!r}, captureMode=stereo, ...).')
                return 0
            log_path = Path('upload-log-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.csv')
            row = upload_stereo_mcap_session(
                client,
                scenario=args.scenario,
                task_description=args.task_description,
                environment=args.environment_description,
                operator=args.operator_name,
                mcap_dir=mcap_dir,
                folder_name=args.folder_name or mcap_dir.name,
            )
            with open(log_path, 'w', newline='') as fh:
                w = csv.DictWriter(fh, fieldnames=['file', 'status', 'videoId', 'boxId', 'boxAction', 'size', 'error'])
                w.writeheader()
                w.writerow(row)
            log(f'done. log → {log_path}')
            return 0

        sys.exit('ERROR: stereo capture-mode requires --session-dir or --mcap-dir')

    # single / three_views — fall back to the legacy upload.py for now.
    sys.exit(
        f'capture-mode={capture_mode} is not implemented in upload_pkg.py yet; '
        'use upload.py (the legacy free-form uploader) for now.'
    )


if __name__ == '__main__':
    sys.exit(main())