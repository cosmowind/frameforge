  import { parse, splitStereo, dedupParamSets } from '/static/hmd/hmd-decode.esm.js';
  import { tryOpenHmdMp4 } from '/static/hmd/hmd-mp4-shortcut.js';

  const $ = id => document.getElementById(id);
  const leftCanvas = $('leftCanvas'), rightCanvas = $('rightCanvas');
  const leftVideo = $('leftVideo'), rightVideo = $('rightVideo');
  const leftCtx = leftCanvas.getContext('2d');
  const rightCtx = rightCanvas.getContext('2d');
  const errBox = $('errBox'), meta = $('meta'), pickStat = $('pickStat');
  const seek = $('seek'), timeEl = $('time'), hudEl = $('hud');
  const playBtn = $('playBtn'), backBtn = $('backBtn'), fwdBtn = $('fwdBtn');
  const loadBtn = $('loadBtn'), autoBtn = $('autoBtn'), folderInput = $('folderInput');

  // Active session (mp4 OR webcodecs); null = nothing loaded
  let mp4Session = null;   // when mode==='mp4'
  let wcMode = false;      // when WebCodecs fallback active

  function err(msg) { errBox.textContent = msg; errBox.classList.remove('hidden'); }
  function clearErr() { errBox.classList.add('hidden'); errBox.textContent = ''; }

  function fmtTime(sec) {
    if (!isFinite(sec)) sec = 0;
    const m = Math.floor(sec / 60);
    const s = sec - m * 60;
    return `${String(m).padStart(2,'0')}:${s.toFixed(1).padStart(4,'0')}`;
  }

  // ─── Player state ───
  const state = {
    folder: null, parts: [], totalSize: 0, metadata: null,
    leftNals: [], rightNals: [], // {type, data}[]
    leftIdx: 0, rightIdx: 0,
    leftDec: null, rightDec: null,
    leftFrame: null, rightFrame: null,
    playing: false, rate: 1.0,
    totalFrames: 0,
    lastTimestamp: 0,
  };

  function buildHevcDescription(vpsNal, spsNal, ppsNal) {
    const spsBody = spsNal.subarray(4);
    const profile_space = (spsBody[3] >> 6) & 0x03;
    const tier_flag = (spsBody[3] >> 5) & 0x01;
    const profile_idc = spsBody[3] & 0x1f;
    const profile_compat = spsBody.subarray(4, 8);
    const constraint = new Uint8Array(6);
    constraint[0] = spsBody[8] & 0xf0;
    let level_idc = spsBody[14];
    if (level_idc === 0) level_idc = 120;
    const out = [];
    const push = arr => out.push(arr);
    push(new Uint8Array([1]));
    push(new Uint8Array([(profile_space << 6) | (tier_flag << 5) | profile_idc]));
    push(profile_compat); push(constraint);
    push(new Uint8Array([level_idc]));
    push(new Uint8Array([0xf0, 0x00]));
    push(new Uint8Array([0xfc]));
    push(new Uint8Array([0xfd]));
    push(new Uint8Array([0xf8]));
    push(new Uint8Array([0xf8]));
    push(new Uint8Array([0, 0]));
    push(new Uint8Array([0x0f]));
    push(new Uint8Array([3]));
    push(new Uint8Array([0x20])); push(new Uint8Array([0, 1]));
    push(new Uint8Array([(vpsNal.subarray(4).length >> 8) & 0xff, vpsNal.subarray(4).length & 0xff]));
    push(vpsNal.subarray(4));
    push(new Uint8Array([0x21])); push(new Uint8Array([0, 1]));
    push(new Uint8Array([(spsNal.subarray(4).length >> 8) & 0xff, spsNal.subarray(4).length & 0xff]));
    push(spsNal.subarray(4));
    push(new Uint8Array([0x22])); push(new Uint8Array([0, 1]));
    push(new Uint8Array([(ppsNal.subarray(4).length >> 8) & 0xff, ppsNal.subarray(4).length & 0xff]));
    push(ppsNal.subarray(4));
    let total = 0; for (const a of out) total += a.length;
    const merged = new Uint8Array(total);
    let off = 0; for (const a of out) { merged.set(a, off); off += a.length; }
    return merged;
  }
  function codecStringFromSps(spsNal) {
    const o = 4;
    const profileIdc = spsNal[o + 3] & 0x1f;
    const compat = spsNal[o + 4];
    let level = spsNal[o + 14];
    if (level === 0) level = 120;
    let constraintHex = '';
    for (let i = 0; i < 6; i++) {
      let b = spsNal[o + 8 + i];
      if (i === 0) b = b & 0xf0; else b = 0;
      constraintHex += b.toString(16).padStart(2, '0');
    }
    return `hev1.${profileIdc}.${compat.toString(16).padStart(2,'0')}.L${level}.${constraintHex.toUpperCase()}`;
  }
  function avccWrap(nal) {
    const body = nal[0]===0&&nal[1]===0&&nal[2]===0&&nal[3]===1 ? nal.subarray(4) : nal;
    const out = new Uint8Array(4 + body.length);
    new DataView(out.buffer).setUint32(0, body.length, false);
    out.set(body, 4);
    return out;
  }
  function frameToChunks(hevc, paramSets) {
    // Build {type, data}[] for a single stream, with VPS/SPS/PPS prepended.
    // Returns { nals, firstSliceIdx } where firstSliceIdx points to the
    // first slice NAL that follows an IDR (or any IDR if no IDR is found,
    // index 0). Caller must skip ahead to firstSliceIdx when priming a
    // fresh decoder (key-frame requirement).
    const nals = [];
    for (const ps of paramSets) nals.push({ type: 'ps', data: ps });
    let i = 0;
    while (i < hevc.length - 3) {
      if (hevc[i]===0 && hevc[i+1]===0 && hevc[i+2]===0 && hevc[i+3]===1) {
        let j = i + 4;
        while (j < hevc.length - 3) {
          if (hevc[j]===0 && hevc[j+1]===0 && hevc[j+2]===0 && hevc[j+3]===1) break;
          if (hevc[j]===0 && hevc[j+1]===0 && hevc[j+2]===1) break;
          j++;
        }
        const nal = hevc.subarray(i, j);
        const nalType = (nal[4] >> 1) & 0x3f;
        nals.push({ type: nalType, data: nal });
        i = j;
      } else i++;
    }
    // Find the first IDR (type 19/20) — everything before it depends on
    // frames we can't decode. primeDecoders() uses this to skip ahead.
    let firstIdr = 0;
    for (let k = 0; k < nals.length; k++) {
      const t = nals[k].type;
      if (t === 19 || t === 20) { firstIdr = k; break; }
    }
    return { nals, firstIdr };
  }

  // ─── progress overlay controls ───
  const progOverlay = $('progressOverlay');
  const progTitle = $('progTitle');
  const progStage = $('progStage');
  const progBar = $('progBar');
  const progPct = $('progPct');
  const stgIds = ['stg1', 'stg2', 'stg3', 'stg4'];
  function showProgress(title) {
    progOverlay.classList.remove('hidden');
    progTitle.textContent = title;
    progBar.style.width = '0%';
    progPct.textContent = '0%';
    stgIds.forEach(id => $(id).classList.remove('active', 'done'));
  }
  function setProgress(stage, pct) {
    // stage: 'download' / 'parse' / 'split' / 'decode', pct 0..100
    const stageMap = { download: 1, parse: 2, split: 3, decode: 4 };
    const stageIdx = stageMap[stage] || 1;
    stgIds.forEach((id, i) => {
      const el = $(id);
      el.classList.remove('active');
      if (i + 1 < stageIdx) el.classList.add('done');
      else if (i + 1 === stageIdx) el.classList.add('active');
    });
    const labels = { download: '下载 .hmd parts', parse: '解析 HMD 容器', split: '拆分左右眼流', decode: '初始化解码器' };
    progStage.textContent = labels[stage] || stage;
    progBar.style.width = pct + '%';
    progPct.textContent = pct.toFixed(0) + '%';
  }
  function hideProgress() {
    stgIds.forEach(id => $(id).classList.add('done'));
    progBar.style.width = '100%';
    progPct.textContent = '100%';
    setTimeout(() => progOverlay.classList.add('hidden'), 350);
  }

  async function loadFolder(folder) {
    clearErr();
    state.folder = folder;
    pickStat.textContent = '加载中…';
    meta.textContent = folder;
    showProgress('加载 HMD 文件中');
    // Close any prior MP4 session so videos reset for the new folder
    if (mp4Session) { try { mp4Session.close(); } catch {} mp4Session = null; }
    leftVideo.hidden = true; rightVideo.hidden = true;
    leftCanvas.style.display = ''; rightCanvas.style.display = '';
    wcMode = false;
    try {
      // ── Stage 0: try preprocessed MP4 (秒开) ──
      setProgress('download', 0);
      const mp4 = await tryOpenHmdMp4({
        folder,
        leftVideo, rightVideo,
        onProgress: (stage, pct) => {
          if (stage === 'check') setProgress('download', 5);
          else if (stage === 'waiting-mp4') setProgress('parse', Math.min(95, 10 + pct * 0.8));
          else if (stage === 'mp4') setProgress('decode', 100);
          else if (stage === 'mp4-error') pickStat.textContent = 'MP4 预处理失败，回退到原始解析…';
          else if (stage === 'kickoff-preprocess') pickStat.textContent = '后台启动预处理，本次先看 WebCodecs…';
        },
      });
      if (mp4) {
        // Short-circuit: switch to <video> mode
        await activateMp4Mode(mp4, folder);
        return;
      }
      // MP4 not ready — fall through to original WebCodecs flow
      // ── Stage 1: download parts ──
      setProgress('download', 0);
      const infoRes = await fetch('/api/hmd/info?path=' + encodeURIComponent(folder));
      if (!infoRes.ok) throw new Error('Info 失败: HTTP ' + infoRes.status);
      const info = await infoRes.json();
      if (info.error) throw new Error(info.error);
      state.parts = info.parts;
      state.totalSize = info.total_size;
      state.metadata = info.metadata;
      if (!state.parts.length) throw new Error('该文件夹下没有 part_*.hmd 文件');
      meta.innerHTML = `<b>${folder}</b> · ${state.parts.length} parts · ${(state.totalSize/1024/1024).toFixed(1)} MB`;
      pickStat.textContent = `下载 0/${state.parts.length} parts…`;

      const partBufs = [];
      for (let pi = 0; pi < state.parts.length; pi++) {
        const p = state.parts[pi];
        const r = await fetch('/api/hmd/raw?path=' + encodeURIComponent(folder) + '&file=' + encodeURIComponent(p.name));
        if (!r.ok) throw new Error('拉取 ' + p.name + ' 失败: HTTP ' + r.status);
        const ab = await r.arrayBuffer();
        partBufs.push(new Uint8Array(ab));
        setProgress('download', Math.round((pi + 1) / state.parts.length * 100));
        pickStat.textContent = `下载 ${pi+1}/${state.parts.length} parts…`;
      }
      pickStat.textContent = `✓ 已下载 ${state.parts.length} parts`;

      // ── Stage 2: parse HMD container ──
      setProgress('parse', 0);
      const r = await parse(partBufs, {
        onProgress: pct => {
          const p = Math.round(pct * 100);
          setProgress('parse', p);
          pickStat.textContent = `解析容器… ${p}%`;
        },
      });
      setProgress('parse', 100);

      // ── Stage 3: split stereo ──
      setProgress('split', 0);
      // 给浏览器一个 paint 帧让进度条更新
      await new Promise(r => setTimeout(r, 30));
      const hevc = dedupParamSets(r.video[0].hevc);
      setProgress('split', 50);
      await new Promise(r => setTimeout(r, 30));
      const stereo = splitStereo(hevc);
      setProgress('split', 100);

      state.totalFrames = stereo.stats.totalFrames;
      const leftChunks = frameToChunks(stereo.left, [r.video[0].vps, r.video[0].sps, r.video[0].pps]);
      const rightChunks = frameToChunks(stereo.right, [r.video[0].vps, r.video[0].sps, r.video[0].pps]);
      state.leftNals = leftChunks.nals;
      state.rightNals = rightChunks.nals;
      state.leftFirstIdr = leftChunks.firstIdr;
      state.rightFirstIdr = rightChunks.firstIdr;
      pickStat.textContent = `✓ 拆分完成 L=${stereo.stats.leftFrames} R=${stereo.stats.rightFrames} 帧 @ 30 fps`;

      // ── Stage 4: setup decoders ──
      setProgress('decode', 0);
      const spsNal = r.video[0].sps;
      const vpsNal = r.video[0].vps;
      const ppsNal = r.video[0].pps;
      state.codec = codecStringFromSps(spsNal);
      state.desc = buildHevcDescription(vpsNal, spsNal, ppsNal);
      setupDecoders();
      // ── WebCodecs requirement: the first frame fed after configure()/flush()
      //    MUST be a key frame (IDR). Skip ahead to the first IDR.
      state.leftIdx = state.leftFirstIdr;
      state.rightIdx = state.rightFirstIdr;
      seek.disabled = false; playBtn.disabled = false; backBtn.disabled = false; fwdBtn.disabled = false;
      primeDecoders();
      setProgress('decode', 100);
      setPlaying(true);
      hideProgress();
    } catch (e) {
      err(e.message || String(e));
      pickStat.textContent = '✗ 失败';
      progTitle.textContent = '加载失败';
      setTimeout(() => progOverlay.classList.add('hidden'), 800);
    }
  }

  function setupDecoders() {
    if (state.leftDec) try { state.leftDec.close(); } catch {}
    if (state.rightDec) try { state.rightDec.close(); } catch {}
    state.leftDec = new VideoDecoder({
      output: f => { if (state.leftFrame) try { state.leftFrame.close(); } catch {} state.leftFrame = f; drawFrame(leftCtx, f, leftCanvas); updateStat('leftStat', f); },
      error: e => console.warn('left dec:', e.message),
    });
    state.rightDec = new VideoDecoder({
      output: f => { if (state.rightFrame) try { state.rightFrame.close(); } catch {} state.rightFrame = f; drawFrame(rightCtx, f, rightCanvas); updateStat('rightStat', f); },
      error: e => console.warn('right dec:', e.message),
    });
    state.leftDec.configure({ codec: state.codec, codedWidth: 1920, codedHeight: 1080, description: state.desc });
    state.rightDec.configure({ codec: state.codec, codedWidth: 1920, codedHeight: 1080, description: state.desc });
  }

  function drawFrame(ctx, frame, canvas) {
    if (canvas.width !== frame.codedWidth) canvas.width = frame.codedWidth;
    if (canvas.height !== frame.codedHeight) canvas.height = frame.codedHeight;
    ctx.drawImage(frame, 0, 0, canvas.width, canvas.height);
  }
  function updateStat(id, frame) {
    document.getElementById(id).textContent =
      `${(frame.codedWidth)}x${frame.codedHeight} t=${(frame.timestamp/1e6).toFixed(2)}s`;
  }

  function feedFrame(dec, nalEntry, frameIdx) {
    if (nalEntry.type === 'ps') return;  // param sets already in description
    const isKey = nalEntry.type === 19 || nalEntry.type === 20;
    const data = avccWrap(nalEntry.data);
    const dur = Math.round(1e6 / 30);
    // Monotonically increasing timestamp per frame (in microseconds).
    // Hardcoded 0 caused "duplicate timestamp" errors on some decoders.
    const ts = (frameIdx || 0) * dur;
    dec.decode(new EncodedVideoChunk({ type: isKey ? 'key' : 'delta', timestamp: ts, duration: dur, data }));
  }
  function primeDecoders() {
    const BUDGET = 60;
    let fedL = 0, fedR = 0;
    while (state.leftIdx < state.leftNals.length && fedL < BUDGET) {
      feedFrame(state.leftDec, state.leftNals[state.leftIdx], fedL);
      state.leftIdx++; fedL++;
    }
    while (state.rightIdx < state.rightNals.length && fedR < BUDGET) {
      feedFrame(state.rightDec, state.rightNals[state.rightIdx], fedR);
      state.rightIdx++; fedR++;
    }
  }

  function setPlaying(on) {
    state.playing = on;
    playBtn.textContent = on ? '⏸' : '⏯';
  }
  playBtn.addEventListener('click', () => {
    if (mp4Session) {
      const nowPlaying = mp4Session.toggle();
      setPlaying(nowPlaying);
    } else {
      setPlaying(!state.playing);
    }
  });

  // ─── MP4 mode activation (uses preprocessed left.mp4/right.mp4 via <video>) ───
  async function activateMp4Mode(mp4, folder) {
    mp4Session = mp4;
    wcMode = false;
    // Hide canvas, show video
    leftCanvas.style.display = 'none';
    rightCanvas.style.display = 'none';
    leftVideo.hidden = false; rightVideo.hidden = false;
    // Wait for metadata
    await new Promise((resolve) => {
      let pending = 2;
      const onMeta = () => { if (--pending <= 0) resolve(); };
      if (leftVideo.readyState >= 1) pending--; else leftVideo.addEventListener('loadedmetadata', onMeta, { once: true });
      if (rightVideo.readyState >= 1) pending--; else rightVideo.addEventListener('loadedmetadata', onMeta, { once: true });
      setTimeout(resolve, 4000);
    });
    // Wire events
    mp4.bindEvents({
      onPlay: () => setPlaying(true),
      onPause: () => setPlaying(false),
      onEnded: () => setPlaying(false),
      onTimeUpdate: (tL, tR) => {
        const dur = mp4.getDuration() || 0;
        if (document.activeElement !== seek && dur > 0) {
          seek.value = Math.round((tL / dur) * 1000);
        }
        timeEl.textContent = `${fmtTime(tL)} / ${fmtTime(dur)}`;
        hudEl.textContent = `L=${tL.toFixed(2)}s R=${tR.toFixed(2)}s Δ=${((tL-tR)*1000).toFixed(0)}ms`;
        $('leftStat').textContent = `${(leftVideo.videoWidth||0)}x${leftVideo.videoHeight||0} t=${tL.toFixed(2)}s`;
        $('rightStat').textContent = `${(rightVideo.videoWidth||0)}x${rightVideo.videoHeight||0} t=${tR.toFixed(2)}s`;
      },
    });
    seek.disabled = false; playBtn.disabled = false; backBtn.disabled = false; fwdBtn.disabled = false;
    const dur = mp4.getDuration() || 0;
    meta.innerHTML = `<b>${folder}</b> · MP4 秒开 · ${fmtTime(dur)}`;
    pickStat.textContent = `✓ MP4 已加载（左 ${(leftVideo.videoWidth||0)}x${leftVideo.videoHeight||0} · 右 ${(rightVideo.videoWidth||0)}x${rightVideo.videoHeight||0}）`;
    // Auto-play
    mp4.play();
    hideProgress();
  }

  let rafId = null;
  function loop() {
    rafId = requestAnimationFrame(loop);
    if (mp4Session) return;  // MP4 mode updates via video timeupdate event
    if (!state.playing) return;
    if (state.leftDec && state.leftDec.decodeQueueSize < 6) primeDecoders();
    if (state.rightDec && state.rightDec.decodeQueueSize < 6) primeDecoders();
    // 进度
    const fedL = state.leftIdx, fedR = state.rightIdx;
    const tL = fedL / 30, tR = fedR / 30;
    const total = state.totalFrames / 2 / 30;  // 一帧流的总时长
    if (document.activeElement !== seek) {
      seek.value = total > 0 ? Math.round(tL / total * 1000) : 0;
    }
    timeEl.textContent = `${fmtTime(tL)} / ${fmtTime(total)}`;
    hudEl.textContent = `L=${fedL}/${state.leftNals.length} R=${fedR}/${state.rightNals.length} Δ=${((tL-tR)*1000).toFixed(0)}ms`;
    if (state.leftIdx >= state.leftNals.length && state.leftDec.decodeQueueSize === 0) {
      setPlaying(false);
    }
  }
  loop();

  // 拖动 = 重新初始化（简化：跳到对应帧）
  function findIdrAtOrBefore(nals, targetIdx, fallbackFirstIdr) {
    let idr = fallbackFirstIdr || 0;
    for (let k = 0; k < targetIdx && k < nals.length; k++) {
      const t = nals[k].type;
      if (t === 19 || t === 20) idr = k;
    }
    return idr;
  }
  seek.addEventListener('change', () => {
    if (mp4Session) {
      const dur = mp4Session.getDuration() || 0;
      if (dur > 0) mp4Session.seek(dur * (parseInt(seek.value) / 1000));
      return;
    }
    if (!state.totalFrames) return;
    const pct = parseInt(seek.value) / 1000;
    const targetL = Math.floor(pct * state.leftNals.length);
    const targetR = Math.floor(pct * state.rightNals.length);
    // Find nearest IDR at or before target (required after flush())
    const idrL = findIdrAtOrBefore(state.leftNals, targetL, state.leftFirstIdr);
    const idrR = findIdrAtOrBefore(state.rightNals, targetR, state.rightFirstIdr);
    setupDecoders();
    state.leftIdx = idrL; state.rightIdx = idrR;
    // Re-feed every frame from 0 up to the IDR (so decoder has full GOP)
    for (let i = 0; i < idrL; i++) {
      feedFrame(state.leftDec, state.leftNals[state.leftIdx], i);
      state.leftIdx++;
    }
    for (let i = 0; i < idrR; i++) {
      feedFrame(state.rightDec, state.rightNals[state.rightIdx], i);
      state.rightIdx++;
    }
    setPlaying(state.playing);
  });
  backBtn.addEventListener('click', () => {
    if (mp4Session) { mp4Session.seekDelta(-5); return; }
    if (!state.leftNals.length) return;
    const curT = state.leftIdx / state.leftNals.length;
    const newT = Math.max(0, curT - 5 / (state.totalFrames / 2 / 30));
    seek.value = Math.round(newT * 1000);
    seek.dispatchEvent(new Event('change'));
  });
  fwdBtn.addEventListener('click', () => {
    if (mp4Session) { mp4Session.seekDelta(5); return; }
    if (!state.leftNals.length) return;
    const curT = state.leftIdx / state.leftNals.length;
    const newT = Math.min(1, curT + 5 / (state.totalFrames / 2 / 30));
    seek.value = Math.round(newT * 1000);
    seek.dispatchEvent(new Event('change'));
  });

  loadBtn.addEventListener('click', () => loadFolder(folderInput.value.trim()));
  folderInput.addEventListener('keydown', e => { if (e.key === 'Enter') loadBtn.click(); });
  autoBtn.addEventListener('click', () => {
    const p = new URLSearchParams(location.search).get('path');
    if (p) { folderInput.value = p; loadFolder(p); }
    else err('URL ?path= 未提供');
  });

  // 启动时尝试从 ?path= 加载
  const initial = new URLSearchParams(location.search).get('path');
  if (initial) { folderInput.value = initial; autoBtn.click(); }
