#!/usr/bin/env python3
"""Bulk uploader for publish.example.com/vendors.

Pipeline per file:
  1. POST /api/deliveries/videos/initiate       → get videoId + multipart uploadId + presigned-URL plan
  2. POST /api/deliveries/videos/sign-parts     → batch of presigned PUT URLs (chunks of 100)
  3. PUT each part in parallel to S3         → collect ETags
  4. POST /api/deliveries/videos/complete       → finalize, archive, queue scene analysis

Files larger than 3 GB are split losslessly with `ffmpeg -c copy -segment_time` first.

Usage:
  export FF_COOKIE='__session=eyJ...'          # paste from browser DevTools
  ./upload.py \\
      --dir ~/Downloads/quark_task_01 \\
      --country US \\
      --region 'California' \\
      --recorder 'Sample Operator' \\
      --category industrial_manufacturing \\
      --subcategory industrial_other \\
      --label 'Sort snowflake blocks' \\
      --notes 'Pulled from quark share sample-share-id'
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from requests.exceptions import ConnectionError, SSLError, Timeout

API_BASE = os.environ.get("DR_API_BASE", "https://publish.example.com")
PART_SIZE = 64 * 1024 * 1024            # must match server VENDOR_UPLOAD_PART_SIZE
MAX_FILE_BYTES = 3 * 1024 * 1024 * 1024  # must match server VENDOR_UPLOAD_MAX_FILE_BYTES (3 GB)
SPLIT_SAFETY_BYTES = int(2.8 * 1024 * 1024 * 1024)  # split target ~2.8 GB to stay clearly under 3 GB
SPLIT_MIN_DURATION = 30                   # minimum seconds per chunk (ensure every chunk ≥ 30s)
ALLOWED_EXT = {".mp4", ".mov"}
PARALLEL_PARTS = 4                       # number of S3 part PUTs in flight at once
SIGN_BATCH = 100                         # how many presigned URLs to request per /sign-parts call

# ffmpeg/ffprobe path (Windows compatible)
FFMPEG_CMD = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links", "ffmpeg.exe")
FFPROBE_CMD = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links", "ffprobe.exe")


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ─── ffprobe / ffmpeg helpers ────────────────────────────────────────────────

def ffprobe_duration_seconds(path: Path) -> float | None:
    """Return duration in seconds or None if probe failed."""
    try:
        out = subprocess.run(
            [FFPROBE_CMD, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True, timeout=30,
        ).stdout.strip()
        return float(out) if out else None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return None


def split_big_file(src: Path, work_dir: Path) -> list[Path]:
    """Split src into ≤SPLIT_SAFETY_BYTES chunks. Returns list of part paths.

    Uses ffmpeg stream copy + segmenter — lossless, fast. After splitting,
    if the last chunk is disproportionately small (< 700 MB) we re-split
    it together with the previous chunk to balance them evenly.
    """
    size = src.stat().st_size
    duration = ffprobe_duration_seconds(src)
    if not duration or duration <= 0:
        chunks = max(2, math.ceil(size / SPLIT_SAFETY_BYTES))
        segment_seconds = 1200
    else:
        bitrate_bps = size * 8 / duration
        target_bits = SPLIT_SAFETY_BYTES * 8
        segment_seconds = max(60, int(target_bits / bitrate_bps))
        chunks = math.ceil(duration / segment_seconds)

    out_pattern = work_dir / f"{src.stem}_part%02d{src.suffix}"
    log(f"  splitting {src.name} ({size / 1e9:.2f} GB) → ~{chunks} chunks of {segment_seconds}s")
    subprocess.run(
        [FFMPEG_CMD, "-y", "-hide_banner", "-loglevel", "warning",
         "-i", str(src),
         "-c", "copy", "-map", "0:v", "-map", "0:a",
         "-f", "segment", "-segment_time", str(segment_seconds),
         "-reset_timestamps", "1",
         str(out_pattern)],
        check=True,
    )
    parts = sorted(work_dir.glob(f"{src.stem}_part*{src.suffix}"))

    # ── Tail rebalance: if last chunk < 700 MB, merge it with previous and split evenly ──
    TAIL_MIN_BYTES = 700 * 1024 * 1024
    if len(parts) >= 2 and parts[-1].stat().st_size < TAIL_MIN_BYTES:
        prev = parts[-2]
        last = parts[-1]
        log(f"  last chunk {last.name} is {last.stat().st_size / 1e6:.1f} MB (< 700 MB), rebalancing with {prev.name}")
        # Merge prev + last via concat, then split evenly
        merged = work_dir / f"{src.stem}_merged{src.suffix}"
        concat_file = work_dir / f"{src.stem}_concat.txt"
        concat_file.write_text(
            f"file '{prev.resolve().as_posix()}'\nfile '{last.resolve().as_posix()}'\n",
            encoding="utf-8",
        )
        subprocess.run(
            [FFMPEG_CMD, "-y", "-hide_banner", "-loglevel", "warning",
             "-f", "concat", "-safe", "0", "-i", str(concat_file),
             "-c", "copy",
             str(merged)],
            check=True,
        )
        concat_file.unlink()
        prev.unlink()
        last.unlink()
        # Re-split the merged file into 2 balanced halves
        merged_dur = ffprobe_duration_seconds(merged)
        if merged_dur and merged_dur > 0:
            half_sec = max(SPLIT_MIN_DURATION, int(merged_dur / 2))
        else:
            half_sec = 1200
        out_pattern2 = work_dir / f"{src.stem}_part%02d{src.suffix}"
        log(f"  re-splitting merged ({merged.stat().st_size / 1e6:.1f} MB, {merged_dur:.0f}s) → 2 chunks of {half_sec}s")
        subprocess.run(
            [FFMPEG_CMD, "-y", "-hide_banner", "-loglevel", "warning",
             "-i", str(merged),
             "-c", "copy", "-map", "0:v", "-map", "0:a",
             "-f", "segment", "-segment_time", str(half_sec),
             "-reset_timestamps", "1",
             str(out_pattern2)],
            check=True,
        )
        merged.unlink()
        parts = sorted(work_dir.glob(f"{src.stem}_part*{src.suffix}"))

    # Sanity check: every chunk must be under the API cap, else recurse.
    for p in list(parts):
        if p.stat().st_size > MAX_FILE_BYTES:
            log(f"  [WARN] chunk {p.name} still > 3 GB - re-splitting with shorter window")
            sub_dir = work_dir / f"{p.stem}_resplit"
            sub_dir.mkdir(exist_ok=True)
            sub_parts = split_big_file(p, sub_dir)
            parts.remove(p)
            p.unlink()
            parts.extend(sub_parts)
    return sorted(parts)


# ─── Cookie source (file or env) ─────────────────────────────────────────────

class CookieSource:
    """Reloadable source of Clerk cookies.

    Two modes:
      file=PATH  → load on every call, so editing the file (e.g. pasting a
                   fresh __session value mid-run) takes effect immediately.
      env       → snapshot of env vars at startup; for batch jobs short enough
                   that the cookie won't expire.

    File format (one per line, # comments OK):
        SESSION=<__session JWT>
        CLIENT=<__client JWT>
        CLIENT_UAT=<unix timestamp>
    """
    def __init__(self, *, file: str | None = None,
                 session: str | None = None,
                 client: str | None = None,
                 client_uat: str | None = None):
        self.file = Path(file).expanduser() if file else None
        self._env_snapshot = (session, client, client_uat)

    def load(self) -> tuple[str, str | None, str | None]:
        if self.file:
            if not self.file.exists():
                raise RuntimeError(f"Cookie file not found: {self.file}")
            parsed: dict[str, str] = {}
            for raw in self.file.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, val = line.partition("=")
                parsed[key.strip().upper()] = val.strip().strip('"').strip("'")
            session = parsed.get("SESSION") or parsed.get("__SESSION")
            client = parsed.get("CLIENT") or parsed.get("__CLIENT")
            client_uat = parsed.get("CLIENT_UAT") or parsed.get("__CLIENT_UAT")
            if not session:
                raise RuntimeError(f"{self.file} missing SESSION= line")
            return session, client, client_uat
        s, c, u = self._env_snapshot
        if not s:
            raise RuntimeError("no session cookie in env or file")
        return s, c, u


def _try_auto_rotate(source: CookieSource) -> bool:
    """Try to auto-rotate __session by calling Clerk directly. Returns True on success.

    Imports lazily so the rotator's optional dependencies don't break the
    script if rotate_session.py is missing or has import errors.
    """
    if not source.file:
        return False
    try:
        from src.rotate_session import rotate as _rotate  # type: ignore
    except Exception as e:
        log(f"    auto-rotate unavailable ({type(e).__name__}: {e})")
        return False
    try:
        ok = _rotate(source.file)
    except Exception as e:
        log(f"    auto-rotate raised {type(e).__name__}: {e}")
        return False
    if ok:
        log("    auto-rotated __session via Clerk — retrying.")
    else:
        log("    auto-rotate did not produce a fresh session — falling back to manual.")
    return ok


def _prompt_for_cookie_refresh(source: CookieSource, wait_seconds: int = 600) -> None:
    """Pause and ask the user to refresh cookies, then continue.

    Three paths:
      * auto  → try Clerk session-token endpoint with the long-lived __client
                cookie already in cookie.txt. Silent on success.
      * tty   → blocking input(); user hits Enter when ready.
      * pipe  → poll the cookie file's mtime; when it changes (you saved a
                new SESSION= line), we retry. Useful when the script is
                running in the background — just edit & save cookie.txt.
    """
    if _try_auto_rotate(source):
        return

    if source.file:
        log(f"  → 401. Refresh browser tab to rotate __session, then edit and SAVE")
        log(f"    {source.file} (update the SESSION= line).")
    else:
        log("  → 401. Refresh browser tab, copy new __session, re-export FF_COOKIE.")
        log("    (Or re-run with --cookie-file for hot-reload.)")

    if sys.stdin.isatty():
        try:
            input("    Press Enter when ready to retry (Ctrl-C to abort)... ")
        except EOFError:
            pass
        return

    # Non-interactive: poll cookie file mtime for up to wait_seconds.
    if not source.file:
        # Nothing to watch; sleep a short while so the loop doesn't spin.
        time.sleep(30)
        return
    initial_mtime = source.file.stat().st_mtime
    deadline = time.time() + wait_seconds
    log(f"    waiting up to {wait_seconds}s for {source.file.name} to change...")
    while time.time() < deadline:
        time.sleep(3)
        try:
            if source.file.stat().st_mtime > initial_mtime:
                log("    detected cookie file update — retrying.")
                return
        except FileNotFoundError:
            continue
    log("    timed out waiting for cookie refresh.")


# ─── publish.example.com API client ─────────────────────────────────────────────────

class VendorUploadClient:
    """Vendor portal API client with hot-reloadable auth + transient-error retries.

    Cookies are reloaded from CookieSource before every request, so a stale
    __session can be fixed mid-upload by updating the cookie file.
    """

    NETWORK_RETRY = 3       # consecutive SSL/connection failures we retry
    AUTH_RETRY = 5          # consecutive 401s before giving up (each prompts user)

    def __init__(self, source: CookieSource):
        self.source = source
        self.s = requests.Session()
        # Ignore HTTP_PROXY / HTTPS_PROXY env vars — Clerk + S3 are reachable
        # direct from China; a dead local proxy (clash/v2ray on 127.0.0.1:7897)
        # would otherwise turn every call into ProxyError "connection refused".
        self.s.trust_env = False
        self.s.headers.update({
            "Accept": "application/json",
            "User-Agent": "vendor-bulk-upload/1.0",
        })

    def _apply_cookies(self) -> None:
        session, client, client_uat = self.source.load()
        host = urlparse(API_BASE).hostname or "publish.example.com"
        # Clear stale cookies first so updates take effect.
        for name in ("__session", "__client", "__client_uat"):
            try:
                self.s.cookies.clear(domain=host, path="/", name=name)
            except KeyError:
                pass
        for name, value in (
            ("__session", session),
            ("__client", client),
            ("__client_uat", client_uat),
        ):
            if not value:
                continue
            v = value.strip()
            if v.startswith(f"{name}="):
                v = v.split("=", 1)[1]
            self.s.cookies.set(name, v, domain=host)

    def _post_json(self, path: str, body: dict, timeout: int = 60) -> dict:
        url = f"{API_BASE}{path}"
        net_attempts = 0
        auth_attempts = 0
        while True:
            self._apply_cookies()
            try:
                r = self.s.post(url, json=body, timeout=timeout)
            except (SSLError, ConnectionError, Timeout) as e:
                net_attempts += 1
                if net_attempts > self.NETWORK_RETRY:
                    raise RuntimeError(f"POST {path}: network failure persisted after {self.NETWORK_RETRY} retries: {e}")
                backoff = min(30, (2 ** net_attempts) + random.uniform(0, 1))
                log(f"    network blip on {path}: {type(e).__name__} — retrying in {backoff:.1f}s ({net_attempts}/{self.NETWORK_RETRY})")
                time.sleep(backoff)
                continue
            if r.status_code == 401:
                auth_attempts += 1
                if auth_attempts > self.AUTH_RETRY:
                    raise RuntimeError(f"POST {path}: 401 persisted after {self.AUTH_RETRY} cookie refreshes")
                _prompt_for_cookie_refresh(self.source)
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"POST {path} → {r.status_code}: {r.text[:500]}")
            return r.json()

    def initiate(self, *, filename: str, content_type: str, size: int, duration: float | None,
                 country: str, region: str, recorder: str, category: str,
                 subcategory: str, custom_label: str | None, notes: str | None) -> dict:
        body = {
            "filename": filename,
            "contentType": content_type,
            "fileSizeBytes": size,
            "durationSeconds": duration,
            "countryCode": country,
            "region": region,
            "recorderName": recorder,
            "sceneCategory": category,
            "sceneSubcategory": subcategory,
        }
        if custom_label:
            body["sceneCustomLabel"] = custom_label
        if notes:
            body["notes"] = notes
        return self._post_json("/api/deliveries/videos/initiate", body)

    def sign_parts(self, video_id: str, part_numbers: list[int]) -> dict[int, str]:
        out: dict[int, str] = {}
        for i in range(0, len(part_numbers), SIGN_BATCH):
            batch = part_numbers[i:i + SIGN_BATCH]
            res = self._post_json(
                "/api/deliveries/videos/sign-parts",
                {"videoId": video_id, "partNumbers": batch},
            )
            for item in res.get("urls", []):
                out[int(item["partNumber"])] = item["url"]
        return out

    def complete(self, video_id: str, parts: list[dict]) -> dict:
        return self._post_json(
            "/api/deliveries/videos/complete",
            {"videoId": video_id, "parts": parts},
            timeout=300,
        )


# ─── S3 part PUT ─────────────────────────────────────────────────────────────

_S3_SESSION = requests.Session()
_S3_SESSION.trust_env = False  # same reason as the API client — bypass dead local proxy

def put_part(url: str, data: bytes, retries: int = 3) -> str:
    """PUT one part to the presigned URL, return its ETag (with surrounding quotes preserved)."""
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            # Lower timeout so the user sees progress sooner; retries handle transient issues
            r = _S3_SESSION.put(url, data=data, timeout=120)
            if r.status_code >= 400:
                raise RuntimeError(f"S3 PUT {r.status_code}: {r.text[:200]}")
            etag = r.headers.get("ETag", "")
            if not etag:
                raise RuntimeError("S3 PUT returned no ETag")
            return etag
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
    raise RuntimeError(f"PUT failed after {retries} attempts: {last_err}")


def upload_parts(file_path: Path, total_size: int, sign_urls: dict[int, str]) -> list[dict]:
    """Read the file in PART_SIZE chunks and PUT each to its presigned URL in parallel."""
    part_results: list[tuple[int, str]] = []

    def _read_and_put(part_no: int) -> tuple[int, str]:
        offset = (part_no - 1) * PART_SIZE
        with open(file_path, "rb") as fh:
            fh.seek(offset)
            data = fh.read(PART_SIZE)
        log(f"    uploading part {part_no}/{len(sign_urls)} ({len(data) / 1e6:.1f} MB)...")
        etag = put_part(sign_urls[part_no], data)
        log(f"    [OK] part {part_no} done -> {etag[:14]}...")
        return part_no, etag

    with ThreadPoolExecutor(max_workers=PARALLEL_PARTS) as pool:
        futures = [pool.submit(_read_and_put, n) for n in sorted(sign_urls.keys())]
        for f in as_completed(futures):
            part_results.append(f.result())

    part_results.sort(key=lambda x: x[0])
    return [{"partNumber": n, "eTag": etag} for n, etag in part_results]


# ─── Per-file flow ────────────────────────────────────────────────────────────

def upload_one(client: VendorUploadClient, file_path: Path, meta: dict, split_root: Path | None = None) -> dict:
    size = file_path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise RuntimeError(f"{file_path.name} is {size / 1e9:.2f} GB — split first")

    duration = ffprobe_duration_seconds(file_path)
    content_type = "video/mp4" if file_path.suffix.lower() == ".mp4" else "video/quicktime"
    log(f"  initiate: {file_path.name} ({size / 1e6:.1f} MB, duration={duration}s)")

    init = client.initiate(
        filename=file_path.name, content_type=content_type, size=size, duration=duration,
        **meta,
    )
    if init.get("skipped"):
        log(f"  [SKIP] already uploaded (videoId={init.get('existingVideoId')})")
        return {"file": str(file_path), "status": "skipped", "videoId": init.get("existingVideoId")}

    video_id = init["videoId"]
    part_count = init["partCount"]
    log(f"  videoId={video_id}, parts={part_count}")

    log(f"  requesting {part_count} presigned URLs...")
    sign_urls = client.sign_parts(video_id, list(range(1, part_count + 1)))
    if len(sign_urls) != part_count:
        raise RuntimeError(f"sign-parts returned {len(sign_urls)} urls, expected {part_count}")

    parts = upload_parts(file_path, size, sign_urls)
    log(f"  complete: {video_id}")
    client.complete(video_id, parts)
    # Clean up split part files after successful completion.
    if split_root is None:
        split_root = Path(__file__).resolve().parent / "videos" / "_parts"
    try:
        if file_path.parent == split_root and file_path.suffix.lower() in ALLOWED_EXT:
            file_path.unlink()
            # If parent dir is now empty, remove it.
            if not any(split_root.iterdir()):
                split_root.rmdir()
    except Exception:
        pass
    return {"file": str(file_path), "status": "complete", "videoId": video_id, "size": size}


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--dir", help="folder containing .mp4/.mov to upload (all under one --label)")
    src.add_argument("--file", action="append", help="upload one specific file; repeat the flag for multiple")
    ap.add_argument("--country", required=True, help="ISO country code, e.g. CN, US")
    ap.add_argument("--region", required=True, help="region/state/province name")
    ap.add_argument("--recorder", required=True, help="who recorded these")
    ap.add_argument("--category", required=True, help="sceneCategory id (see vendor-upload-taxonomy.ts)")
    ap.add_argument("--subcategory", required=True, help="sceneSubcategory id under that category")
    ap.add_argument("--label", default=None, help="custom label, required if subcategory is *_other")
    ap.add_argument("--notes", default=None, help="optional free-text notes")
    ap.add_argument("--cookie-file", default=os.environ.get("FF_COOKIE_FILE"),
                    help="path to file with SESSION=/CLIENT=/CLIENT_UAT= lines; reloaded "
                         "before every API call so you can paste fresh __session mid-run. "
                         "Falls back to FF_COOKIE/DR_CLIENT/DR_CLIENT_UAT env vars.")
    ap.add_argument("--parts-dir", default=None,
                    help="directory for split part files (default: videos/_parts/ relative to script)")
    ap.add_argument("--dry-run", action="store_true", help="print plan, don't upload")
    args = ap.parse_args()

    if args.cookie_file:
        cookie_source = CookieSource(file=args.cookie_file)
        # Smoke-test the file early so we don't choke after starting an upload.
        cookie_source.load()
    else:
        cookie = os.environ.get("FF_COOKIE")
        if not cookie:
            sys.exit("ERROR: set FF_COOKIE env var (or pass --cookie-file)")
        client_cookie = os.environ.get("DR_CLIENT")
        client_uat = os.environ.get("DR_CLIENT_UAT")
        if not client_cookie or not client_uat:
            log("WARN: DR_CLIENT and/or DR_CLIENT_UAT not set — Clerk auth likely to 401")
        cookie_source = CookieSource(session=cookie, client=client_cookie, client_uat=client_uat)

    if args.dir:
        src_dir = Path(args.dir).expanduser().resolve()
        if not src_dir.is_dir():
            sys.exit(f"ERROR: {src_dir} is not a directory")
        raw_files = sorted([p for p in src_dir.iterdir()
                            if p.is_file() and p.suffix.lower() in ALLOWED_EXT])
        if not raw_files:
            sys.exit(f"ERROR: no .mp4/.mov files in {src_dir}")
    else:
        raw_files = []
        for f in args.file:
            p = Path(f).expanduser().resolve()
            if not p.is_file():
                sys.exit(f"ERROR: {p} is not a file")
            if p.suffix.lower() not in ALLOWED_EXT:
                sys.exit(f"ERROR: {p.name} is not .mp4/.mov")
            raw_files.append(p)
        # Logs go alongside the first file's parent dir.
        src_dir = raw_files[0].parent

    log(f"found {len(raw_files)} candidate files in {src_dir}")
    total_bytes = sum(p.stat().st_size for p in raw_files)
    log(f"total size: {total_bytes / 1e9:.2f} GB")

    # Split anything over the cap into the designated parts dir.
    if args.parts_dir:
        work_dir = Path(args.parts_dir).resolve()
    else:
        work_dir = Path(__file__).resolve().parent / "videos" / "_parts"
    work_dir.mkdir(parents=True, exist_ok=True)

    plan: list[Path] = []
    for p in raw_files:
        if p.stat().st_size <= MAX_FILE_BYTES:
            plan.append(p)
        else:
            log(f"file > 3 GB: {p.name}")
            if args.dry_run:
                log("  (dry-run: skipping split)")
                continue
            plan.extend(split_big_file(p, work_dir))

    log(f"plan: {len(plan)} upload(s)")
    for p in plan:
        log(f"  - {p.name} ({p.stat().st_size / 1e6:.1f} MB)")

    if args.dry_run:
        log("dry-run done.")
        return

    meta = {
        "country": args.country,
        "region": args.region,
        "recorder": args.recorder,
        "category": args.category,
        "subcategory": args.subcategory,
        "custom_label": args.label,
        "notes": args.notes,
    }
    client = VendorUploadClient(cookie_source)

    log_path = src_dir / f"upload-log-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    with open(log_path, "w", newline="") as log_fh:
        w = csv.DictWriter(log_fh, fieldnames=["file", "status", "videoId", "size", "error"])
        w.writeheader()
        for i, p in enumerate(plan, 1):
            log(f"[{i}/{len(plan)}] {p.name}")
            try:
                row = upload_one(client, p, meta, split_root=work_dir)
            except Exception as e:
                log(f"  [ERROR] {e}")
                row = {"file": str(p), "status": "failed", "error": str(e)}
            w.writerow({k: row.get(k, "") for k in w.fieldnames})
            log_fh.flush()

    log(f"done. log → {log_path}")


if __name__ == "__main__":
    main()
