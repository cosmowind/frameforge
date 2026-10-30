#!/usr/bin/env node
// verify_hmd_packets.js — self-test for the corrected hmd-decode.js
//
// Usage:
//   node verify_hmd_packets.js [path/to/part_XXX.hmd]
//
// Default: session_00000/part_000.hmd
// Exit 0 = pass, non-zero = fail.

const fs = require('fs');
const path = require('path');
const { parse, findPackets, MAGIC, IMU_TYPE, GLUE_TYPE, CHUNK_TYPE, dedupParamSets, splitStereo } = require('./hmd-decode.js');

// Usage: node verify_hmd_packets.js [part_000.hmd part_001.hmd ...]
// If only one arg given and it's a directory, auto-load all part_*.hmd from it.
const args = process.argv.slice(2);
let targetPaths;
if (args.length === 1 && fs.statSync(args[0]).isDirectory()) {
  const dir = args[0];
  targetPaths = fs.readdirSync(dir)
    .filter(f => f.startsWith('part_') && f.endsWith('.hmd'))
    .sort()
    .map(f => path.join(dir, f));
} else {
  targetPaths = args.length ? args : ['session_00000/part_000.hmd'];
}
const buffers = targetPaths.map(p => new Uint8Array(fs.readFileSync(p)));
const totalSize = buffers.reduce((a, b) => a + b.length, 0);

console.log(`=== verify_hmd_packets.js on ${targetPaths.join(' + ')} ===`);
console.log(`total parts: ${buffers.length}, total size: ${totalSize} bytes (${(totalSize / 1024 / 1024).toFixed(1)} MB)`);

let failures = 0;
function check(name, ok, info) {
  const tag = ok ? '[32mPASS[0m' : '[31mFAIL[0m';
  console.log(`  [${tag}] ${name}${info ? ' — ' + info : ''}`);
  if (!ok) failures++;
}

// ---- findPackets ----
const t0 = Date.now();
let allPackets = [];
for (let i = 0; i < buffers.length; i++) {
  const local = findPackets(buffers[i]);
  for (const p of local) allPackets.push({ ...p, _part: i });
}
const tFind = Date.now() - t0;
console.log(`\nfindPackets: ${allPackets.length} real packets in ${tFind} ms`);

check('real packet count is sane (1 — 1e6)',
  allPackets.length > 1 && allPackets.length < 1e6,
  `got ${allPackets.length}`);

const imuPackets = allPackets.filter(p => p.type === IMU_TYPE);
const gluePackets = allPackets.filter(p => p.type === GLUE_TYPE);
const chunkPackets = allPackets.filter(p => p.type === CHUNK_TYPE);
console.log(`  IMU (0x59): ${imuPackets.length}, GLUE (0x5a): ${gluePackets.length}, CHUNK (0xfd): ${chunkPackets.length}`);

check('IMU packets are 97 bytes apart (contiguous, where present)',
  imuPackets.length < 2 || imuPackets[1].offset - imuPackets[0].offset === 97);

// ---- parse ----
async function main() {
const t1 = Date.now();
const r = await parse(buffers, { onProgress: () => {} });
const tParse = Date.now() - t1;
console.log(`\nparse: ${tParse} ms`);
console.log(`  stats: ${JSON.stringify(r.stats)}`);

check('parse reports non-zero IMU samples', r.stats.imu > 0, `got ${r.stats.imu}`);
check('parse reports non-zero glue packets', r.stats.glue > 0, `got ${r.stats.glue}`);
check('parse reports non-zero chunk packets', r.stats.chunkPackets > 0, `got ${r.stats.chunkPackets}`);
check('parse reports 19,000+ HEVC start codes',
  r.stats.hevcStartCodes >= 19000,
  `got ${r.stats.hevcStartCodes}`);

check('hevc byte stream is non-empty (>100 MB)', r.video[0].hevc.length > 100 * 1024 * 1024,
  `${(r.video[0].hevc.length / 1024 / 1024).toFixed(1)} MB`);

check('VPS/SPS/PPS present', !!r.video[0].vps && !!r.video[0].sps && !!r.video[0].pps);
check('VPS NAL type is 32', r.video[0].vps && ((r.video[0].vps[4] >> 1) & 0x3f) === 32);
check('SPS NAL type is 33', r.video[0].sps && ((r.video[0].sps[4] >> 1) & 0x3f) === 33);
check('PPS NAL type is 34', r.video[0].pps && ((r.video[0].pps[4] >> 1) & 0x3f) === 34);

// ---- cross-check: HEVC bytes + HMD3 packet bytes = total file size ----
let hmdBytes = 0;
for (const p of allPackets) {
  if (p.type === IMU_TYPE) hmdBytes += 97;
  else if (p.type === GLUE_TYPE) hmdBytes += 8;
  // CHUNK: counted in HEVC payload total since the chunk header (27 bytes) is part of HEVC stream
}
const reconstructed = r.stats.hevcBytes + hmdBytes;
check('hevc + umi3-packet bytes = total file size',
  reconstructed === totalSize,
  `hevc=${r.stats.hevcBytes} + umi3=${hmdBytes} = ${reconstructed}, total=${totalSize}`);

// ---- dedupParamSets ----
const tDedup = Date.now();
const dedup = dedupParamSets(r.video[0].hevc);
const tDedupMs = Date.now() - tDedup;
console.log(`\ndedupParamSets: ${(dedup.length / 1024 / 1024).toFixed(1)} MB in ${tDedupMs} ms`);
check('dedup output is smaller than input',
  dedup.length < r.video[0].hevc.length,
  `${dedup.length} < ${r.video[0].hevc.length}`);

// ---- splitStereo (60 fps frame-interleaved → 2 × 30 fps) ----
const stereo = splitStereo(dedup);
console.log(`\nsplitStereo: left=${stereo.stats.leftFrames} frames, right=${stereo.stats.rightFrames} frames, total=${stereo.stats.totalFrames}`);
check('splitStereo total frames = HEVC frame count',
  stereo.stats.leftFrames + stereo.stats.rightFrames === stereo.stats.totalFrames);
check('left and right frame counts are balanced (±1)',
  Math.abs(stereo.stats.leftFrames - stereo.stats.rightFrames) <= 1,
  `|${stereo.stats.leftFrames} - ${stereo.stats.rightFrames}| = ${Math.abs(stereo.stats.leftFrames - stereo.stats.rightFrames)}`);
check('splitStereo output bytes are non-empty',
  stereo.left.length > 10 * 1024 * 1024 && stereo.right.length > 10 * 1024 * 1024,
  `left=${(stereo.left.length/1024/1024).toFixed(1)}MB right=${(stereo.right.length/1024/1024).toFixed(1)}MB`);
check('splitStereo outputs are different (proves they are different views)',
  stereo.left.length !== stereo.right.length ||
  Buffer.compare(Buffer.from(stereo.left), Buffer.from(stereo.right)) !== 0);

// ---- frame count ----
let idrCount = 0;
{
  const h = r.video[0].hevc;
  let p = 0;
  while (p + 4 < h.length) {
    if (h[p] === 0 && h[p+1] === 0 && h[p+2] === 0 && h[p+3] === 1) {
      if (((h[p+4] >> 1) & 0x3f) === 19) idrCount++;
      p += 4;
    } else p++;
  }
}
console.log(`  IDR (NAL 19) count: ${idrCount}`);

// ---- summary ----
console.log(`\n=== ${failures === 0 ? 'ALL PASSED' : failures + ' FAILED'} ===`);
process.exit(failures === 0 ? 0 : 1);
}

main().catch(e => { console.error(e); process.exit(2); });
