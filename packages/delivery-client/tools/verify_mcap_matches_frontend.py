#!/usr/bin/env python3
"""Verify that a .mcap produced by `hmd_to_mcap.js` (this repo) matches what
the frameforge upstream browser converter `hmdToMcap` would produce.

What we check (in priority order):
  1. Schema names + encoding match the reference set:
        foxglove.CompressedVideo   (protobuf)
        google.protobuf.StringValue (protobuf)
  2. FileDescriptorSet bytes match the canonical reference (lifted from
     `F:/sys/o/frameforge/frameforge/frameforge/src/lib/mcap/proto.ts`).
     This is the strongest signal — protobuf descriptors must be byte-for-byte
     identical or downstream viewers / parsers may interpret messages wrong.
  3. Topic names match the vendor MCAP delivery spec:
        /top-left-camera/image-raw    foxglove.CompressedVideo
        /top-right-camera/image-raw   foxglove.CompressedVideo
        /head-imu                     google.protobuf.StringValue
  4. Per-topic message counts are in the expected 2:1:high range (stereo
     video is interleaved 60 fps, IMU rate > 200 Hz). The script doesn't
     assert exact ratios (recordings vary) — just that the video topic counts
     are equal and IMU is at least ~3× the per-eye frame rate.

Usage:
    # Verify a single .mcap produced by hmd_to_mcap.js
    python tools/verify_mcap_matches_frontend.py path/to/session.mcap

    # Compare two .mcaps (e.g. one from our pipeline, one from frameforge UI)
    python tools/verify_mcap_matches_frontend.py ours.mcap --against theirs.mcap

    # CI mode: exit 1 on any mismatch
    python tools/verify_mcap_matches_frontend.py --strict session.mcap

Reference FDS strings are hard-coded below from
`frameforge/src/lib/mcap/proto.ts` (COMPRESSED_VIDEO_FDS_B64 /
STRING_VALUE_FDS_B64). If upstream changes them, regenerate this file's
constants by re-running `git show origin/master:frameforge/src/lib/mcap/proto.ts`
and copy-pasting the new base64 strings.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import sys
from pathlib import Path

try:
    from mcap.reader import make_reader as _make_reader
    _HAVE_MCAP = True
except ImportError:  # pragma: no cover
    _make_reader = None
    _HAVE_MCAP = False


# ─── Reference constants (lifted from frameforge/src/lib/mcap/proto.ts) ─────

# Canonical FileDescriptorSet base64 strings for the two schemas the stereo
# session uses. MUST stay in sync with frameforge upstream — if upstream
# regenerates them, re-copy the constants here.
COMPRESSED_VIDEO_FDS_B64_REF = (
    'Cv8BCh9nb29nbGUvcHJvdG9idWYvdGltZXN0YW1wLnByb3RvEg9nb29nbGUucHJvdG9idWYiOwoJ' +
    'VGltZXN0YW1wEhgKB3NlY29uZHMYASABKANSB3NlY29uZHMSFAoFbmFub3MYAiABKAVSBW5hbm9z' +
    'QoUBChNjb20uZ29vZ2xlLnByb3RvYnVmQg5UaW1lc3RhbXBQcm90b1ABWjJnb29nbGUuZ29sYW5n' +
    'Lm9yZy9wcm90b2J1Zi90eXBlcy9rbm93bi90aW1lc3RhbXBwYvgBAaICA0dQQqoCHkdvb2dsZS5Q' +
    'cm90b2J1Zi5XZWxsS25vd25UeXBlc2IGcHJvdG8zCsUBCh5mb3hnbG92ZS9Db21wcmVzc2VkVmlk' +
    'ZW8ucHJvdG8SCGZveGdsb3ZlGh9nb29nbGUvcHJvdG9idWYvdGltZXN0YW1wLnByb3RvInAKD0Nv' +
    'bXByZXNzZWRWaWRlbxItCgl0aW1lc3RhbXAYASABKAsyGi5nb29nbGUucHJvdG9idWYuVGltZXN0' +
    'YW1wEhAKCGZyYW1lX2lkGAIgASgJEgwKBGRhdGEYAyABKAwSDgoGZm9ybWF0GAQgASgJYgZwcm90' +
    'bzM='
)
STRING_VALUE_FDS_B64_REF = (
    'CoYECh5nb29nbGUvcHJvdG9idWYvd3JhcHBlcnMucHJvdG8SD2dvb2dsZS5wcm90b2J1ZiIjCgtE' +
    'b3VibGVWYWx1ZRIUCgV2YWx1ZRgBIAEoAVIFdmFsdWUiIgoKRmxvYXRWYWx1ZRIUCgV2YWx1ZRgB' +
    'IAEoAlIFdmFsdWUiIgoKSW50NjRWYWx1ZRIUCgV2YWx1ZRgBIAEoA1IFdmFsdWUiIwoLVUludDY0' +
    'VmFsdWUSFAoFdmFsdWUYASABKARSBXZhbHVlIiIKCkludDMyVmFsdWUSFAoFdmFsdWUYASABKAVS' +
    'BXZhbHVlIiMKC1VJbnQzMlZhbHVlEhQKBXZhbHVlGAEgASgNUgV2YWx1ZSIhCglCb29sVmFsdWUS' +
    'FAoFdmFsdWUYASABKAhSBXZhbHVlIiMKC1N0cmluZ1ZhbHVlEhQKBXZhbHVlGAEgASgJUgV2YWx1' +
    'ZSIiCgpCeXRlc1ZhbHVlEhQKBXZhbHVlGAEgASgMUgV2YWx1ZUKDAQoTY29tLmdvb2dsZS5wcm90' +
    'b2J1ZkINV3JhcHBlcnNQcm90b1ABWjFnb29nbGUuZ29sYW5nLm9yZy9wcm90b2J1Zi90eXBlcy9r' +
    'bm93bi93cmFwcGVyc3Bi+AEBogIDR1BCqgIeR29vZ2xlLlByb3RvYnVmLldlbGxLbm93blR5cGVz' +
    'YgZwcm90bzM='
)

COMPRESSED_VIDEO_FDS_REF = base64.b64decode(COMPRESSED_VIDEO_FDS_B64_REF)
STRING_VALUE_FDS_REF = base64.b64decode(STRING_VALUE_FDS_B64_REF)

EXPECTED_TOPICS = {
    '/top-left-camera/image-raw': 'foxglove.CompressedVideo',
    '/top-right-camera/image-raw': 'foxglove.CompressedVideo',
    '/head-imu': 'google.protobuf.StringValue',
}

EXPECTED_SCHEMAS = {
    'foxglove.CompressedVideo',
    'google.protobuf.StringValue',
}


# ─── Per-MCAP report (extracted from the MCAP file) ─────────────────────────

def _report_mcap(path: Path) -> dict:
    """Read schemas + topics out of a .mcap for comparison."""
    if not _HAVE_MCAP:
        sys.exit('mcap python library not installed. Run: pip install mcap')
    if not path.is_file():
        sys.exit(f'no such file: {path}')

    with open(path, 'rb') as fh:
        reader = _make_reader(fh)
        summ = reader.get_summary()

        schemas_by_name: dict[str, dict] = {}
        for s in summ.schemas.values():
            fds_bytes = bytes(s.data)
            schemas_by_name[s.name] = {
                'name': s.name,
                'encoding': s.encoding,
                'fds_sha256': hashlib.sha256(fds_bytes).hexdigest(),
                'fds_bytes': fds_bytes,
            }
        topic_to_schema: dict[str, str] = {}
        for ch in summ.channels.values():
            sch = summ.schemas.get(ch.schema_id) if ch.schema_id else None
            if sch is not None:
                topic_to_schema[ch.topic] = sch.name

        topic_counts: dict[str, int] = {}
        for _schema, channel, _msg in reader.iter_messages():
            topic_counts[channel.topic] = topic_counts.get(channel.topic, 0) + 1

    return {
        'path': str(path),
        'schemas': schemas_by_name,
        'topic_to_schema': topic_to_schema,
        'topic_counts': topic_counts,
    }


def _compare(a: dict, b: dict | None) -> list[tuple[str, str, str]]:
    """Return a list of (severity, code, detail) tuples for mismatches.

    severity: 'error' or 'warn'. The script returns 1 if any 'error' is
    emitted (in --strict mode).
    """
    issues: list[tuple[str, str, str]] = []

    # 1. Schema set completeness.
    schema_names = set(a['schemas'].keys())
    missing = EXPECTED_SCHEMAS - schema_names
    if missing:
        issues.append(('error', 'schema_missing',
                       f'missing schema(s): {sorted(missing)} (found {sorted(schema_names)})'))

    # 2. FDS byte-exact match against the upstream reference.
    for schema_name, ref_bytes in [
        ('foxglove.CompressedVideo', COMPRESSED_VIDEO_FDS_REF),
        ('google.protobuf.StringValue', STRING_VALUE_FDS_REF),
    ]:
        sch = a['schemas'].get(schema_name)
        if sch is None:
            continue
        if sch['fds_bytes'] != ref_bytes:
            issues.append((
                'error', 'fds_mismatch',
                f'{schema_name} FileDescriptorSet bytes differ from upstream reference; '
                f'sha256 ours={sch["fds_sha256"][:16]}… (if upstream changed, '
                're-copy the new base64 string from frameforge/src/lib/mcap/proto.ts)',
            ))
        else:
            issues.append(('ok', 'fds_match',
                           f'{schema_name} FDS bytes match upstream reference '
                           f'(sha256={sch["fds_sha256"][:16]}…)'))

    # 3. Topic names + per-topic schema.
    for topic, schema_name in EXPECTED_TOPICS.items():
        actual_schema = a['topic_to_schema'].get(topic)
        if actual_schema is None:
            issues.append(('error', 'topic_missing',
                           f'expected topic {topic!r} not found'))
        elif actual_schema != schema_name:
            issues.append((
                'error', 'topic_schema_mismatch',
                f'topic {topic!r} uses schema {actual_schema!r}, expected {schema_name!r}',
            ))
        else:
            issues.append(('ok', 'topic_match',
                           f'topic {topic!r} → {schema_name!r}'))

    # 4. Video topic counts should be equal (stereo is frame-interleaved).
    left_count = a['topic_counts'].get('/top-left-camera/image-raw', 0)
    right_count = a['topic_counts'].get('/top-right-camera/image-raw', 0)
    if left_count != right_count:
        issues.append((
            'warn', 'video_count_imbalance',
            f'left={left_count} right={right_count} (should be equal for frame-interleaved stereo)',
        ))
    elif left_count == 0:
        issues.append(('warn', 'no_video_messages', 'no messages on either video topic'))
    else:
        issues.append(('ok', 'video_counts',
                       f'left={left_count} right={right_count}'))

    # 5. IMU should be present and at least ~3× per-eye rate (200 Hz vs 30 fps per eye).
    imu_count = a['topic_counts'].get('/head-imu', 0)
    if imu_count == 0:
        issues.append(('warn', 'no_imu', 'no messages on /head-imu topic'))
    elif left_count > 0 and imu_count < left_count * 3:
        issues.append((
            'warn', 'low_imu_rate',
            f'/head-imu has {imu_count} msgs vs {left_count} per-eye video frames — '
            f'IMU rate looks low (expect ≥ 3× the per-eye frame rate)',
        ))
    else:
        issues.append(('ok', 'imu_present', f'/head-imu has {imu_count} msgs'))

    # 6. If a second MCAP was given, compare schema sets + per-topic counts.
    if b is not None:
        a_topics = set(a['topic_to_schema'].keys())
        b_topics = set(b['topic_to_schema'].keys())
        if a_topics != b_topics:
            only_a = a_topics - b_topics
            only_b = b_topics - a_topics
            issues.append((
                'error', 'topic_set_diff',
                f'topic set differs — only in ours: {sorted(only_a)}, only in theirs: {sorted(only_b)}',
            ))
        for topic in a_topics & b_topics:
            if a['topic_to_schema'][topic] != b['topic_to_schema'][topic]:
                issues.append((
                    'error', 'topic_schema_diff',
                    f'topic {topic!r}: ours schema={a["topic_to_schema"][topic]!r}, '
                    f'theirs schema={b["topic_to_schema"][topic]!r}',
                ))
        for topic in a['topic_counts'].keys() & b['topic_counts'].keys():
            a_n, b_n = a['topic_counts'][topic], b['topic_counts'][topic]
            if a_n != b_n:
                issues.append((
                    'warn', 'count_diff',
                    f'topic {topic!r}: ours={a_n} msgs, theirs={b_n} msgs '
                    f'(delta {abs(a_n - b_n)})',
                ))

    return issues


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mcap', type=Path, help='path to the .mcap produced by hmd_to_mcap.js')
    ap.add_argument('--against', type=Path, default=None,
                    help='optional second .mcap (e.g. produced by frameforge UI) for pairwise comparison')
    ap.add_argument('--strict', action='store_true',
                    help='exit 1 on any error-level mismatch (default: warn only)')
    args = ap.parse_args(argv)

    ours = _report_mcap(args.mcap)
    theirs = _report_mcap(args.against) if args.against else None
    issues = _compare(ours, theirs)

    n_error = sum(1 for sev, _, _ in issues if sev == 'error')
    n_warn = sum(1 for sev, _, _ in issues if sev == 'warn')
    n_ok = sum(1 for sev, _, _ in issues if sev == 'ok')

    for sev, code, detail in issues:
        prefix = {'error': 'ERROR', 'warn': 'WARN ', 'ok': 'OK   '}[sev]
        print(f'  {prefix} [{code}] {detail}')
    print()
    print(f'summary: {n_ok} ok, {n_warn} warn, {n_error} error')

    if n_error > 0:
        print(f'fail: {n_error} mismatch(es) detected against the frameforge upstream reference.')
        return 1
    if n_warn > 0:
        print(f'pass with warnings: {n_warn} warning(s); review before shipping.')
        return 0
    print('pass: mcap is consistent with the frameforge upstream reference.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
