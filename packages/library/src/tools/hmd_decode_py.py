#!/usr/bin/env python
"""Pure-Python HMD decoder: extract HEVC from .hmd container files.
Re-implements hmd-decode.js parse() + splitStereo() + dedupParamSets()
to bypass Node.js ArrayBuffer memory limit for large HMD sessions.

Uses mmap to avoid loading entire part files into RAM.

Output: left.h265 file (HEVC bitstream, left eye / even frames)
        right.h265 file (HEVC bitstream, right eye / odd frames) [optional]

Usage (called from hmd_preprocess.py):
    python hmd_decode_py.py <output_left.h265> [output_right.h265] part_000.hmd [part_001.hmd ...]
"""
import sys, os, struct, mmap, tempfile

MAGIC = b"HMD3"
IMU_TYPE = 0x59
GLUE_TYPE = 0x5a
CHUNK_TYPE = 0xfd

HEADER_LEN = 8
IMU_TOTAL = 97
GLUE_HEADER = 8
CHUNK_HEADER = 27


def find_packets(data):
    """Scan bytes-like `data` for HMD3 packet headers; return list of (offset, type)."""
    results = []
    pos = 0
    end = len(data)
    while pos + HEADER_LEN <= end:
        if (data[pos] == 0x55 and data[pos+1] == 0x4d and
            data[pos+2] == 0x49 and data[pos+3] == 0x33):
            pkt_type = data[pos+4]
            if pkt_type == IMU_TYPE or pkt_type == GLUE_TYPE:
                if data[pos+5] == 0 and data[pos+6] == 0 and data[pos+7] == 0:
                    results.append((pos, pkt_type))
            elif pkt_type == CHUNK_TYPE:
                if (data[pos+6] == 0 and data[pos+7] == 0 and
                    data[pos+8] == 0x86 and data[pos+9] == 0x01):
                    results.append((pos, pkt_type))
        pos += 1
    return results


def extract_hevc_to_file(part_mmaps, part_offsets, out_fileobj):
    """Extract HEVC bitstream from mmap-ed part files, write directly to a file-like object.
    This avoids storing the entire HEVC stream in memory (which can be multiple GB).
    Returns stats_dict.
    """
    total_len = part_offsets[-1] + len(part_mmaps[-1]) if part_mmaps else 0

    # Collect all packets across all parts
    all_packets = []
    for pi, data in enumerate(part_mmaps):
        local_packets = find_packets(data)
        for offset, pkt_type in local_packets:
            all_packets.append((offset + part_offsets[pi], pkt_type))
    all_packets.sort(key=lambda x: x[0])

    stats = {"realPackets": len(all_packets), "imu": 0, "glue": 0,
             "chunkPackets": 0, "hevcBytes": 0}

    # Extract HEVC byte ranges, write directly to out_fileobj
    cursor = 0  # global offset
    for i, (pkt_global_off, pkt_type) in enumerate(all_packets):
        if pkt_type == IMU_TYPE:
            pkt_end = pkt_global_off + IMU_TOTAL
        elif pkt_type == GLUE_TYPE:
            pkt_end = pkt_global_off + GLUE_HEADER
        elif pkt_type == CHUNK_TYPE:
            if i + 1 < len(all_packets):
                pkt_end = all_packets[i+1][0]
            else:
                pkt_end = total_len
        else:
            pkt_end = pkt_global_off + HEADER_LEN

        if cursor < pkt_global_off:
            _write_range(out_fileobj, cursor, pkt_global_off, part_mmaps, part_offsets)
            stats["hevcBytes"] += pkt_global_off - cursor

        if pkt_type == GLUE_TYPE:
            hevc_start = pkt_global_off + GLUE_HEADER
            if hevc_start < pkt_end:
                _write_range(out_fileobj, hevc_start, pkt_end, part_mmaps, part_offsets)
                stats["hevcBytes"] += pkt_end - hevc_start
        elif pkt_type == CHUNK_TYPE:
            hevc_start = pkt_global_off + CHUNK_HEADER
            if hevc_start < pkt_end:
                _write_range(out_fileobj, hevc_start, pkt_end, part_mmaps, part_offsets)
                stats["hevcBytes"] += pkt_end - hevc_start

        cursor = pkt_end

    if cursor < total_len:
        _write_range(out_fileobj, cursor, total_len, part_mmaps, part_offsets)
        stats["hevcBytes"] += total_len - cursor

    return stats


def _write_range(out_fileobj, global_start, global_end, part_mmaps, part_offsets):
    """Read bytes in global range and write directly to out_fileobj."""
    pos = global_start
    while pos < global_end:
        pi = _find_part(pos, part_offsets)
        local_pos = pos - part_offsets[pi]
        if pi + 1 < len(part_offsets):
            part_size = part_offsets[pi+1] - part_offsets[pi]
        else:
            part_size = global_end - part_offsets[pi]
        end_in_part = min(part_size, global_end - part_offsets[pi])
        out_fileobj.write(part_mmaps[pi][local_pos:end_in_part])
        pos = part_offsets[pi] + end_in_part


def extract_hevc(part_mmaps, part_offsets):
    """Extract HEVC bitstream from mmap-ed part files.
    Returns (hevc_bytes, stats_dict).
    NOTE: This loads entire HEVC into memory; for large sessions use extract_hevc_to_file().
    """
    import io
    buf = io.BytesIO()
    stats = extract_hevc_to_file(part_mmaps, part_offsets, buf)
    return buf.getvalue(), stats


def _add_range(out_ranges, global_start, global_end, part_offsets):
    """Convert global byte range to per-part ranges (appends to out_ranges)."""
    pos = global_start
    while pos < global_end:
        pi = _find_part(pos, part_offsets)
        local_pos = pos - part_offsets[pi]
        # Compute this part's size
        if pi + 1 < len(part_offsets):
            part_size = part_offsets[pi+1] - part_offsets[pi]
        else:
            # Last part: size = whatever is left (global_end won't exceed it)
            part_size = global_end - part_offsets[pi]
        end_in_part = min(part_size, global_end - part_offsets[pi])
        out_ranges.append((pi, local_pos, local_pos + end_in_part))
        pos = part_offsets[pi] + end_in_part


def _find_part(global_off, part_offsets):
    """Binary search: which part contains global_off."""
    lo, hi = 0, len(part_offsets) - 1
    while lo < hi:
        mid = (lo + hi + 1) >> 1
        if part_offsets[mid] <= global_off:
            lo = mid
        else:
            hi = mid - 1
    return lo


def split_stereo(hevc_bytes):
    """Split frame-interleaved HEVC into left (even frames) and right (odd frames)."""
    aus = _parse_aus(hevc_bytes)
    left_aus = aus[::2]
    right_aus = aus[1::2]

    param_nal_types = {32, 33, 34}

    def au_to_bytes(au_list):
        out = bytearray()
        # Write param sets first
        written_params = set()
        for au in au_list:
            for nal in au:
                if len(nal) > 4:
                    nal_type = (nal[4] >> 1) & 0x3f
                    if nal_type in param_nal_types and nal_type not in written_params:
                        out.extend(nal)
                        written_params.add(nal_type)
        for au in au_list:
            for nal in au:
                out.extend(nal)
        return bytes(out)

    left_bytes = au_to_bytes(left_aus)
    right_bytes = au_to_bytes(right_aus)
    stats = {"leftFrames": len(left_aus), "rightFrames": len(right_aus)}
    return left_bytes, right_bytes, stats


def _find_next_start(data, pos):
    """Find next start code position using bytes.find (C-level, ~100x faster
    than byte-by-byte Python loop for large files)."""
    data_len = len(data)
    if pos >= data_len - 3:
        return data_len

    while True:
        p = data.find(b'\x00\x00\x01', pos)
        if p == -1:
            return data_len
        # Check if this is actually a 4-byte start code (0x00 0x00 0x00 0x01)
        # where the 3-byte pattern sits at p, with a leading 0x00 at p-1
        if p > 0 and data[p - 1] == 0:
            if p - 1 >= pos:
                return p - 1   # 4-byte start code
            # This 3-byte match is the tail of a start code we've already passed
            pos = p + 3
            continue
        # Genuine 3-byte start code
        return p


def _parse_aus(hevc_bytes):
    """Parse HEVC bitstream into Access Units (list of list of NAL bytes).

    Uses bytes.find() (C-level) instead of byte-by-byte Python loops
    for large file performance (~100x speedup for multi-GB streams).
    """
    aus = []
    current_au = []
    i = 0
    data_len = len(hevc_bytes)

    while i < data_len - 3:
        # Use bytes.find() to locate the next start code at C speed
        p3 = hevc_bytes.find(b'\x00\x00\x01', i)
        if p3 == -1:
            break

        # Determine if 3-byte or 4-byte start code
        if p3 > 0 and hevc_bytes[p3 - 1] == 0:
            # 4-byte start code: 0x00 0x00 0x00 0x01 at p3-1
            start = p3 - 1
            code_len = 4
        else:
            # 3-byte start code: 0x00 0x00 0x01 at p3
            start = p3
            code_len = 3

        # Find next start code, slice NAL unit
        end = _find_next_start(hevc_bytes, start + code_len)
        nal = hevc_bytes[start:end]

        nal_type = (nal[code_len] >> 1) & 0x3f if len(nal) > code_len else 0
        if nal_type <= 21:  # VCL NAL unit
            if current_au:
                has_vcl = any(((n[code_len] >> 1) & 0x3f) <= 21
                              for n in current_au if len(n) > code_len)
                if has_vcl:
                    aus.append(current_au)
                    current_au = []
        current_au.append(nal)
        i = end

    if current_au:
        aus.append(current_au)
    return aus


def split_stereo_to_files(hevc_file, left_out_path, right_out_path):
    """Parse HEVC from file-like object, split into left/right files.
    Streaming: does NOT load entire HEVC into memory.
    Returns (left_frames, right_frames).
    """
    # Parse AUs from the file-like object (read in chunks)
    # We need to find start codes and parse AUs without loading everything
    aus_nal_types = []  # list of (nal_type_is_vcl,) for each AU

    # Actually, we still need to buffer individual AUs to know frame boundaries.
    # But each AU is small (one frame ~few KB to few MB), so this is fine.
    # The problem was storing the ENTIRE stream; per-AU is OK.

    # Read file in chunks and parse AUs incrementally
    left_frames = 0
    right_frames = 0

    # Use _parse_aus_from_file which reads sequentially
    aus = _parse_aus_from_file(hevc_file)

    left_aus = aus[::2]
    right_aus = aus[1::2]

    param_nal_types = {32, 33, 34}

    def write_aus(au_list, out_path):
        written_params = set()
        with open(out_path, "wb") as f:
            for au in au_list:
                for nal in au:
                    if len(nal) > 4:
                        nal_type = (nal[4] >> 1) & 0x3f
                        if nal_type in param_nal_types and nal_type not in written_params:
                            f.write(nal)
                            written_params.add(nal_type)
            for au in au_list:
                for nal in au:
                    f.write(nal)

    write_aus(left_aus, left_out_path)
    if right_out_path:
        write_aus(right_aus, right_out_path)

    return len(left_aus), len(right_aus)


def _parse_aus_from_file(fileobj):
    """Parse HEVC bitstream from a file-like object into Access Units.
    Reads the file sequentially without loading it all into memory.
    Returns list of AUs (each AU is list of NAL unit bytes).
    """
    # Read file in 64MB chunks and find start codes
    CHUNK_SIZE = 64 * 1024 * 1024
    aus = []
    current_au = []
    fileobj.seek(0)

    # We need to handle start code crossing chunk boundaries
    # Simpler approach: use mmap on the temp file (it's already on disk)
    # Actually the input fileobj is a temp file on disk - just mmap it
    if hasattr(fileobj, 'fileno'):
        import mmap as mmap_mod
        try:
            mm = mmap_mod.mmap(fileobj.fileno(), 0, access=mmap_mod.ACCESS_READ)
            try:
                file_size_mb = mm.size() / (1024 * 1024)
                print(f"Parsing HEVC stream ({file_size_mb:.0f} MB, this may take a while)...",
                      file=sys.stderr, flush=True)
                result = _parse_aus(mm)
                print(f"Parsing complete: {len(result)} access units found.",
                      file=sys.stderr, flush=True)
                return result
            finally:
                mm.close()
        except Exception as e:
            print(f"[warn] mmap failed: {e}, falling back to file read", file=sys.stderr)

    # Fallback: read all (only happens for small files or weird file objects)
    print("Reading HEVC file into memory...", file=sys.stderr, flush=True)
    data = fileobj.read()
    return _parse_aus(data)


def main():
    if len(sys.argv) < 3:
        print("Usage: python hmd_decode_py.py <left_out.h265> [right_out.h265] part1.hmd [part2.hmd ...]")
        sys.exit(1)

    left_out = sys.argv[1]
    right_out = sys.argv[2] if len(sys.argv) > 3 and not sys.argv[2].endswith('.hmd') else None
    parts_start = 3 if right_out else 2

    part_paths = sys.argv[parts_start:]
    if not part_paths:
        print("Error: no part files given", file=sys.stderr)
        sys.exit(1)

    print(f"PROGRESS:5", flush=True)
    print(f"Opening {len(part_paths)} part files (mmap)...", file=sys.stderr)

    # Open all parts as mmap (does NOT load into RAM)
    part_mmaps = []
    part_files = []
    part_offsets = []
    total = 0
    for p in part_paths:
        f = open(p, "rb")
        part_files.append(f)
        try:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            part_mmaps.append(mm)
        except Exception as e:
            print(f"[warn] mmap failed for {p}: {e}, reading into memory", file=sys.stderr)
            part_mmaps.append(f.read())
            f.close()
            part_files[-1] = None
        part_offsets.append(total)
        total += len(part_mmaps[-1])

    print(f"PROGRESS:30", flush=True)
    print(f"Extracting HEVC to temp file...", file=sys.stderr)

    # Extract HEVC directly to a temp file (avoids storing GBs in memory)
    hevc_tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.h265')
    hevc_tmp_path = hevc_tmp.name
    try:
        extract_hevc_to_file(part_mmaps, part_offsets, hevc_tmp)
        hevc_tmp.close()

        print(f"PROGRESS:85", flush=True)
        hevc_size = os.path.getsize(hevc_tmp_path)
        print(f"Splitting stereo ({hevc_size} bytes HEVC) from file...", file=sys.stderr)

        with open(hevc_tmp_path, "rb") as hevc_file:
            left_frames, right_frames = split_stereo_to_files(hevc_file, left_out, right_out)

        print(f"PROGRESS:95", flush=True)
        print(f"Wrote left -> {left_out}", file=sys.stderr)
        if right_out:
            print(f"Wrote right -> {right_out}", file=sys.stderr)
    finally:
        try:
            os.unlink(hevc_tmp_path)
        except Exception:
            pass

    # Cleanup
    for mm in part_mmaps:
        if isinstance(mm, mmap.mmap):
            mm.close()
    for f in part_files:
        if f is not None:
            f.close()

    print(f"PROGRESS:100", flush=True)
    print(f"DONE:{left_frames}:{right_frames}", flush=True)


if __name__ == "__main__":
    main()
