// hmd-player-core.js
// ESM module for video-sort-package. Wraps hmd-decode.esm.js with
// WebCodecs VideoDecoder playback helpers.
//
// Usage:
//   import { openHmdSession } from '/static/hmd/hmd-player-core.js';
//   const session = await openHmdSession({
//     parts: [uint8Array1, uint8Array2, ...],  // pre-loaded Uint8Array per part
//     canvas: document.getElementById('canvas'),
//     fps: 30,
//     onFrame: (frameTimeSec) => { ... },
//     cameraIdx: 0,  // 0 or 1
//   });
//   session.play();
//   session.pause();
//   session.seek(sec);
//   session.close();
//
// Returns session info: { durationSec, nalCount, cameraIdx, codecStr,
//                        fps, width, height, isStereo, hasCamera1 }

import { parse, splitNals } from '/static/hmd/hmd-decode.esm.js';

// =====================================================================
// HEVC helpers (hvcC description, codec string)
// =====================================================================

function stripStartCode(nal) {
  return (nal[0] === 0 && nal[1] === 0 && nal[2] === 0 && nal[3] === 1)
    ? nal.subarray(4)
    : nal;
}

function concatBytes(arrs) {
  let t = 0;
  for (const a of arrs) t += a.length;
  const o = new Uint8Array(t);
  let p = 0;
  for (const a of arrs) { o.set(a, p); p += a.length; }
  return o;
}

/**
 * Build a HEVCDecoderConfigurationRecord (hvcC) for the
 * VideoDecoder.configure({ description }) call.
 */
function buildHevcDescription(vpsNal, spsNal, ppsNal) {
  const vpsBody = stripStartCode(vpsNal);
  const spsBody = stripStartCode(spsNal);
  const ppsBody = stripStartCode(ppsNal);

  const profile_space = (spsBody[3] >> 6) & 0x03;
  const tier_flag = (spsBody[3] >> 5) & 0x01;
  const profile_idc = spsBody[3] & 0x1f;
  const profile_compat = spsBody.subarray(4, 8);
  const constraint = new Uint8Array(6);
  constraint[0] = spsBody[8] & 0xf0;
  let level_idc = spsBody[14];
  if (level_idc === 0) level_idc = 120;  // Galaxea HMD: encoder leaves level unspecified

  const out = [];
  out.push(new Uint8Array([1]));
  out.push(new Uint8Array([(profile_space << 6) | (tier_flag << 5) | profile_idc]));
  out.push(profile_compat);
  out.push(constraint);
  out.push(new Uint8Array([level_idc]));
  out.push(new Uint8Array([0xf0, 0x00]));
  out.push(new Uint8Array([0xfc]));
  out.push(new Uint8Array([0xfd]));
  out.push(new Uint8Array([0xf8]));
  out.push(new Uint8Array([0xf8]));
  out.push(new Uint8Array([0, 0]));
  out.push(new Uint8Array([0x0f]));
  out.push(new Uint8Array([3]));

  out.push(new Uint8Array([0x20]));
  out.push(new Uint8Array([0, 1]));
  out.push(new Uint8Array([(vpsBody.length >> 8) & 0xff, vpsBody.length & 0xff]));
  out.push(vpsBody);

  out.push(new Uint8Array([0x21]));
  out.push(new Uint8Array([0, 1]));
  out.push(new Uint8Array([(spsBody.length >> 8) & 0xff, spsBody.length & 0xff]));
  out.push(spsBody);

  out.push(new Uint8Array([0x22]));
  out.push(new Uint8Array([0, 1]));
  out.push(new Uint8Array([(ppsBody.length >> 8) & 0xff, ppsBody.length & 0xff]));
  out.push(ppsBody);

  return concatBytes(out);
}

/**
 * Build WebCodecs codec string from SPS (Annex-B with start code).
 * Example: hev1.1.6.L93.B000000000
 */
function codecStringFromSps(sps) {
  if (sps.length < 22) return null;
  const o = (sps[0] === 0 && sps[1] === 0 && sps[2] === 0 && sps[3] === 1) ? 4 : 0;
  const profileIdc = sps[o + 3] & 0x1f;
  const compat = sps[o + 4];
  let level = sps[o + 14];
  if (level === 0) level = 120;
  let constraintHex = '';
  for (let i = 0; i < 6; i++) {
    let b = sps[o + 8 + i];
    if (i === 0) b = b & 0xf0;
    else b = 0;
    constraintHex += b.toString(16).padStart(2, '0');
  }
  return `hev1.${profileIdc}.${compat.toString(16).padStart(2, '0')}.L${level}.${constraintHex.toUpperCase()}`;
}

/**
 * Wrap an Annex-B NAL slice (in HEVC byte stream) into AVCC format:
 * 4-byte big-endian length prefix + body (no start code).
 */
function makeAvccChunk(hevc, nalStart, nalEnd) {
  const bodyLen = nalEnd - nalStart - 4;
  const out = new Uint8Array(4 + bodyLen);
  new DataView(out.buffer).setUint32(0, bodyLen, false);
  out.set(hevc.subarray(nalStart + 4, nalEnd), 4);
  return out;
}

// =====================================================================
// Public API
// =====================================================================

/**
 * Parse a multi-part HMD session and prepare WebCodecs decoder.
 *
 * @param {Object} opts
 * @param {Array<Uint8Array>} opts.parts - Pre-loaded Uint8Array per part
 * @param {HTMLCanvasElement} opts.canvas - Target canvas to draw frames
 * @param {number} [opts.fps=30] - Assumed FPS (HMD containers don't carry it)
 * @param {Function} [opts.onFrame] - (timeSec, frameCount) callback per draw
 * @param {Function} [opts.onError] - (err) callback for decode errors
 * @param {Function} [opts.onProgress] - (0..1) callback during parse
 * @param {number} [opts.cameraIdx=0] - 0 or 1
 * @returns {Promise<HmdSession>}
 */
export async function openHmdSession(opts) {
  const {
    parts,
    canvas,
    fps = 30,
    onFrame = null,
    onError = null,
    onProgress = null,
    cameraIdx = 0,
  } = opts;

  if (typeof VideoDecoder === 'undefined') {
    throw new Error('当前浏览器不支持 WebCodecs VideoDecoder（需 Edge 88+ / Chrome 94+）');
  }
  if (!canvas) throw new Error('canvas 不能为空');
  if (!parts || parts.length === 0) throw new Error('parts 不能为空');

  // 1) Concatenate all parts into one Uint8Array (HMD containers are linear)
  let totalLen = 0;
  for (const b of parts) totalLen += b.length;
  const combined = new Uint8Array(totalLen);
  let off = 0;
  for (const b of parts) { combined.set(b, off); off += b.length; }

  // 2) Parse via hmd-decode.esm.js
  const parsed = await parse(combined, {
    onProgress: onProgress || (() => {}),
  });

  const cam = parsed.video[cameraIdx];
  if (!cam || !cam.hevc || cam.hevc.length === 0) {
    throw new Error(`camera ${cameraIdx} 无 HEVC 数据`);
  }

  const hevc = cam.hevc;
  const vps = cam.vps, sps = cam.sps, pps = cam.pps;

  if (!vps || !sps || !pps) {
    throw new Error('未找到 VPS/SPS/PPS（不是合法的 HEVC 录像？）');
  }

  // 3) Split into NAL units (keep byte offsets in hevc for AVCC wrap)
  //    splitNals returns { nalType, data }, but data is already subarray — we
  //    need byte offsets. Re-scan manually.
  const nalInfos = [];  // { nalType, start, end }
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
      nalInfos.push({ nalType, start: i, end: j });
      i = j;
    } else i++;
  }

  const sliceNals = nalInfos.filter(n => n.nalType < 32);
  const idrIdxs = [];
  for (let k = 0; k < sliceNals.length; k++) {
    if (sliceNals[k].nalType === 19 || sliceNals[k].nalType === 20) idrIdxs.push(k);
  }

  const durationSec = sliceNals.length / fps;
  const FRAME_US = Math.round(1e6 / fps);
  const WIDTH = 1920;
  const HEIGHT = 1080;

  // 4) Set up canvas + decoder
  const ctx = canvas.getContext('2d');
  canvas.width = WIDTH;
  canvas.height = HEIGHT;
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, WIDTH, HEIGHT);

  const description = buildHevcDescription(vps, sps, pps);
  const codecStr = codecStringFromSps(sps) || 'hev1.1.6.L93.B0';

  // 5) Construct session object
  const session = {
    durationSec,
    nalCount: sliceNals.length,
    fps,
    width: WIDTH,
    height: HEIGHT,
    cameraIdx,
    codecStr,
    hasCamera1: parsed.video[1] && parsed.video[1].hevc.length > 0,
    isStereo: !!(parsed.video[1] && parsed.video[1].hevc.length > 0),
    imuCount: parsed.imu.length,

    // ── playback controls (filled below) ──
    playing: false,
    rate: 1.0,
    _decoder: null,
    _currentFrame: null,
    _nextNalIdx: 0,
    _pendingTs: 0,
    _lastFrameTime: 0,
    _frameCount: 0,
    _rafId: 0,
  };

  function makeDecoder() {
    const d = new VideoDecoder({
      output: (frame) => {
        if (session._currentFrame) {
          try { session._currentFrame.close(); } catch {}
        }
        session._currentFrame = frame;
        if (canvas.width !== frame.codedWidth) canvas.width = frame.codedWidth;
        if (canvas.height !== frame.codedHeight) canvas.height = frame.codedHeight;
        ctx.drawImage(frame, 0, 0, canvas.width, canvas.height);
        session._frameCount++;
        if (onFrame) onFrame(session._pendingTs / 1e6, session._frameCount);
      },
      error: (e) => {
        console.warn('[hmd-player] decode error:', e.message);
        if (onError) onError(e);
      },
    });
    try {
      d.configure({ codec: codecStr, codedWidth: WIDTH, codedHeight: HEIGHT, description });
    } catch (e) {
      // Fallback codec string
      d.configure({ codec: 'hev1.1.6.L93.B0', codedWidth: WIDTH, codedHeight: HEIGHT, description });
    }
    return d;
  }

  function feedSliceNal(n) {
    const isKey = n.nalType === 19 || n.nalType === 20;
    const data = makeAvccChunk(hevc, n.start, n.end);
    session._decoder.decode(new EncodedVideoChunk({
      type: isKey ? 'key' : 'delta',
      timestamp: session._pendingTs,
      duration: FRAME_US,
      data,
    }));
    session._pendingTs += FRAME_US;
  }

  function primeDecoder(budget = 60) {
    if (!session._decoder) return;
    let fed = 0;
    while (session._nextNalIdx < sliceNals.length && fed < budget) {
      feedSliceNal(sliceNals[session._nextNalIdx]);
      session._nextNalIdx++;
      fed++;
    }
  }

  function playbackLoop() {
    if (!session.playing) return;
    if (session._decoder && session._decoder.decodeQueueSize < 6) {
      primeDecoder();
    }
    if (session._nextNalIdx >= sliceNals.length &&
        session._decoder.decodeQueueSize === 0) {
      session.playing = false;
      return;
    }
    session._rafId = requestAnimationFrame(playbackLoop);
  }

  // ── Public methods ──
  session.play = function() {
    if (session.playing) return;
    if (!session._decoder) {
      session._decoder = makeDecoder();
      session._nextNalIdx = 0;
      session._pendingTs = 0;
      primeDecoder();
    }
    session.playing = true;
    session._rafId = requestAnimationFrame(playbackLoop);
  };

  session.pause = function() {
    session.playing = false;
    if (session._rafId) cancelAnimationFrame(session._rafId);
  };

  session.seek = function(sec) {
    const targetSlice = Math.max(0, Math.min(sliceNals.length - 1, Math.round(sec * fps)));
    // Find nearest IDR at or before target
    let idrSlice = 0;
    for (const idx of idrIdxs) {
      if (idx <= targetSlice) idrSlice = idx;
      else break;
    }
    // Reinit decoder
    session.pause();
    if (session._decoder) {
      try { session._decoder.close(); } catch {}
    }
    if (session._currentFrame) {
      try { session._currentFrame.close(); } catch {}
      session._currentFrame = null;
    }
    session._decoder = makeDecoder();
    session._nextNalIdx = 0;
    session._pendingTs = 0;
    // Prime up to idrSlice
    let k = 0;
    while (session._nextNalIdx < sliceNals.length && k < idrSlice) {
      feedSliceNal(sliceNals[session._nextNalIdx]);
      session._nextNalIdx++;
      k++;
    }
    session.play();
  };

  session.toggle = function() {
    if (session.playing) session.pause();
    else session.play();
  };

  session.close = function() {
    session.pause();
    if (session._decoder) {
      try { session._decoder.close(); } catch {}
      session._decoder = null;
    }
    if (session._currentFrame) {
      try { session._currentFrame.close(); } catch {}
      session._currentFrame = null;
    }
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  };

  // Pre-load the decoder so user can hit play and get instant first frame
  session._decoder = makeDecoder();
  primeDecoder();

  return session;
}

/**
 * Fetch a session's part files from server as Uint8Array, in part order.
 */
export async function fetchSessionParts(sessionPath) {
  // sessionPath like "/media\session_00002"
  // Server endpoint: /api/hmd/file?path=...
  // We need to list parts first; assume caller knows part names OR we
  // call a list endpoint. For simplicity, return an array builder hook.
  // The caller is expected to call fetchParts(partNames).
  throw new Error('fetchSessionParts not implemented; call fetchPart(name) for each part');
}

/**
 * Fetch a single .hmd file from server.
 */
export async function fetchPart(filePath) {
  const res = await fetch('/api/hmd/file?path=' + encodeURIComponent(filePath));
  if (!res.ok) throw new Error(`fetch failed (${res.status}): ${filePath}`);
  const buf = await res.arrayBuffer();
  return new Uint8Array(buf);
}

export { buildHevcDescription, codecStringFromSps, makeAvccChunk };