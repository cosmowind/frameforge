#!/usr/bin/env python3
"""Inspect a Foxglove MCAP file: schemas (with FileDescriptorSet bytes),
channels/topics, per-topic message counts, and overall statistics.

Used to verify that a .mcap produced by `hmd_to_mcap.js` (or by the
frameforge browser `hmdToMcap` upstream) conforms to the stereo session
shape the vendor MCAP delivery spec expects.

Usage:
    python tools/inspect_mcap.py path/to/session.mcap
    python tools/inspect_mcap.py path/to/session.mcap --json > out.json
    python tools/inspect_mcap.py path/to/session.mcap --quiet  # only summary

Requires: pip install mcap
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

try:
    from mcap.reader import make_reader as _make_reader
    _HAVE_MCAP = True
except ImportError:  # pragma: no cover
    _make_reader = None
    _HAVE_MCAP = False


def inspect(path: Path) -> dict:
    """Read the summary section + per-topic message counts of an MCAP.

    Returns a dict with keys:
      schemas:    [{id, name, encoding, fds_b64, fds_sha256}]
      channels:   [{id, topic, schema_id, message_encoding, metadata}]
      topics:     {topic: count}
      statistics: {message_count, schema_count, channel_count, chunk_count,
                   channel_message_counts}
    """
    if not _HAVE_MCAP:
        sys.exit('mcap python library not installed. Run: pip install mcap')
    if not path.is_file():
        sys.exit(f'no such file: {path}')

    import hashlib

    with open(path, 'rb') as fh:
        reader = _make_reader(fh)
        summ = reader.get_summary()

        schemas = []
        for s in summ.schemas.values():
            fds_bytes = bytes(s.data)
            schemas.append({
                'id': s.id,
                'name': s.name,
                'encoding': s.encoding,
                'fds_b64': base64.b64encode(fds_bytes).decode('ascii'),
                'fds_sha256': hashlib.sha256(fds_bytes).hexdigest(),
                'fds_bytes': len(fds_bytes),
            })

        channels = []
        for ch in summ.channels.values():
            channels.append({
                'id': ch.id,
                'topic': ch.topic,
                'schema_id': ch.schema_id,
                'message_encoding': ch.message_encoding,
                'metadata': dict(ch.metadata) if ch.metadata else {},
            })

        # Per-topic message counts: walk iter_messages once (cheap; the reader
        # uses chunk indexes when available so this is O(message_count)).
        topic_counts: dict[str, int] = {}
        for _schema, channel, _msg in reader.iter_messages():
            topic_counts[channel.topic] = topic_counts.get(channel.topic, 0) + 1

        statistics = {}
        if summ.statistics is not None:
            statistics = {
                'message_count': summ.statistics.message_count,
                'schema_count': summ.statistics.schema_count,
                'channel_count': summ.statistics.channel_count,
                'chunk_count': summ.statistics.chunk_count,
                'channel_message_counts': dict(summ.statistics.channel_message_counts or {}),
            }

    return {
        'path': str(path),
        'file_size_bytes': path.stat().st_size,
        'schemas': schemas,
        'channels': channels,
        'topics': dict(sorted(topic_counts.items())),
        'statistics': statistics,
    }


def _print_human_friendly(report: dict, quiet: bool) -> None:
    print(f'MCAP: {report["path"]}')
    print(f'  size: {report["file_size_bytes"] / 1e6:.2f} MB')
    if report['statistics']:
        st = report['statistics']
        print(f'  stats: messages={st["message_count"]}, '
              f'schemas={st["schema_count"]}, channels={st["channel_count"]}, '
              f'chunks={st["chunk_count"]}')
    print('  schemas:')
    for s in report['schemas']:
        print(f'    - id={s["id"]} name={s["name"]!r} encoding={s["encoding"]} '
              f'fds_bytes={s["fds_bytes"]} sha256={s["fds_sha256"][:16]}…')
    if not quiet:
        print('  channels:')
        for c in report['channels']:
            print(f'    - id={c["id"]} topic={c["topic"]!r} schema_id={c["schema_id"]} '
                  f'encoding={c["message_encoding"]}')
        print('  per-topic message counts:')
        for topic, n in report['topics'].items():
            print(f'    - {topic}: {n}')


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mcap', type=Path, help='path to the .mcap to inspect')
    ap.add_argument('--json', action='store_true', help='emit JSON instead of human-friendly text')
    ap.add_argument('--quiet', action='store_true', help='(human mode) only print summary, no channels/topics')
    args = ap.parse_args(argv)

    report = inspect(args.mcap)
    if args.json:
        # Don't dump the full FDS bytes by default in JSON — too noisy. Caller
        # can re-fetch via inspect() if they want them.
        out = dict(report)
        out['schemas'] = [
            {k: v for k, v in s.items() if k != 'fds_bytes'} for s in report['schemas']
        ]
        json.dump(out, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write('\n')
    else:
        _print_human_friendly(report, quiet=args.quiet)
    return 0


if __name__ == '__main__':
    sys.exit(main())
