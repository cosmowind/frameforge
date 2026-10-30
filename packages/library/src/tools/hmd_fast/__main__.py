#!/usr/bin/env python
"""CLI entry point: python -m tools.hmd_fast <session_folder>"""

import argparse

from tools.hmd_fast.preprocess import process_fast, process_frames_only, process_cover_only


def main():
    parser = argparse.ArgumentParser(description="HMD Fast Preprocess")
    parser.add_argument("folder", help="Session folder path")
    parser.add_argument("--extract-frames", action="store_true",
                        help="Only extract frames from existing left.h265")
    parser.add_argument("--cover-only", action="store_true",
                        help="Only generate cover from existing left.h265")
    parser.add_argument("--no-frames", action="store_true",
                        help="Skip frame extraction (decode only)")
    parser.add_argument("--no-cover", action="store_true",
                        help="Skip cover generation")
    args = parser.parse_args()

    folder = args.folder

    if args.extract_frames:
        results = process_frames_only(folder)
        print(f"Extracted {len(results)} frames from {folder}")
    elif args.cover_only:
        ok = process_cover_only(folder)
        print(f"Cover {'OK' if ok else 'FAILED'} for {folder}")
    else:
        status = process_fast(
            folder,
            extract_frames=not args.no_frames,
            extract_cover=not args.no_cover,
        )
        print(f"Fast preprocess done: {folder}")
        print(f"  Frames: {status.get('left_frames', 0)} left")
        print(f"  Duration: {status.get('duration_sec', 0)}s")
        print(f"  Preview frames: {status.get('frames_count', 0)}")
        print(f"  Cover: {'OK' if status.get('cover_ok') else 'N/A'}")


if __name__ == "__main__":
    main()
