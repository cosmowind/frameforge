// core.js — mcap -> mp4 (H.265 remux) in pure JavaScript
//
// 双格式：既能在 Node（CommonJS require）跑，也能在浏览器（script 标签）跑。
// 不依赖 DOM、VideoDecoder、WebCodecs —— 只读 mcap / 重写盒子。
// 不依赖任何第三方 npm 库 —— mp4 盒子是手写的（只覆盖本项目需要的）。
//
// 本文件暴露：
//   - parseMcap(buf, {onProgress})                       -> { channels, frames }
//   - findAnnexBNals(es: Uint8Array)                     -> [{ offset, end, scLen, type, hdr }]
//   - buildHevcHvcC(vps, sps, pps)                       -> Uint8Array  // HEVCDecoderConfigurationRecord
//   - parseHevcSps(sps)                                  -> { width, height, chroma }
//   - muxMp4({samples, hvcC, width, height, fps?})       -> Uint8Array
//
// 关键修复（2026-07-18）：
//   - NAL header 类型提取 (hdr >> 1) & 0x3f，而非 hdr & 0x3f
//     （HEVC NAL type 是 byte0 的 bits 6-1，bits 5-0 是错的）
//   - 源流的 VPS/SPS/PPS 用的是【标准】NAL 类型 32/33/34；
//     之前的 (hdr & 0x3f) 错误提取为 0/2/4，再"remap"成 32/33/34 时
//     把 NAL header byte 也改坏了（0x40→0x60，0x42→0x61，0x44→0x62），
//     hvcC 因此写出非法类型，mdat 的 slice header 也被改坏（0x02→0x21 = RSV）
//   - 因此删除所有非标准→标准的 remap；直接用源 NAL header byte。
//   - 新增 3 字节起始码 (00 00 01) 支持
//   - 新增 EPB (00 00 03) 跳过，保证切片内部不会被误识别为起始码
//   - 新增 SPS 解析 → width/height，不再硬编码 1920x1080
//   - hvcC 头长度修正为 23（包含 numOfArrays），avgFrameRate 写 2 字节
//
// 用法（Node）:
//   const fs = require('fs');
//   const mcap2mp4 = require('./core.js');
//   const buf = fs.readFileSync('ego_0000.mcap');
//   const { frames } = mcap2mp4.parseMcap(buf);
//   const data = frames.get('/ego/camera/0') || [];
//   const ps = mcap2mp4.scanHevcVpsSpsPps(data);
//   const hvcC = mcap2mp4.buildHevcHvcC(ps.vps, ps.sps, ps.pps);
//   const { width, height } = mcap2mp4.parseHevcSps(ps.sps);
//   const mp4 = mcap2mp4.muxMp4({ samples: data, hvcC, width, height });
//   fs.writeFileSync('out.mp4', Buffer.from(mp4));
//
// 用法（浏览器）：
//   <script src="core.js"></script>
//   const { parseMcap, muxMp4, ... } = window.mcap2mp4Core;

'use strict';

(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory();
  } else {
    root.mcap2mp4Core = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {

  // ═══════════════════════════════════════════════════════════════
  //  MCAP 解析（op-code / varint）
  // ═══════════════════════════════════════════════════════════════

  const MAGIC = [0x89, 0x4D, 0x43, 0x41, 0x50, 0x30, 0x0D, 0x0A];
  const OP_SCHEMA = 0x03, OP_CHANNEL = 0x04, OP_MESSAGE = 0x05,
        OP_CHUNK = 0x06, OP_FOOTER = 0x02;

  function readU16(d, p) { return [d[p] | (d[p + 1] << 8), p + 2]; }
  function readU32(d, p) {
    return [(d[p] | (d[p + 1] << 8) | (d[p + 2] << 16) | (d[p + 3] << 24)) >>> 0, p + 4];
  }
  function readU64(d, p) {
    let v = 0;
    for (let i = 0; i < 8; i++) v += d[p + i] * Math.pow(2, i * 8);
    return [v, p + 8];
  }
  function readStr(d, p) {
    const [l, p2] = readU32(d, p);
    return [new TextDecoder().decode(d.subarray(p2, p2 + l)), p2 + l];
  }

  function readVarint(b, p) {
    let v = 0, sh = 0;
    let x;
    do {
      if (p >= b.length) return [0, p];
      x = b[p++];
      v += (x & 0x7f) * Math.pow(2, sh);
      sh += 7;
    } while (x & 0x80);
    return [v, p];
  }

  function handleMessage(body, len, schemas, channels, frames) {
    const [cid] = readU16(body, 0);
    const [seq] = readU32(body, 2);
    const [pubTime] = readU64(body, 6);
    const [logTime] = readU64(body, 14);
    const ch = channels[cid];
    if (!ch) return;
    const schema = schemas[ch.schema_id];
    if (!schema || schema.name !== 'foxglove.CompressedVideo') return;
    const lastSlash = ch.topic.lastIndexOf('/');
    const cam = ch.topic.substring(lastSlash + 1);
    if (cam !== '0') return;
    const inner = body.subarray(22, len);
    let p = 0;
    let data = null;
    let format = '';
    let captureNs = logTime;
    let gotCapture = false;
    while (p < inner.length) {
      const [tag, afterTag] = readVarint(inner, p); p = afterTag;
      const fn = tag >>> 3, wire = tag & 7;
      if (wire === 2) {
        const [l, afterLen] = readVarint(inner, p);
        if (fn === 3) {
          data = inner.subarray(afterLen, afterLen + l);
          p = afterLen + l;
        } else if (fn === 4) {
          format = new TextDecoder().decode(inner.subarray(afterLen, afterLen + l));
          p = afterLen + l;
        } else if (fn === 1) {
          const end = afterLen + l;
          let ip = afterLen, tsSec = 0, tsNs = 0;
          while (ip < end && ip < inner.length) {
            const [tt, afterT] = readVarint(inner, ip); ip = afterT;
            const tf = tt >>> 3;
            if (tf === 1) { const [sv, np] = readVarint(inner, ip); tsSec = sv; ip = np; }
            else if (tf === 2) { const [nv, np2] = readVarint(inner, ip); tsNs = nv; ip = np2; }
            else ip = readVarint(inner, ip)[1];
          }
          captureNs = tsSec * 1e9 + tsNs;
          gotCapture = true;
          p = end;
        } else if (fn === 2) {
          p = afterLen + l;
        } else {
          p = afterLen + l;
        }
      } else if (wire === 0) {
        p = readVarint(inner, p)[1];
      } else if (wire === 1) {
        p += 8;
      } else if (wire === 5) {
        p += 4;
      } else {
        return;
      }
    }
    if (!data) return;
    let arr = frames.get(ch.topic);
    if (!arr) { arr = []; frames.set(ch.topic, arr); }
    arr.push({
      capture_ns: captureNs,
      data: data,
      format: format,
      frame_id: '',
      used_logtime_fallback: !gotCapture,
    });
  }

  function parseMcap(buf, opts) {
    opts = opts || {};
    const onProgress = opts.onProgress || function () {};
    const d = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
    for (let i = 0; i < 8; i++) {
      if (d[i] !== MAGIC[i]) throw new Error('不是有效的 MCAP 文件');
    }
    const schemas = {}, channels = {};
    const frames = new Map();
    let p = 8;
    let records = 0;
    while (p < d.length - 9) {
      const op = d[p++];
      const [length] = readU64(d, p); p += 8;
      if (length === 0) { p += 8; records++; continue; }
      const len = length;
      if (p + len > d.length) break;
      const body = d.subarray(p, p + len);
      p += len;
      records++;
      if (records % 5000 === 0) onProgress(records);

      if (op === OP_SCHEMA) {
        const [id, q] = readU16(body, 0);
        const [name, q2] = readStr(body, q);
        schemas[id] = { id, name };
      } else if (op === OP_CHANNEL) {
        const [id, q] = readU16(body, 0);
        const [sid, q2] = readU16(body, q);
        const [topic, q3] = readStr(body, q2);
        channels[id] = { id, schema_id: sid, topic };
      } else if (op === OP_MESSAGE) {
        handleMessage(body, len, schemas, channels, frames);
      } else if (op === OP_CHUNK) {
        let cp = 28;
        const [compLen, q1] = readU32(body, cp); cp = q1;
        cp += compLen;
        const [dataLen] = readU64(body, cp); cp += 8;
        const recRaw = body.subarray(cp, cp + dataLen);
        if (dataLen !== recRaw.length) break;
        let rp = 0;
        while (rp < recRaw.length - 9) {
          const iop = recRaw[rp++];
          const [ilen] = readU64(recRaw, rp); rp += 8;
          if (rp + ilen > recRaw.length) break;
          const recData = recRaw.subarray(rp, rp + ilen);
          rp += ilen;
          if (iop === OP_SCHEMA) {
            const [id, q] = readU16(recData, 0);
            const [name, q2] = readStr(recData, q);
            schemas[id] = { id, name };
          } else if (iop === OP_CHANNEL) {
            const [id, q] = readU16(recData, 0);
            const [sid, q2] = readU16(recData, q);
            const [topic, q3] = readStr(recData, q2);
            channels[id] = { id, schema_id: sid, topic };
          } else if (iop === OP_MESSAGE) {
            try {
              handleMessage(recData, recData.length, schemas, channels, frames);
            } catch (e) { /* skip malformed */ }
          }
        }
      } else if (op === OP_FOOTER) {
        break;
      }
    }
    onProgress(records);
    return { channels, frames };
  }

  // ═══════════════════════════════════════════════════════════════
  //  H.265 NAL 工具（Annex-B 扫描；不做 remap，源流已是标准类型）
  // ═══════════════════════════════════════════════════════════════

  // 关键帧：H.265 NAL type 16..23（IDR/BLA/CRA/RASL 等）
  function hevcIsKeyframeType(t) {
    return t >= 16 && t <= 23;
  }

  // 扫 Annex-B 流，找每个 NAL 的 [offset, end, scLen, type, hdr]
  // 同时跳过 emulation prevention byte (00 00 03)
  function findAnnexBNals(data) {
    const nals = [];
    let i = 0;
    const n = data.length;
    while (i < n - 2) {
      let scLen = 0;
      if (i + 3 < n && data[i] === 0 && data[i + 1] === 0 && data[i + 2] === 0 && data[i + 3] === 1) {
        scLen = 4;
      } else if (data[i] === 0 && data[i + 1] === 0 && data[i + 2] === 1) {
        scLen = 3;
      } else {
        i++;
        continue;
      }
      let j = i + scLen;
      while (j < n - 2) {
        // 跳过 emulation prevention byte (00 00 03 XX → 跳过 03)
        if (j + 2 < n && data[j] === 0 && data[j + 1] === 0 && data[j + 2] === 3) {
          j += 3;
          continue;
        }
        if (j + 3 < n && data[j] === 0 && data[j + 1] === 0 && data[j + 2] === 0 && data[j + 3] === 1) break;
        if (data[j] === 0 && data[j + 1] === 0 && data[j + 2] === 1) break;
        j++;
      }
      if (j > i + scLen) {
        const nal = data.subarray(i + scLen, j);
        const hdr = nal.length > 0 ? nal[0] : 0;
        // HEVC NAL header byte 0: forbidden(1) | nal_unit_type(6) | nuh_layer_id MSB(1)
        // → nal_unit_type = (hdr >> 1) & 0x3f
        const type = (hdr >> 1) & 0x3f;
        nals.push({ offset: i, end: j, scLen, type, hdr });
      }
      i = j;
    }
    return nals;
  }

  // 把一帧 Annex-B 数据转成长度前缀 NAL（4 字节大端，lengthSizeMinusOne=3 一致）
  // 保留源 NAL header（已是标准类型），不做 remap
  function annexBToLengthPrefixed(data) {
    const nals = findAnnexBNals(data);
    let total = 0;
    for (let i = 0; i < nals.length; i++) {
      total += 4 + (nals[i].end - nals[i].offset - nals[i].scLen);
    }
    const out = new Uint8Array(total);
    let o = 0;
    let keyframe = false;
    for (let i = 0; i < nals.length; i++) {
      const nal = data.subarray(nals[i].offset + nals[i].scLen, nals[i].end);
      const length = nal.length;
      out[o] = (length >>> 24) & 0xff;
      out[o + 1] = (length >>> 16) & 0xff;
      out[o + 2] = (length >>> 8) & 0xff;
      out[o + 3] = length & 0xff;
      o += 4;
      if (length > 0) {
        out.set(nal, o);
        o += length;
      }
      if (hevcIsKeyframeType(nals[i].type)) keyframe = true;
    }
    return { sample: out, keyframe };
  }

  // 构造 HEVCDecoderConfigurationRecord (hvcC)
  // 使用源流 SPS/VPS/PPS 字节（保留 EPB，ffmpeg movenc 也是这么写）
  function buildHevcHvcC(vps, sps, pps, opts) {
    opts = opts || {};
    const ptl0 = sps.length > 3 ? sps[3] : 0;
    const generalProfileSpace = (ptl0 >>> 6) & 0x03;
    const generalTierFlag = (ptl0 >>> 5) & 0x01;
    const generalProfileIdc = ptl0 & 0x1f;
    const generalLevelIdc = sps.length > 14 ? sps[14] : 0;

    function makeArray(nalType, nal) {
      if (!nal || nal.length === 0) return null;
      // 数组布局（per ISO/IEC 14496-15）:
      //   1 byte: array_completeness(1) | reserved(1) | NAL_unit_type(6)
      //   2 bytes: numNalus (BE u16)
      //   2 bytes: nalUnitLength (BE u16)
      //   N bytes: nalUnit 数据
      const body = new Uint8Array(1 + 2 + 2 + nal.length);
      body[0] = (nalType & 0x3f);              // array_completeness=0, NAL_unit_type
      body[1] = 0x00;
      body[2] = 0x01;                          // numNalus = 1
      body[3] = (nal.length >>> 8) & 0xff;
      body[4] = nal.length & 0xff;
      body.set(nal, 5);
      return body;
    }

    const arrays = [];
    if (vps && vps.length > 0) arrays.push(makeArray(32, vps));
    if (sps && sps.length > 0) arrays.push(makeArray(33, sps));
    if (pps && pps.length > 0) arrays.push(makeArray(34, pps));

    // head: 23 bytes (含 numOfArrays)
    const headLen = 23;
    let total = headLen;
    for (const a of arrays) total += a.length;
    const out = new Uint8Array(total);
    let o = 0;
    out[o++] = 1;                                                 // configurationVersion
    out[o++] = (generalProfileSpace << 6) | (generalTierFlag << 5) | generalProfileIdc;
    for (let i = 0; i < 4; i++) out[o++] = sps.length > 4 + i ? sps[4 + i] : 0;   // profile_compatibility (含可能的 EPB)
    for (let i = 0; i < 6; i++) out[o++] = sps.length > 8 + i ? sps[8 + i] : 0;   // constraint_indicator (含可能的 EPB)
    out[o++] = generalLevelIdc;                                   // general_level_idc
    out[o++] = 0xf0;                                              // min_spatial_segmentation_idc high (reserved=1111 + 0)
    out[o++] = 0x00;                                              // min_spatial_segmentation_idc low
    out[o++] = 0xfc;                                              // parallelismType (reserved=111111 + 00)
    out[o++] = 0xfd;                                              // chromaFormat (reserved=111111 + 01 = 4:2:0)
    out[o++] = 0xf8;                                              // bitDepthLumaMinus8 (reserved=11111 + 000)
    out[o++] = 0xf8;                                              // bitDepthChromaMinus8
    out[o++] = 0x00; out[o++] = 0x00;                             // avgFrameRate (16 bits, 0 = unknown)
    // constantFrameRate(2)=0, numTemporalLayers(3)=1, temporalIdNested(1)=1, lengthSizeMinusOne(2)=3
    out[o++] = (0 << 6) | (1 << 3) | (1 << 2) | 3;
    out[o++] = arrays.length;                                     // numOfArrays
    for (const a of arrays) {
      out.set(a, o);
      o += a.length;
    }
    return out;
  }

  // 扫若干帧的前部字节，找 VPS / SPS / PPS（按标准 NAL 类型 32/33/34）
  // 不做 remap。返回 {vps, sps, pps} 或 null
  function scanHevcVpsSpsPps(frames) {
    const limit = Math.min(frames.length, 50);
    for (let i = 0; i < limit; i++) {
      const data = frames[i].data;
      const nals = findAnnexBNals(data);
      let vps = null, sps = null, pps = null;
      for (let k = 0; k < nals.length; k++) {
        const type = nals[k].type;
        const nal = data.subarray(nals[k].offset + nals[k].scLen, nals[k].end);
        if (type === 32 && !vps) vps = nal;
        else if (type === 33 && !sps) sps = nal;
        else if (type === 34 && !pps) pps = nal;
        if (vps && sps && pps) return { vps, sps, pps };
      }
    }
    return null;
  }

  // 解析 HEVC SPS：返回 { width, height, chroma }
  // 处理 EPB：先把 00 00 03 XX 还原为 00 00 XX 再按位解析
  function parseHevcSps(sps) {
    if (!sps || sps.length < 16) return null;

    // 1) 构造跳过 EPB 的位流
    const bits = [];
    let i = 0;
    while (i < sps.length) {
      if (i + 2 < sps.length && sps[i] === 0 && sps[i + 1] === 0 && sps[i + 2] === 3) {
        for (let b = 7; b >= 0; b--) bits.push((sps[i] >> b) & 1);
        for (let b = 7; b >= 0; b--) bits.push((sps[i + 1] >> b) & 1);
        i += 3;
      } else {
        for (let b = 7; b >= 0; b--) bits.push((sps[i] >> b) & 1);
        i++;
      }
    }

    function readBit(p) { return p < bits.length ? bits[p] : 0; }
    function readBits(p, n) {
      let v = 0;
      for (let k = 0; k < n; k++) v = (v << 1) | readBit(p + k);
      return v;
    }
    function ue(p) {
      let n = 0;
      while (n < 32 && readBit(p + n) === 0) n++;
      if (n >= 32) return { value: 0, next: p };
      const val = readBits(p + n, n + 1);
      return { value: val - 1, next: p + 2 * n + 1 };
    }

    // 2) SPS 头部
    // byte 0-1: NAL header（用源字节即可，不依赖 EPB）
    // byte 2: vps_id(4) | max_sub_layers_minus1(3) | temporal_id_nesting_flag(1)
    const maxSubLayersMinus1 = (sps[1] >>> 5) & 0x07;

    // profile_tier_level 从 bit 24 开始（NAL hdr 16 bit + vps_id(4)+max_sub_layers_minus1(3)+nesting(1) = 8 bit），
    // profilePresentFlag=1 固定 96 bit。
    let bitPos = 24 + 96;

    // 3) sub-layer profile/level flags
    if (maxSubLayersMinus1 > 0) {
      let profileFlags = 0, levelFlags = 0;
      for (let i = 0; i < maxSubLayersMinus1; i++) {
        profileFlags |= (readBit(bitPos + i * 2) << i);
        levelFlags |= (readBit(bitPos + i * 2 + 1) << i);
      }
      bitPos += maxSubLayersMinus1 * 2;
      if (maxSubLayersMinus1 > 0) bitPos += 2;  // 2 reserved bits
      for (let i = 0; i < maxSubLayersMinus1; i++) {
        if (profileFlags & (1 << i)) bitPos += 88;
        if (levelFlags & (1 << i)) bitPos += 8;
      }
    }

    // 4) exp-golomb 字段
    const seqId = ue(bitPos); bitPos = seqId.next;
    const chroma = ue(bitPos); bitPos = chroma.next;
    if (chroma.value === 3) bitPos += 1;  // separate_colour_plane_flag
    const width = ue(bitPos); bitPos = width.next;
    const height = ue(bitPos); bitPos = height.next;

    return { width: width.value, height: height.value, chroma: chroma.value };
  }


  // ═══════════════════════════════════════════════════════════════
  //  MP4 盒子（Box）—— 手写、最小集
  // ═══════════════════════════════════════════════════════════════

  function wbox(typeStr, ...payloads) {
    let len = 8;
    for (const p of payloads) if (p) len += p.length;
    const out = new Uint8Array(len);
    const dv = new DataView(out.buffer);
    dv.setUint32(0, len);
    for (let i = 0; i < 4; i++) out[4 + i] = typeStr.charCodeAt(i);
    let o = 8;
    for (const p of payloads) {
      if (!p) continue;
      out.set(p, o); o += p.length;
    }
    return out;
  }

  function wfbox(typeStr, version, flags, ...payloads) {
    const head = new Uint8Array(12);
    for (let i = 0; i < 4; i++) head[4 + i] = typeStr.charCodeAt(i);
    head[8] = version;
    head[9] = (flags >>> 16) & 0xff;
    head[10] = (flags >>> 8) & 0xff;
    head[11] = flags & 0xff;
    let total = 12;
    for (const p of payloads) if (p) total += p.length;
    const out = new Uint8Array(total);
    out.set(head, 0);
    let o = 12;
    for (const p of payloads) {
      if (!p) continue;
      out.set(p, o); o += p.length;
    }
    new DataView(out.buffer).setUint32(0, total);
    return out;
  }

  function out4(b, o, s) { for (let i = 0; i < 4; i++) b[o + i] = s.charCodeAt(i); }

  function mvhdV0(timescale, duration) {
    const b = new Uint8Array(96);
    let o = 0;
    const dv = new DataView(b.buffer);
    dv.setUint32(o, 0); o += 4;                  // creation_time
    dv.setUint32(o, 0); o += 4;                  // modification_time
    dv.setUint32(o, timescale); o += 4;
    dv.setUint32(o, duration); o += 4;
    dv.setInt32(o, 0x00010000); o += 4;          // rate
    dv.setInt16(o, 0x0100); o += 2;              // volume
    for (let i = 0; i < 10; i++) { b[o++] = 0; }
    dv.setUint32(o, 0x00010000); o += 4;
    dv.setInt32(o, 0); dv.setInt32(o + 4, 0); o += 8;
    dv.setInt32(o, 0); o += 4;
    dv.setUint32(o, 0x00010000); o += 4;
    dv.setInt32(o, 0); dv.setInt32(o + 4, 0); o += 8;
    dv.setInt32(o, 0); o += 4;
    dv.setUint32(o, 0x40000000); o += 4;
    for (let i = 0; i < 24; i++) { b[o++] = 0; }
    dv.setUint32(o, 2); o += 4;                  // next_track_ID
    return wfbox('mvhd', 0, 0, b);
  }

  function tkhdV1(trackId, duration, width, height) {
    const b = new Uint8Array(88);
    const dv = new DataView(b.buffer);
    let o = 0;
    dv.setUint32(o, 0); o += 4;
    dv.setUint32(o, 0); o += 4;
    dv.setUint32(o, 0); o += 4;
    dv.setUint32(o, 0); o += 4;
    dv.setUint32(o, trackId); o += 4;
    dv.setUint32(o, 0); o += 4;            // reserved
    dv.setUint32(o, duration); o += 4;
    for (let i = 0; i < 2; i++) { dv.setUint32(o, 0); o += 4; } // reserved
    dv.setUint16(o, 0); o += 2;
    dv.setUint16(o, 0); o += 2;
    dv.setUint16(o, 0); o += 2;
    dv.setUint16(o, 0); o += 2;
    dv.setUint32(o, 0x00010000); o += 4;
    dv.setInt32(o, 0); dv.setInt32(o + 4, 0); o += 8;
    dv.setInt32(o, 0); o += 4;
    dv.setUint32(o, 0x00010000); o += 4;
    dv.setInt32(o, 0); dv.setInt32(o + 4, 0); o += 8;
    dv.setInt32(o, 0); o += 4;
    dv.setUint32(o, 0x40000000); o += 4;
    dv.setUint32(o, (width << 16) >>> 0); o += 4;
    dv.setUint32(o, (height << 16) >>> 0); o += 4;
    return wfbox('tkhd', 1, 0x000007, b);
  }

  function mdhdV0(timescale, duration) {
    const b = new Uint8Array(20);
    const dv = new DataView(b.buffer);
    let o = 0;
    dv.setUint32(o, 0); o += 4;
    dv.setUint32(o, 0); o += 4;
    dv.setUint32(o, timescale); o += 4;
    dv.setUint32(o, duration); o += 4;
    dv.setUint16(o, 0x55c4); o += 2;
    dv.setUint16(o, 0); o += 2;
    return wfbox('mdhd', 0, 0, b);
  }

  function hdlrVide() {
    const b = new Uint8Array(21);
    let o = 0;
    new DataView(b.buffer).setUint32(o, 0); o += 4;
    out4(b, o, 'vide'); o += 4;
    for (let i = 0; i < 12; i++) b[o++] = 0;
    b[o++] = 0;
    return wfbox('hdlr', 0, 0, b);
  }

  function vmhd() {
    const b = new Uint8Array(8);
    let o = 0;
    new DataView(b.buffer).setUint16(o, 0); o += 2;
    for (let i = 0; i < 3; i++) { new DataView(b.buffer).setUint16(o, 0); o += 2; }
    return wfbox('vmhd', 0, 1, b);
  }

  function dinfDref() {
    const url = wfbox('url ', 0, 1, null);
    const ec = new Uint8Array(4);
    new DataView(ec.buffer).setUint32(0, 1);
    const dref = wfbox('dref', 0, 0, ec, url);
    return wbox('dinf', dref);
  }

  function hvc1Entry(hvcC, width, height) {
    const head = new Uint8Array(78);
    const dv = new DataView(head.buffer);
    dv.setUint16(0, 0); dv.setUint32(2, 0);
    dv.setUint16(6, 1);                       // data_ref_idx
    dv.setUint16(8, 0);
    dv.setUint16(10, 0);
    for (let i = 0; i < 12; i += 4) dv.setUint32(12 + i, 0);
    dv.setUint16(24, width);
    dv.setUint16(26, height);
    dv.setUint32(28, 0x00480000);
    dv.setUint32(32, 0x00480000);
    dv.setUint32(36, 0);
    dv.setUint16(40, 1);
    for (let i = 42; i < 74; i++) head[i] = 0;
    dv.setUint16(74, 24);
    dv.setInt16(76, -1);
    return wbox('hvc1', head, hvcC);
  }

  function wrapStsd(visualEntryBox) {
    const out = new Uint8Array(16 + visualEntryBox.length);
    new DataView(out.buffer).setUint32(0, out.length);
    out4(out, 4, 'stsd');
    out[8] = 0; out[9] = 0; out[10] = 0; out[11] = 0;
    new DataView(out.buffer).setUint32(12, 1);
    out.set(visualEntryBox, 16);
    return out;
  }

  function stts(samples, timescale) {
    if (samples.length === 0) return wfbox('stts', 0, 0, new Uint8Array(0));
    const out = new Uint8Array(4 + samples.length * 8);
    const dv = new DataView(out.buffer);
    let o = 0;
    dv.setUint32(o, samples.length); o += 4;
    for (let i = 0; i < samples.length; i++) {
      dv.setUint32(o, 1); o += 4;
      let delta;
      if (i + 1 < samples.length) {
        delta = Math.round((samples[i + 1].capture_ns - samples[i].capture_ns)
                            / 1e9 * timescale);
      } else {
        delta = i > 0
          ? Math.round((samples[i].capture_ns - samples[i - 1].capture_ns) / 1e9 * timescale)
          : 1;
      }
      if (delta < 1) delta = 1;
      dv.setUint32(o, delta); o += 4;
    }
    return wfbox('stts', 0, 0, out);
  }

  function cttsZero(samples) {
    const out = new Uint8Array(4 + samples.length * 8);
    const dv = new DataView(out.buffer);
    let o = 0;
    dv.setUint32(o, samples.length); o += 4;
    for (let i = 0; i < samples.length; i++) {
      dv.setUint32(o, 1); o += 4;
      dv.setInt32(o, 0); o += 4;
    }
    return wfbox('ctts', 0, 0, out);
  }

  function stscOneChunk(samples) {
    const out = new Uint8Array(16);
    const dv = new DataView(out.buffer);
    let o = 0;
    dv.setUint32(o, 1); o += 4;
    dv.setUint32(o, 1); o += 4;
    dv.setUint32(o, samples.length); o += 4;
    dv.setUint32(o, 1); o += 4;
    return wfbox('stsc', 0, 0, out);
  }

  function stsz(samples) {
    const out = new Uint8Array(8 + samples.length * 4);
    const dv = new DataView(out.buffer);
    let o = 0;
    dv.setUint32(o, 0); o += 4;
    dv.setUint32(o, samples.length); o += 4;
    for (let i = 0; i < samples.length; i++) {
      dv.setUint32(o, samples[i].size); o += 4;
    }
    return wfbox('stsz', 0, 0, out);
  }

  function stco(offset) {
    const out = new Uint8Array(8);
    const dv = new DataView(out.buffer);
    let o = 0;
    dv.setUint32(o, 1); o += 4;
    dv.setUint32(o, offset); o += 4;
    return wfbox('stco', 0, 0, out);
  }

  function stss(keyframeIndices) {
    const out = new Uint8Array(4 + keyframeIndices.length * 4);
    const dv = new DataView(out.buffer);
    let o = 0;
    dv.setUint32(o, keyframeIndices.length); o += 4;
    for (let i = 0; i < keyframeIndices.length; i++) {
      dv.setUint32(o, keyframeIndices[i] + 1); o += 4;
    }
    return wfbox('stss', 0, 0, out);
  }

  function ftyp() {
    const out = new Uint8Array(20);
    const dv = new DataView(out.buffer);
    dv.setUint32(0, 20);
    out[4] = 0x66; out[5] = 0x74; out[6] = 0x79; out[7] = 0x70;
    out[8] = 0x69; out[9] = 0x73; out[10] = 0x6f; out[11] = 0x6d;
    dv.setUint32(12, 512);
    out[16] = 0x69; out[17] = 0x73; out[18] = 0x6f; out[19] = 0x6d;
    return out;
  }

  function patchStcoOffset(moov, offset) {
    // 递归扫描所有子 box 找 stco；stco 第一项 offset 位于 box 内偏移 16。
    function scan(start, end) {
      let i = start;
      while (i + 8 <= end) {
        const size = (moov[i] << 24) | (moov[i + 1] << 16) | (moov[i + 2] << 8) | moov[i + 3];
        const type = String.fromCharCode(moov[i + 4], moov[i + 5], moov[i + 6], moov[i + 7]);
        if (size <= 0 || i + size > end) return false;
        if (type === 'stco') {
          new DataView(moov.buffer, moov.byteOffset).setUint32(i + 16, offset >>> 0);
          return true;
        }
        // 容器 box 递归扫描其 payload
        if (type === 'moov' || type === 'trak' || type === 'mdia' ||
            type === 'minf' || type === 'stbl' || type === 'dinf' ||
            type === 'stsd' || type === 'dref') {
          if (scan(i + 8, i + size)) return true;
        }
        i += size;
      }
      return false;
    }
    scan(0, moov.length);
  }

  // ═══════════════════════════════════════════════════════════════
  //  muxMp4 —— 主入口
  // ═══════════════════════════════════════════════════════════════

  function muxMp4(opts) {
    const rawFrames = opts.frames;
    const hvcC = opts.hvcC;
    let width = opts.width | 0;
    let height = opts.height | 0;
    const timescale = opts.timescale || 90000;
    const onProgress = opts.onProgress || function () {};

    if (!rawFrames.length) throw new Error('没有帧');

    // 1) 把每帧 Annex-B 转成长度前缀 NAL。每个 sample 只放【一个】VCL 切片 NAL
    //    （VPS/SPS/PPS 只放在 hvcC，mdat 里不放），这是 PyAV/mp4box 的惯例，
    //    也是 ffmpeg 解码器最稳的布局（混合多个 NAL 在同一 sample 里会触发
    //    "Invalid NAL unit size"）。
    const samples = [];
    const firstCaptureNs = rawFrames[0].capture_ns;
    for (let i = 0; i < rawFrames.length; i++) {
      // 在原始帧里找第一个 VCL NAL（type < 32，即 slice 类型）
      const nals = findAnnexBNals(rawFrames[i].data);
      let vclNal = null;
      for (let k = 0; k < nals.length; k++) {
        if (nals[k].type < 32) { vclNal = nals[k]; break; }
      }
      if (!vclNal) {
        // 没找到切片，整帧跳过
        continue;
      }
      const nal = rawFrames[i].data.subarray(vclNal.offset + vclNal.scLen, vclNal.end);
      const length = nal.length;
      // 4 字节大端长度前缀 + NAL 字节
      const sample = new Uint8Array(4 + length);
      sample[0] = (length >>> 24) & 0xff;
      sample[1] = (length >>> 16) & 0xff;
      sample[2] = (length >>> 8) & 0xff;
      sample[3] = length & 0xff;
      sample.set(nal, 4);
      const keyframe = hevcIsKeyframeType(vclNal.type);
      const pts = Math.round((rawFrames[i].capture_ns - firstCaptureNs) / 1e9 * timescale);
      samples.push({ size: sample.length, data: sample, keyframe, pts });
    }

    // 兜底：如果调用方没传 width/height，从 SPS 解析
    if ((!width || !height) && opts.sps) {
      const sp = parseHevcSps(opts.sps);
      if (sp) { width = sp.width; height = sp.height; }
    }

    const lastCaptureNs = rawFrames[rawFrames.length - 1].capture_ns;
    const duration = Math.round((lastCaptureNs - firstCaptureNs) / 1e9 * timescale) || 1;
    const keyframeIndices = [];
    for (let i = 0; i < samples.length; i++) if (samples[i].keyframe) keyframeIndices.push(i);

    // 2) 各表盒子
    const sdHvcCBox = wbox('hvcC', hvcC);
    const visualEntry = hvc1Entry(sdHvcCBox, width, height);
    const stsdBox_ = wrapStsd(visualEntry);

    const stbl = wbox('stbl',
      stsdBox_,
      stts(samples, timescale),
      cttsZero(samples),
      stscOneChunk(samples),
      stsz(samples),
      stco(0),
      stss(keyframeIndices)
    );

    const minf = wbox('minf', vmhd(), dinfDref(), stbl);
    const mdia = wbox('mdia', mdhdV0(timescale, duration), hdlrVide(), minf);
    const trak = wbox('trak', tkhdV1(1, duration, width, height), mdia);
    const moov = wbox('moov', mvhdV0(timescale, duration), trak);

    // 3) mdat
    let mdatPayloadSize = 0;
    for (let i = 0; i < samples.length; i++) mdatPayloadSize += samples[i].size;
    const mdat = new Uint8Array(8 + mdatPayloadSize);
    new DataView(mdat.buffer).setUint32(0, mdat.length);
    for (let i = 0; i < 4; i++) mdat[4 + i] = 'mdat'.charCodeAt(i);
    {
      let o = 8;
      for (let i = 0; i < samples.length; i++) {
        mdat.set(samples[i].data, o);
        o += samples[i].size;
      }
    }

    // 4) 拼接 + 回填 stco
    //    stco 指向 mdat 的【载荷】起点（=mdat 头 8 字节之后），不是 mdat box 起点
    const ftyp_ = ftyp();
    const mdatPayloadOffset = ftyp_.length + moov.length + 8;
    patchStcoOffset(moov, mdatPayloadOffset);

    const out = new Uint8Array(ftyp_.length + moov.length + mdat.length);
    out.set(ftyp_, 0);
    out.set(moov, ftyp_.length);
    out.set(mdat, ftyp_.length + moov.length);
    onProgress(samples.length);
    return out;
  }

  // ═══════════════════════════════════════════════════════════════
  //  exports
  // ═══════════════════════════════════════════════════════════════

  return {
    parseMcap,
    findAnnexBNals,
    annexBToLengthPrefixed,
    scanHevcVpsSpsPps,
    buildHevcHvcC,
    parseHevcSps,
    muxMp4,
    ftyp,
    mvhdV0,
    tkhdV1,
    hvc1Entry,
    stts,
    stco,
  };
}));
