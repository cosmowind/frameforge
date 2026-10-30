#!/usr/bin/env node
// hmd2mp4.js — batch convert .hmd → .mp4 using ffmpeg.
//
// Usage:
//   node hmd2mp4.js <input.hmd> [more.hmd ...]
//   node hmd2mp4.js --dedup <input.hmd> ...     # drop repeated VPS/SPS/PPS, cleaner MP4
//   node hmd2mp4.js --color <input.hmd> ...     # also tag full-range BT.709 in container
//   node hmd2mp4.js --h265 <input.hmd> ...      # also emit .h265
//   node hmd2mp4.js --imu <input.hmd> ...       # also emit _imu.json
//
// Requires: node ≥ 18, ffmpeg in PATH or set FFMPEG env var.

const fs = require('fs');
const { spawnSync } = require('child_process');
const { parse, dedupParamSets } = require('./hmd-decode.js');

const FFMPEG = process.env.FFMPEG || 'ffmpeg';

function help() {
  console.log(`hmd2mp4.js — convert Galaxea HMD recordings to MP4

Usage:
  node hmd2mp4.js <input.hmd> [more.hmd ...]
      Convert each .hmd to a same-basename .mp4 (raw bitstream copy, fastest).

  --dedup   Drop the VPS/SPS/PPS that the encoder prepends to every
            video packet. Produces a cleaner MP4 without "Duplicate
            POC" warnings. Recommended.

  --color   Tag the output MP4 with explicit color metadata
            (BT.709 full range). Some players need this to render
            the yuvj420p stream correctly.

  --h265    Also write the extracted raw HEVC bitstream as <name>.h265
  --imu     Also write the IMU samples as <name>_imu.json

Examples:
  node hmd2mp4.js --dedup --color session_00000/part_000.hmd
  node hmd2mp4.js --dedup session_00000/part_*.hmd`);
  process.exit(0);
}

const args = process.argv.slice(2);
if (!args.length || args.includes('-h') || args.includes('--help')) help();

let dedup = args.includes('--dedup');
let color = args.includes('--color');
let wantHevc = args.includes('--h265');
let wantImu = args.includes('--imu');
const inputs = args.filter(a => !a.startsWith('-'));

(async () => {
  for (const f of inputs) await convertOne(f);
})().catch(e => { console.error(e); process.exit(1); });

async function convertOne(file) {
  console.log(`\n→ ${file}`);
  const t0 = Date.now();
  const buf = fs.readFileSync(file);
  const r = await parse(buf);
  console.log(`  parsed ${(buf.length/1024/1024).toFixed(1)} MB in ${Date.now()-t0} ms, packets=${r.stats.packets}`);
  let hevc = r.video[0].hevc;
  const v = r.video[0];
  console.log(`  HEVC: ${(hevc.length/1024/1024).toFixed(1)} MB, ${v.packets} packets, VPS=${!!v.vps} SPS=${!!v.sps} PPS=${!!v.pps}, IMU=${r.imu.length}`);

  if (dedup) {
    const before = hevc.length;
    hevc = dedupParamSets(hevc);
    console.log(`  dedup: ${(before/1024/1024).toFixed(1)} → ${(hevc.length/1024/1024).toFixed(1)} MB`);
  }

  const outHevc = file.replace(/\.hmd$/i, '') + '.h265';
  const outMp4 = file.replace(/\.hmd$/i, '') + '.mp4';
  const outImu = file.replace(/\.hmd$/i, '') + '_imu.json';

  if (wantHevc) {
    fs.writeFileSync(outHevc, hevc);
    console.log(`  ✓ ${outHevc} (${(hevc.length/1024/1024).toFixed(1)} MB)`);
  }
  if (wantImu) {
    const imu = r.imu.map(s => ({ seq: s.seq, t_us: s.t_us, raw_b64: Buffer.from(s.raw).toString('base64') }));
    fs.writeFileSync(outImu, JSON.stringify(imu, null, 2));
    console.log(`  ✓ ${outImu} (${r.imu.length} samples)`);
  }

  console.log(`  → ffmpeg remux → ${outMp4}`);
  const ffArgs = [
    '-y', '-loglevel', 'error',
    '-f', 'hevc', '-framerate', '30', '-i', 'pipe:0',
    '-c:v', 'copy', '-tag:v', 'hvc1',
  ];
  if (color) {
    // Force full-range + BT.709 even if SPS says otherwise
    ffArgs.push('-bsf:v', 'hevc_metadata=video_full_range_flag=1:colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1');
  }
  ffArgs.push(outMp4);

  const proc = spawnSync(FFMPEG, ffArgs, { input: hevc, maxBuffer: 1024 * 1024 * 1024 });
  if (proc.status !== 0) {
    console.error('  ✗ ffmpeg failed:', proc.stderr?.toString());
  } else {
    const sz = fs.statSync(outMp4).size;
    console.log(`  ✓ ${outMp4} (${(sz/1024/1024).toFixed(1)} MB)`);
  }
}
