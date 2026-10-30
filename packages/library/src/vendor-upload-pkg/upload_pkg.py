#!/usr/bin/env python3
"""Task-box aware uploader for publish.example.com/vendors.

Picks up where the legacy `upload.py` (free-form `.mp4`/`.mov` uploader) leaves
off: every upload flows through a task box capped at 10 hours of total duration.
For stereo `.hmd` sessions, the box is created/extended via the
`/api/deliveries/task-boxes` (and `/.../stereo-hmd-initiate`) endpoints and the
`.hmd` session is first converted to a single MCAP + metadata.json by the
Node script `hmd_to_mcap.js` next to this file.

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
        '--parts-glob', str(session_dir / 'part_*.hmd').replace('\\', '/'),
        '--metadata', str(session_dir / metadata_filename).replace('\\', '/'),
        '--out', str(mcap_out).replace('\\', '/'),
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


# ─── Box matching ──────────────────────────────────────────────────────────

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
    """Run the full stereo upload flow for ONE session folder.

    Returns a dict suitable for a single CSV row: file, status, videoId,
    boxId, boxAction, size, error.
    """
    row = {
        'file': str(session_dir),
        'status': 'failed',
        'videoId': '',
        'boxId': '',
        'boxAction': 'n/a',
        'size': '',
        'error': '',
    }

    # 1. Validate + convert .hmd → .mcap + metadata.json sidecar.
    parts, _meta_path = validate_session_dir(session_dir)
    log(f'  found {len(parts)} .hmd parts + metadata.json in {session_dir}')
    mcap_path, metadata_path = run_hmd_to_mcap(
        session_dir=session_dir,
        work_dir=work_dir,
        node_path=node_path,
    )
    mcap_size = mcap_path.stat().st_size
    metadata_size = metadata_path.stat().st_size
    row['size'] = str(mcap_size + metadata_size)

    # 2. Look for a matching approved box (5-tuple match).
    boxes = client.list_task_boxes(filter_='active')
    match = find_reusable_box(
        boxes,
        scenario=scenario,
        task_description=task_description,
        environment=environment,
        operator=operator,
        capture_mode='stereo',
    )

    # 3. Initiate: create new box OR upload to existing one.
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
    s3_bucket = init['s3Bucket']
    row['videoId'] = video_id

    # The init response carries:
    #   parts:        [{ partIndex, filename, fileSizeBytes, uploadId, s3Key, partSize, partCount }]
    #   metadataJson: { filename, fileSizeBytes, uploadId, s3Key, partSize, partCount }
    parts_inits = init['parts']
    metadata_init = init['metadataJson']

    # 4. Upload each object (parts array is normally length 1: the .mcap, plus
    # the metadata.json sidecar).
    completed_mcap_parts: list[dict] = []
    for p in parts_inits:
        file_path = mcap_path if p['filename'] == mcap_path.name else None
        if file_path is None:
            # The init payload uses canonical names — the mcap's filename is
            # the user-provided one (session.mcap in our case). Match by partIndex
            # being 0 (the only part).
            file_path = mcap_path
        log(f'  uploading {file_path.name} ({p["fileSizeBytes"]} bytes, {p["partCount"]} parts)...')
        sign_urls = client.stereo_sign_parts(
            video_id=video_id, s3_key=p['s3Key'], upload_id=p['uploadId'],
            part_numbers=list(range(1, p['partCount'] + 1)),
        )
        # Put each part sequentially (the legacy uploader uses parallel;
        # single-file-by-file here is fine for the mcap which is typically
        # hundreds of MB; we can switch to parallel later).
        from upload import upload_parts as _legacy_upload_parts
        completed = _legacy_upload_parts(file_path, p['fileSizeBytes'], sign_urls)
        completed_mcap_parts.append({
            'partIndex': p['partIndex'],
            'filename': p['filename'],
            'fileSizeBytes': p['fileSizeBytes'],
            'uploadId': p['uploadId'],
            's3Key': p['s3Key'],
            'completedParts': [{'partNumber': c['partNumber'], 'eTag': c['eTag']} for c in completed],
        })

    # 5. Upload metadata.json sidecar.
    log(f'  uploading {metadata_path.name} ({metadata_size} bytes, {metadata_init["partCount"]} parts)...')
    sign_urls = client.stereo_sign_parts(
        video_id=video_id, s3_key=metadata_init['s3Key'], upload_id=metadata_init['uploadId'],
        part_numbers=list(range(1, metadata_init['partCount'] + 1)),
    )
    from upload import upload_parts as _legacy_upload_parts
    meta_completed = _legacy_upload_parts(metadata_path, metadata_size, sign_urls)
    metadata_complete = {
        'filename': metadata_init['filename'],
        'fileSizeBytes': metadata_size,
        'uploadId': metadata_init['uploadId'],
        's3Key': metadata_init['s3Key'],
        'completedParts': [{'partNumber': c['partNumber'], 'eTag': c['eTag']} for c in meta_completed],
    }

    # 6. Complete.
    complete = client.stereo_complete(
        video_id=video_id,
        parts=completed_mcap_parts,
        metadata_json=metadata_complete,
        # video_stats omitted — .hmd recordings don't carry per-frame timestamps;
        # Foxglove Studio will play them back at the file's recorded fps once
        # the worker adds a real frame index.
    )
    log(f'  complete: {complete}')
    row['status'] = 'complete'
    return row


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
    src.add_argument('--session-dir', help='folder containing part_NNN.hmd + metadata.json (stereo mode)')
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
    if args.session_dir:
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
        # Write the CSV row.
        with open(log_path, 'w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=['file', 'status', 'videoId', 'boxId', 'boxAction', 'size', 'error'])
            w.writeheader()
            w.writerow(row)
        log(f'done. log → {log_path}')
        return 0

    # single / three_views — fall back to the legacy upload.py for now.
    sys.exit(
        f'capture-mode={capture_mode} is not implemented in upload_pkg.py yet; '
        'use upload.py (the legacy free-form uploader) for now.'
    )


if __name__ == '__main__':
    sys.exit(main())