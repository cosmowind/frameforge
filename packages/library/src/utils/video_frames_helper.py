"""Helper module for extracting frames from videos."""

import os
import subprocess


def extract_video_frames(video_path, output_dir, num_frames=6, width=320):
    """Extract multiple frames from MP4 video at even intervals.
    
    Args:
        video_path: Path to MP4 video file
        output_dir: Directory to save extracted frames
        num_frames: Number of frames to extract (default 6)
        width: Width of extracted frames (height auto)
    
    Returns:
        list of (timestamp_sec, frame_path) tuples, or empty list on failure
    """
    if not os.path.isfile(video_path):
        return []
    
    # Get video duration
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", video_path],
            capture_output=True, encoding="utf-8", errors="replace", timeout=10
        )
        if r.returncode == 0 and r.stdout.strip():
            duration = float(r.stdout.strip())
        else:
            duration = 30.0  # Default fallback
    except (subprocess.TimeoutExpired, ValueError, Exception):
        duration = 30.0
    
    # Calculate timestamps at even intervals
    # User requirement: 6 frames at 1/6, 2/6, 3/6, 4/6, 5/6, 6/6 points
    if duration < 1.0:
        duration = 1.0
    timestamps = [duration * (i + 1) / num_frames for i in range(num_frames)]
    
    # Extract frames
    os.makedirs(output_dir, exist_ok=True)
    results = []
    vf = f"scale={width}:-1:force_original_aspect_ratio=decrease"
    
    for i, ts in enumerate(timestamps):
        out_path = os.path.join(output_dir, f"frame_{i:02d}.jpg")
        try:
            r = subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error",
                 "-ss", f"{ts:.2f}",
                 "-i", video_path,
                 "-v_frames", "1",
                 "-vf", vf,
                 "-q:v", "5",
                 out_path],
                capture_output=True, encoding="utf-8", errors="replace", timeout=15
            )
            if r.returncode == 0 and os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
                results.append((ts, out_path))
        except (subprocess.TimeoutExpired, Exception):
            continue
    
    return results
