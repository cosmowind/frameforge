"""video_routes — video streaming, thumbnails, and frame preview."""

import os
import threading
import urllib.parse

from flask import Blueprint, jsonify, request, send_file

from config import THUMBNAILS_DIR
from services.video import (
    _ensure_frames, _ensure_thumbnail, _get_placeholder_thumb,
    _is_registered_video_path, _is_hmd_session, _read_fingerprint,
    _thumb_cache_key,
)

bp = Blueprint("video", __name__)


# ─────────────────────────────────────────────────────────────────
# Video streaming
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/video")
def serve_video():
    """Stream a video file by path."""
    video_path = request.args.get("path", "").strip()
    if not video_path:
        return "Missing path", 400
    video_path = video_path.replace("/", os.sep).replace("\\", os.sep)
    if not _is_registered_video_path(video_path):
        return "Forbidden", 403
    if not os.path.isfile(video_path):
        return "Not found", 404
    return send_file(video_path, mimetype="video/mp4", conditional=True)


@bp.route("/hmd-preview")
def hmd_preview():
    """Serve the HMD preview MP4 (from hmd_cache)."""
    video_path = request.args.get("path", "").strip()
    if not video_path:
        return "Missing path", 400
    video_path = video_path.replace("/", os.sep).replace("\\", os.sep)
    if not _is_registered_video_path(video_path):
        return "Forbidden", 403
    if not os.path.isfile(video_path):
        return "Not found", 404
    return send_file(video_path, mimetype="video/mp4", conditional=True)


# ─────────────────────────────────────────────────────────────────
# Thumbnails
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/thumbnail")
def get_thumbnail():
    """Return cached JPEG thumbnail for a registered video path."""
    path = (request.args.get("path") or "").strip()
    if not path:
        return "Missing path", 400
    if not _is_registered_video_path(path):
        return "Forbidden: path not in video_manager.csv", 403
    if os.path.isdir(path):
        kind = "hmd"
    else:
        kind = "hmd" if _is_hmd_session(path) else "mp4"
        if kind == "mp4" and not os.path.isfile(path):
            kind = "unknown"
    try:
        cache = _ensure_thumbnail(path, kind) if kind in ("mp4", "hmd") else None
    except Exception as e:
        print(f"[thumbnail] Unexpected error generating thumbnail for {path}: {e}", flush=True)
        cache = None
    if not cache:
        placeholder = _get_placeholder_thumb()
        if placeholder:
            resp = send_file(placeholder, mimetype="image/jpeg", conditional=True, max_age=86400)
            resp.headers["X-Thumbnail-Placeholder"] = "1"
            return resp
        return "Thumbnail generation failed", 404
    return send_file(cache, mimetype="image/jpeg", conditional=True, max_age=86400)


@bp.route("/api/thumbnail/warm", methods=["POST"])
def warm_thumbnails():
    """Background-warm thumbnails for a list of video paths."""
    body = request.get_json(silent=True) or {}
    paths = body.get("paths") or []
    if not isinstance(paths, list):
        return jsonify({"error": "paths must be list"}), 400
    queued = 0
    for p in paths:
        if not isinstance(p, str) or not _is_registered_video_path(p):
            continue
        if not os.path.isfile(p):
            continue
        kind = "hmd" if _is_hmd_session(p) else "mp4"
        if kind != "mp4":
            continue
        def _bg(path=p, k=kind):
            try:
                _ensure_thumbnail(path, k)
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()
        queued += 1
    return jsonify({"ok": True, "queued": queued}), 202


# ─────────────────────────────────────────────────────────────────
# Frames
# ─────────────────────────────────────────────────────────────────

@bp.route("/api/frames/warm", methods=["POST"])
def warm_frames():
    """Background-warm 6-frame previews for a list of video paths."""
    body = request.get_json(silent=True) or {}
    paths = body.get("paths") or []
    if not isinstance(paths, list):
        return jsonify({"error": "paths must be list"}), 400
    queued = 0
    for p in paths:
        if not isinstance(p, str) or not _is_registered_video_path(p):
            continue
        kind = "hmd" if _is_hmd_session(p) else "mp4"
        def _bg(path=p, k=kind):
            try:
                _ensure_frames(path, k, num_frames=6, width=320)
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()
        queued += 1
    return jsonify({"ok": True, "queued": queued}), 202


@bp.route("/api/video/frames")
def video_get_frames():
    """Extract and return multiple preview frames from MP4 video."""
    video_path = request.args.get("path", "")
    if video_path:
        video_path = video_path.replace("/", os.sep).replace("\\", os.sep)
    if not video_path or not os.path.isfile(video_path):
        return jsonify({"error": "Invalid video path"}), 400
    if not _is_registered_video_path(video_path):
        return jsonify({"error": "Forbidden: path not in video_manager.csv"}), 403
    num_frames = int(request.args.get("num", "6"))
    width = int(request.args.get("width", "320"))
    frames_dir = _ensure_frames(video_path, "mp4", num_frames=num_frames, width=width)
    if not frames_dir or not os.path.isdir(frames_dir):
        return jsonify({"frames": [], "error": "Frame extraction failed"}), 500
    frame_files = sorted([f for f in os.listdir(frames_dir) if f.endswith(".jpg")])
    frames = []
    for f in frame_files:
        frames.append({
            "url": f"/api/video/frame?path={urllib.parse.quote(video_path)}&file={urllib.parse.quote(f)}",
            "file": f,
        })
    return jsonify({"frames": frames})


@bp.route("/api/video/frame")
def video_serve_frame():
    """Serve a specific frame image from video frames cache."""
    video_path = request.args.get("path", "")
    file = request.args.get("file", "")
    if video_path:
        video_path = video_path.replace("/", os.sep).replace("\\", os.sep)
    if not video_path or not file:
        return "Bad request", 400
    if not file.endswith(".jpg"):
        return "Forbidden", 403
    if not _is_registered_video_path(video_path):
        return "Forbidden", 403
    key, fp = _thumb_cache_key(video_path, validate_staleness=True)
    frame_path = os.path.join(THUMBNAILS_DIR, "frames", key, file)
    if not os.path.isfile(frame_path):
        return "Frame not found", 404
    fp_path = os.path.join(THUMBNAILS_DIR, "frames", key, ".fingerprint")
    stored_fp = _read_fingerprint(fp_path)
    if stored_fp and stored_fp != fp:
        return "Frame expired (source changed)", 404
    return send_file(frame_path, mimetype="image/jpeg", conditional=True, max_age=86400)