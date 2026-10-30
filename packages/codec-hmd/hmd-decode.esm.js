// hmd-decode.esm.js — browser-friendly ESM build of hmd-decode.
// Mirrors hmd-decode.js: extracts HEVC (60 fps frame-interleaved stereo)
// + IMU from Galaxea HMD container files.
//
// ACTUAL FILE LAYOUT (verified 2026-06-16):
//   Real HMD3 packet headers:
//     - 0x59 (IMU, fixed 97 bytes total)
//     - 0x5a (Galaxea glue, 8-byte header)
//     - 0xfd (per-GOP HEVC chunk, 27-byte header + VPS/SPS/PPS/IDR/P-frames)
//
//   Camera HEVC: Annex-B NAL units (00 00 00 01 ...) come from
//     - "Gap" regions: bytes between HMD3 packet headers
//     - "0xfd payload": bytes inside 0xfd packets, after the 27-byte header
//   Concatenating both gives the full HEVC bitstream (60 fps frame-interleaved
//   stereo: even frames = camera 0 / left eye, odd frames = camera 1 / right eye).
//
//   All other "HMD3" sequences (76k+ in 256 MB) are HEVC-payload noise.

const MAGIC = [0x55, 0x4d, 0x49, 0x33];
const IMU_TYPE = 0x59;
const GLUE_TYPE = 0x5a;
const CHUNK_TYPE = 0xfd;
const KNOWN_PACKET_TYPES = new Set([IMU_TYPE, GLUE_TYPE, CHUNK_TYPE]);

const HEADER_LEN = 8;
const IMU_TOTAL = 97;
const GLUE_HEADER = 8;
const CHUNK_HEADER = 27;

function findPackets(buf) {
  const real = [];
  for (let p = 0; p + HEADER_LEN <= buf.length; p++) {
    if (buf[p] !== MAGIC[0] || buf[p+1] !== MAGIC[1] ||
        buf[p+2] !== MAGIC[2] || buf[p+3] !== MAGIC[3]) continue;
    const t = buf[p+4];
    if (t === IMU_TYPE || t === GLUE_TYPE) {
      if (buf[p+5] === 0 && buf[p+6] === 0 && buf[p+7] === 0) {
        real.push({ offset: p, type: t });
      }
    } else if (t === CHUNK_TYPE) {
      if (buf[p+6] === 0 && buf[p+7] === 0 &&
          buf[p+8] === 0x86 && buf[p+9] === 0x01) {
        real.push({ offset: p, type: t });
      }
    }
  }
  return real;
}

async function parse(input, opts = {}) {
  const onProgress = opts.onProgress || (() => {});
  const parts = Array.isArray(input) ? input : [input];
  const buffers = parts.map(p => p instanceof Uint8Array ? p : new Uint8Array(p));
  const offsets = [];
  let totalLen = 0;
  for (const b of buffers) { offsets.push(totalLen); totalLen += b.length; }

  const stats = {
    parts: buffers.length,
    realPackets: 0,
    imu: 0, glue: 0, chunkPackets: 0,
    hevcStartCodes: 0, hevcBytes: 0,
  };

  const hevcChunks = [];
  const params = {};
  const imu = [];

  function locate(off) {
    let lo = 0, hi = offsets.length - 1;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if (offsets[mid] <= off) lo = mid; else hi = mid - 1;
    }
    return { buf: buffers[lo], localOff: off - offsets[lo] };
  }

  const allPackets = [];
  for (let pi = 0; pi < buffers.length; pi++) {
    const local = findPackets(buffers[pi]);
    for (const p of local) allPackets.push({ offset: p.offset + offsets[pi], type: p.type });
  }
  allPackets.sort((a, b) => a.offset - b.offset);
  stats.realPackets = allPackets.length;

  let cursor = 0;
  for (let i = 0; i < allPackets.length; i++) {
    if ((i & 0xff) === 0) onProgress(i / allPackets.length);
    const pkt = allPackets[i];
    const p = pkt.offset;
    let pktEnd;
    if (pkt.type === IMU_TYPE) pktEnd = p + IMU_TOTAL;
    else if (pkt.type === GLUE_TYPE) pktEnd = p + GLUE_HEADER;
    else if (pkt.type === CHUNK_TYPE) pktEnd = allPackets[i + 1] ? allPackets[i + 1].offset : totalLen;
    else pktEnd = p + HEADER_LEN;

    if (p > cursor) {
      pushRange(hevcChunks, cursor, p, locate);
      stats.hevcBytes += p - cursor;
    }

    if (pkt.type === IMU_TYPE) {
      const loc = locate(p);
      const buf = loc.buf;
      const seq = buf[loc.localOff + 16] | (buf[loc.localOff + 17] << 8) |
                  (buf[loc.localOff + 18] << 16) | (buf[loc.localOff + 19] << 24);
      const tLow = buf[loc.localOff + 20] | (buf[loc.localOff + 21] << 8) |
                   (buf[loc.localOff + 22] << 16);
      imu.push({ seq, t_us: tLow, raw: buf.subarray(loc.localOff + HEADER_LEN, loc.localOff + IMU_TOTAL) });
      stats.imu++;
    } else if (pkt.type === GLUE_TYPE) {
      const hevcStart = p + GLUE_HEADER;
      if (hevcStart < pktEnd) {
        pushRange(hevcChunks, hevcStart, pktEnd, locate);
        stats.hevcBytes += pktEnd - hevcStart;
      }
      stats.glue++;
    } else if (pkt.type === CHUNK_TYPE) {
      const hevcStart = p + CHUNK_HEADER;
      if (hevcStart < pktEnd) {
        pushRange(hevcChunks, hevcStart, pktEnd, locate);
        stats.hevcBytes += pktEnd - hevcStart;
      }
      stats.chunkPackets++;
    }

    cursor = pktEnd;
  }
  if (cursor < totalLen) {
    pushRange(hevcChunks, cursor, totalLen, locate);
    stats.hevcBytes += totalLen - cursor;
  }

  onProgress(0.9);

  function concat(chunks) {
    let total = 0;
    for (const c of chunks) total += c.length;
    const out = new Uint8Array(total);
    let off = 0;
    for (const c of chunks) { out.set(c, off); off += c.length; }
    return out;
  }

  function captureParams(hevc, params) {
    let i = 0;
    while (i < hevc.length - 3) {
      if (hevc[i] === 0 && hevc[i+1] === 0 && hevc[i+2] === 0 && hevc[i+3] === 1) {
        const nalStart = i;
        let j = i + 4;
        while (j < hevc.length - 3) {
          if (hevc[j] === 0 && hevc[j+1] === 0 && hevc[j+2] === 0 && hevc[j+3] === 1) break;
          if (hevc[j] === 0 && hevc[j+1] === 0 && hevc[j+2] === 1) break;
          j++;
        }
        const nal = hevc.subarray(nalStart, j);
        const nalType = (nal[4] >> 1) & 0x3f;
        if (nalType === 32 && !params.vps) params.vps = nal;
        else if (nalType === 33 && !params.sps) params.sps = nal;
        else if (nalType === 34 && !params.pps) params.pps = nal;
        i = j;
      } else i++;
    }
  }

  const hevc = concat(hevcChunks);
  captureParams(hevc, params);

  for (let i = 0; i < hevc.length - 3; i++) {
    if (hevc[i] === 0 && hevc[i+1] === 0 && hevc[i+2] === 0 && hevc[i+3] === 1) stats.hevcStartCodes++;
  }

  onProgress(1);
  return {
    video: [{ packets: stats.hevcStartCodes, hevc, vps: params.vps, sps: params.sps, pps: params.pps }],
    imu,
    stats,
  };
}

function pushRange(chunks, from, to, locate) {
  let cursor = from;
  while (cursor < to) {
    const { buf, localOff } = locate(cursor);
    const partRemaining = buf.length - localOff;
    const slice = Math.min(partRemaining, to - cursor);
    chunks.push(buf.subarray(localOff, localOff + slice));
    cursor += slice;
  }
}

function splitNals(hevc) {
  const out = [];
  let i = 0;
  while (i < hevc.length - 3) {
    if (hevc[i] === 0 && hevc[i+1] === 0 && hevc[i+2] === 0 && hevc[i+3] === 1) {
      let j = i + 4;
      while (j < hevc.length - 3) {
        if (hevc[j] === 0 && hevc[j+1] === 0 && hevc[j+2] === 0 && hevc[j+3] === 1) break;
        if (hevc[j] === 0 && hevc[j+1] === 0 && hevc[j+2] === 1) break;
        j++;
      }
      const nalType = (hevc[i+4] >> 1) & 0x3f;
      out.push({ nalType, data: hevc.subarray(i, j) });
      i = j;
    } else i++;
  }
  return out;
}

function dedupParamSets(hevc) {
  const nals = splitNals(hevc);
  const out = [];
  let vpsKept = false, spsKept = false, ppsKept = false;
  let total = 0;
  for (const nal of nals) {
    if (nal.nalType === 32) { if (vpsKept) continue; vpsKept = true; }
    else if (nal.nalType === 33) { if (spsKept) continue; spsKept = true; }
    else if (nal.nalType === 34) { if (ppsKept) continue; ppsKept = true; }
    out.push(nal.data);
    total += nal.data.length;
  }
  const merged = new Uint8Array(total);
  let off = 0;
  for (const c of out) { merged.set(c, off); off += c.length; }
  return merged;
}

/**
 * Split a 60 fps frame-interleaved stereo HEVC stream into two 30 fps streams.
 * NAL index 0, 2, 4, ... → camera 0 (left); 1, 3, 5, ... → camera 1 (right).
 * Param sets (VPS/SPS/PPS) are prepended to both streams.
 */
function splitStereo(hevc) {
  const nals = splitNals(hevc);
  const left = [];
  const right = [];
  let frameIdx = 0, leftFrames = 0, rightFrames = 0;
  for (const nal of nals) {
    const isParamSet = nal.nalType === 32 || nal.nalType === 33 || nal.nalType === 34;
    if (isParamSet) {
      left.push(nal.data);
      right.push(nal.data);
      continue;
    }
    const target = (frameIdx % 2 === 0) ? left : right;
    target.push(nal.data);
    if (frameIdx % 2 === 0) leftFrames++; else rightFrames++;
    frameIdx++;
  }
  function concat(arr) {
    let total = 0;
    for (const c of arr) total += c.length;
    const out = new Uint8Array(total);
    let off = 0;
    for (const c of arr) { out.set(c, off); off += c.length; }
    return out;
  }
  return {
    left: concat(left),
    right: concat(right),
    stats: { leftFrames, rightFrames, totalFrames: frameIdx },
  };
}

export {
  parse, findPackets, splitNals, dedupParamSets, splitStereo,
  MAGIC, IMU_TYPE, GLUE_TYPE, CHUNK_TYPE, KNOWN_PACKET_TYPES,
  HEADER_LEN, IMU_TOTAL, GLUE_HEADER, CHUNK_HEADER,
};
export default { parse, findPackets, splitNals, dedupParamSets, splitStereo };