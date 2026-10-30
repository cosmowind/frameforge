// hmd-inline-player.js — HMD stereo player (HEVC decode, WebCodecs)
// Extracted from index.html

/* ── HMD inline preview + scanner (added 2026-06-17) ─────────────── */
let hmdPanelSession = null;     // {folder, parts[], total_size, metadata}
let hmdLeftSession = null;       // session object from openHmdSession (left)
let hmdRightSession = null;      // session object from openHmdSession (right)
let hmdRafId = null;
let hmdLeftFrameCount = 0;
let hmdRightFrameCount = 0;
let hmdDurationSec = 0;
let hmdLeftFrameTime = 0;
let hmdRightFrameTime = 0;
let hmdPlaying = false;
let hmdRate = 1;  // 1, 5, 10, 16 — playback speed multiplier (driven by .hmd-rate-btn clicks)

const hmdState = {
  folder: null,
  info: null,
  hevc0: null,
  hevc1: null,
  vps: null, sps: null, pps: null,
  codecStr: null,
  desc: null,
  leftNals: [], leftIdx: 0, leftFirstIdr: 0,
  rightNals: [], rightIdx: 0, rightFirstIdr: 0,
  totalFrames: 0,
  leftDec: null, rightDec: null,
  leftFrame: null, rightFrame: null,
};

function closeHmdPanel() {
  document.getElementById('hmdPanel').style.display = 'none';
  stopHmdPlayback();
  const lc = document.getElementById('hmdLeftCanvas').getContext('2d');
  const rc = document.getElementById('hmdRightCanvas').getContext('2d');
  if (lc) lc.clearRect(0,0,960,540);
  if (rc) rc.clearRect(0,0,960,540);
  
  // Clean up frame preview if exists
  const frameContainer = document.getElementById('hmdFrameContainer');
  if (frameContainer) {
    frameContainer.style.display = 'none';
    frameContainer.innerHTML = '';
  }
  
  // Restore video stage visibility
  const stage = document.querySelector('.hmd-stage');
  if (stage) stage.style.display = '';
  
  // Restore controls visibility
  const controls = document.querySelector('.hmd-controls');
  if (controls) controls.style.display = '';
}

function setHmdErr(msg) {
  const el = document.getElementById('hmdErrBox');
  if (!msg) { el.style.display = 'none'; el.textContent = ''; return; }
  el.style.display = 'block'; el.textContent = msg;
}

async function openHmdPreviewInline(folder) {
  // 检查预处理状态：输出视频不存在时禁止预览
  const ps = _preprocessStatusMap[folder];
  if (ps && ps.hmd_preprocess && ps.hmd_preprocess !== 'done') {
    const statusLabel = ps.hmd_preprocess === 'processing' ? '处理中' : ps.hmd_preprocess === 'error' ? '失败' : '等待';
    const progressHint = ps.hmd_progress ? `（${ps.hmd_progress}%）` : '';
    showToast(`HMD 预处理${statusLabel}${progressHint}，暂无法预览。请等待预处理完成。`, 'warn');
    return;
  }

  // 显示 hmdPanel，用预处理后的 left.mp4 走 <video> 元素播放（同页内嵌，不弹新窗口）
  // 只有当 hmdPanel 不存在或 video 元素不可用时，才回退到系统播放器
  const panel = document.getElementById('hmdPanel');
  const leftVideo = document.getElementById('hmdLeftVideo');
  const meta = document.getElementById('hmdPanelMeta');
  if (!panel || !leftVideo) {
    return _openHmdWithSystemPlayer(folder);
  }

  // 关闭任何旧 session
  if (window.__hmdMp4Session) {
    try { window.__hmdMp4Session.close(); } catch {}
    window.__hmdMp4Session = null;
  }
  setHmdErr(null);

  // 把 rightVideo 藏起来（只播 left，节省 50% 带宽）
  const rightVideo = document.getElementById('hmdRightVideo');
  if (rightVideo) { rightVideo.hidden = true; rightVideo.removeAttribute('src'); rightVideo.load(); }
  // 把 canvas 藏起来
  const leftCanvas = document.getElementById('hmdLeftCanvas');
  const rightCanvas = document.getElementById('hmdRightCanvas');
  if (leftCanvas) leftCanvas.style.display = 'none';
  if (rightCanvas) rightCanvas.style.display = 'none';
  leftVideo.hidden = false;
  leftVideo.muted = true;  // autoplay-safe
  leftVideo.playsInline = true;
  leftVideo.controls = true;  // 显示原生视频控件（用户能直接点播放/暂停/进度条）

  // 路径归一化（backslash → forward-slash）
  const normalizedFolder = (folder || '').replace(/\\/g, '/');
  const leftUrl = '/api/hmd/mp4?folder=' + encodeURIComponent(normalizedFolder) + '&eye=left';

  panel.style.display = 'block';
  if (meta) meta.textContent = `${folder} · 加载中…`;

  // 先用 API 检查 MP4 是否真的可用
  let mp4Ok = false;
  let durationSec = 0;
  try {
    const statusResp = await fetch('/api/hmd/process-status?folder=' + encodeURIComponent(normalizedFolder));
    if (statusResp.ok) {
      const st = await statusResp.json();
      if (st.status === 'done') {
        mp4Ok = true;
        durationSec = st.duration_sec || 0;
      }
    }
  } catch (e) {
    console.warn('[HMD] status check failed:', e);
  }

  if (!mp4Ok) {
    // MP4 还没就绪 → 回退到系统播放器
    if (meta) meta.textContent = `${folder} · 浏览器内播放不可用，调用系统播放器`;
    panel.style.display = 'none';
    return _openHmdWithSystemPlayer(folder);
  }

  // 浏览器不支持 HEVC 时自动回退到系统播放器
  let fellBackToSystem = false;
  const onLoadError = () => {
    if (fellBackToSystem) return;
    fellBackToSystem = true;
    console.warn('[HMD] Browser cannot decode MP4, falling back to system player');
    showToast('浏览器无法解码该视频（可能缺少 HEVC 编码器），已用系统播放器打开', 'warn');
    panel.style.display = 'none';
    _openHmdWithSystemPlayer(folder);
  };
  leftVideo.onerror = onLoadError;

  // 设置 video src 并播放
  leftVideo.src = leftUrl;
  leftVideo.preload = 'auto';
  leftVideo.load();

  // 等 metadata
  try {
    await new Promise((resolve) => {
      if (leftVideo.readyState >= 1 && isFinite(leftVideo.duration) && leftVideo.duration > 0) {
        resolve();
      } else {
        const onMeta = () => { leftVideo.removeEventListener('loadedmetadata', onMeta); resolve(); };
        leftVideo.addEventListener('loadedmetadata', onMeta);
        setTimeout(resolve, 5000);
      }
    });
  } catch (e) {
    console.warn('[HMD] video metadata load failed:', e);
  }

  // 元信息
  const realDur = isFinite(leftVideo.duration) && leftVideo.duration > 0 ? leftVideo.duration : durationSec;
  if (meta) meta.textContent = `${folder} · MP4 秒开 · ${fmtHmdTime(realDur)}`;

  // 启用控制按钮（基于 MP4 模式）
  window.__hmdMp4Session = {
    leftVideo,
    rightVideo: null,
    play() { leftVideo.play().catch(() => {}); },
    pause() { leftVideo.pause(); },
    toggle() {
      const playing = !leftVideo.paused;
      if (playing) leftVideo.pause(); else leftVideo.play().catch(() => {});
      return !playing;
    },
    seek(sec) { leftVideo.currentTime = sec; },
    seekDelta(d) { leftVideo.currentTime = Math.max(0, leftVideo.currentTime + d); },
    close() { leftVideo.pause(); leftVideo.removeAttribute('src'); leftVideo.load(); },
    getDuration() { return isFinite(leftVideo.duration) ? leftVideo.duration : 0; },
  };
  enableHmdControls(true);
  // 同步到 seek bar
  const seek = document.getElementById('hmdSeek');
  if (seek) {
    seek.max = Math.round(realDur) || 1;
    seek.value = 0;
  }
  // 同步时间显示
  const updateTime = () => {
    if (!leftVideo || !isFinite(leftVideo.currentTime)) return;
    const t = leftVideo.currentTime;
    if (meta) meta.textContent = `${folder} · ${fmtHmdTime(t)} / ${fmtHmdTime(realDur)}`;
    if (document.activeElement !== seek && seek) {
      seek.value = Math.min(parseInt(seek.max || 1), Math.round(t));
    }
    const hudEl = document.getElementById('hmdHudEl');
    if (hudEl) hudEl.textContent = `L=${t.toFixed(2)}s`;
  };
  leftVideo.ontimeupdate = updateTime;
  leftVideo.onplay = () => { setHmdPlaying(true); updateTime(); };
  leftVideo.onpause = () => { setHmdPlaying(false); updateTime(); };
  leftVideo.onended = () => { setHmdPlaying(false); updateTime(); };

  // 自动播放（可能被浏览器拦截）
  const playPromise = leftVideo.play();
  if (playPromise && playPromise.catch) {
    playPromise.catch(err => {
      console.warn('[HMD] autoplay failed:', err);
      if (meta && !fellBackToSystem) meta.textContent = `${folder} · 点击播放按钮开始播放`;
    });
  }

  // 滚到面板
  panel.scrollIntoView({ behavior: 'smooth', block: 'start' });

  // 只在视频真的能播放时才提示"已在浏览器内打开"；如果 readyState/duration 都不正常，说明浏览器无法解码
  const playable = leftVideo.readyState >= 1 && isFinite(leftVideo.duration) && leftVideo.duration > 0;
  if (playable && !fellBackToSystem) {
    showToast('已在浏览器内打开预览', 'info');
  } else if (!fellBackToSystem) {
    showToast('浏览器可能无法解码该视频，正尝试系统播放器…', 'warn');
  }
}

// 后备：调系统播放器（仅在 hmdPanel 不可用时）
async function _openHmdWithSystemPlayer(folder) {
  try {
    const resp = await fetch('/api/hmd/open', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({folder: folder})
    });
    if (resp.ok) {
      const result = await resp.json();
      console.log('[HMD] Opened with system player:', result.path);
      showToast('已用系统播放器打开预览视频', 'info');
      return;
    } else {
      const err = await resp.json();
      showToast(err.error || '无法打开预览视频', 'error');
    }
  } catch (e) {
    console.error('Failed to open with system player:', e);
    showToast('打开播放器失败：' + (e.message || String(e)), 'error');
  }
}

async function openHmdFramePreview(folder) {
  // Display extracted frames as preview instead of playing video.
  // This is a lightweight alternative when MP4 playback is not available.
  const panel = document.getElementById('hmdPanel');
  const meta = document.getElementById('hmdPanelMeta');
  
  meta.textContent = '正在提取预览帧…';
  
  try {
    // Hide video/canvas elements
    const _lc = document.getElementById('hmdLeftCanvas');
    const _rc = document.getElementById('hmdRightCanvas');
    const _lv = document.getElementById('hmdLeftVideo');
    const _rv = document.getElementById('hmdRightVideo');
    if (_lc) _lc.style.display = 'none';
    if (_rc) _rc.style.display = 'none';
    if (_lv) _lv.hidden = true;
    if (_rv) _rv.hidden = true;
    
    // Fetch frames from API
    const resp = await fetch('/api/hmd/frames?folder=' + encodeURIComponent(folder));
    if (!resp.ok) throw new Error('Failed to fetch frames: HTTP ' + resp.status);
    
    const data = await resp.json();
    if (!data.frames || data.frames.length === 0) {
      throw new Error('没有可用的预览帧');
    }
    
    meta.textContent = `预览帧 (${data.frames.length} 帧) - ${folder}`;
    
    // Create frame preview container if not exists
    let frameContainer = document.getElementById('hmdFrameContainer');
    if (!frameContainer) {
      frameContainer = document.createElement('div');
      frameContainer.id = 'hmdFrameContainer';
      frameContainer.style.cssText = 'display:flex;flex-wrap:wrap;gap:10px;padding:10px;overflow-y:auto;max-height:600px;';
      // Insert after the stage div
      const stage = panel.querySelector('.hmd-stage');
      if (stage) {
        stage.style.display = 'none'; // Hide the video stage
        panel.insertBefore(frameContainer, stage.nextSibling);
      }
    }
    
    // Clear previous frames
    frameContainer.innerHTML = '';
    
    // Add frames to container
    data.frames.forEach((frame, idx) => {
      const wrapper = document.createElement('div');
      wrapper.style.cssText = 'text-align:center;';
      
      const img = document.createElement('img');
      img.src = frame.url;
      img.style.cssText = 'width:320px;border:1px solid #444;border-radius:4px;cursor:pointer;display:block;';
      img.loading = 'lazy';
      img.onclick = () => window.open(frame.url, '_blank');
      
      const label = document.createElement('div');
      label.textContent = `帧 ${idx + 1}`;
      label.style.cssText = 'font-size:11px;color:#9aa4ad;margin-top:4px;';
      
      wrapper.appendChild(img);
      wrapper.appendChild(label);
      frameContainer.appendChild(wrapper);
    });
    
    frameContainer.style.display = 'flex';
    
    // Hide controls (not needed for frame preview)
    const controls = panel.querySelector('.hmd-controls');
    if (controls) controls.style.display = 'none';
    
  } catch (e) {
    setHmdErr(e.message || String(e));
    meta.textContent = '预览帧提取失败';
  }
}

function frameToNals(hevc, paramSets) {
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
      const nt = (nal[4] >> 1) & 0x3f;
      nals.push({ type: nt, data: nal });
      i = j;
    } else i++;
  }
  let firstIdr = 0;
  for (let k = 0; k < nals.length; k++) {
    if (nals[k].type === 19 || nals[k].type === 20) { firstIdr = k; break; }
  }
  return { nals, firstIdr };
}

function stripHmdSc(nal) {
  return (nal[0]===0&&nal[1]===0&&nal[2]===0&&nal[3]===1) ? nal.subarray(4) : nal;
}
function avccWrapUmi(nal) {
  const body = stripHmdSc(nal);
  const out = new Uint8Array(4 + body.length);
  new DataView(out.buffer).setUint32(0, body.length, false);
  out.set(body, 4);
  return out;
}
function buildHmdHevcDesc(vpsNal, spsNal, ppsNal) {
  const spsBody = stripHmdSc(spsNal);
  const vpsBody = stripHmdSc(vpsNal);
  const ppsBody = stripHmdSc(ppsNal);
  const profile_space = (spsBody[3] >> 6) & 0x03;
  const tier_flag = (spsBody[3] >> 5) & 0x01;
  const profile_idc = spsBody[3] & 0x1f;
  const profile_compat = spsBody.subarray(4, 8);
  const constraint = new Uint8Array(6);
  constraint[0] = spsBody[8] & 0xf0;
  let level_idc = spsBody[14];
  if (level_idc === 0) level_idc = 120;
  const out = [];
  const push = a => out.push(a);
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
  push(new Uint8Array([(vpsBody.length >> 8) & 0xff, vpsBody.length & 0xff]));
  push(vpsBody);
  push(new Uint8Array([0x21])); push(new Uint8Array([0, 1]));
  push(new Uint8Array([(spsBody.length >> 8) & 0xff, spsBody.length & 0xff]));
  push(spsBody);
  push(new Uint8Array([0x22])); push(new Uint8Array([0, 1]));
  push(new Uint8Array([(ppsBody.length >> 8) & 0xff, ppsBody.length & 0xff]));
  push(ppsBody);
  let total = 0; for (const a of out) total += a.length;
  const merged = new Uint8Array(total);
  let off = 0; for (const a of out) { merged.set(a, off); off += a.length; }
  return merged;
}
function codecStrFromSps(spsNal) {
  const o = (spsNal[0]===0&&spsNal[1]===0&&spsNal[2]===0&&spsNal[3]===1) ? 4 : 0;
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

function setupHmdDecoders() {
  if (hmdState.leftDec) try { hmdState.leftDec.close(); } catch {}
  if (hmdState.rightDec) try { hmdState.rightDec.close(); } catch {}
  const lc = document.getElementById('hmdLeftCanvas').getContext('2d');
  const rc = document.getElementById('hmdRightCanvas').getContext('2d');
  hmdState.leftDec = new VideoDecoder({
    output: f => {
      if (hmdState.leftFrame) try { hmdState.leftFrame.close(); } catch {}
      hmdState.leftFrame = f;
      hmdLeftFrameCount++;
      hmdLeftFrameTime = f.timestamp / 1e6;
      const c = document.getElementById('hmdLeftCanvas');
      if (c.width !== f.codedWidth) c.width = f.codedWidth;
      if (c.height !== f.codedHeight) c.height = f.codedHeight;
      lc.drawImage(f, 0, 0, c.width, c.height);
      document.getElementById('hmdLeftStat').textContent =
        `${f.codedWidth}x${f.codedHeight} t=${(f.timestamp/1e6).toFixed(2)}s`;
    },
    error: e => setHmdErr('左眼 decode: ' + e.message),
  });
  hmdState.rightDec = new VideoDecoder({
    output: f => {
      if (hmdState.rightFrame) try { hmdState.rightFrame.close(); } catch {}
      hmdState.rightFrame = f;
      hmdRightFrameCount++;
      hmdRightFrameTime = f.timestamp / 1e6;
      const c = document.getElementById('hmdRightCanvas');
      if (c.width !== f.codedWidth) c.width = f.codedWidth;
      if (c.height !== f.codedHeight) c.height = f.codedHeight;
      rc.drawImage(f, 0, 0, c.width, c.height);
      document.getElementById('hmdRightStat').textContent =
        `${f.codedWidth}x${f.codedHeight} t=${(f.timestamp/1e6).toFixed(2)}s`;
    },
    error: e => setHmdErr('右眼 decode: ' + e.message),
  });
  try {
    hmdState.leftDec.configure({ codec: hmdState.codecStr, codedWidth: 1920, codedHeight: 1080, description: hmdState.desc });
    hmdState.rightDec.configure({ codec: hmdState.codecStr, codedWidth: 1920, codedHeight: 1080, description: hmdState.desc });
  } catch (e) {
    hmdState.codecStr = 'hev1.1.6.L93.B0';
    hmdState.leftDec.configure({ codec: hmdState.codecStr, codedWidth: 1920, codedHeight: 1080, description: hmdState.desc });
    hmdState.rightDec.configure({ codec: hmdState.codecStr, codedWidth: 1920, codedHeight: 1080, description: hmdState.desc });
  }
}
function feedHmdFrame(dec, nalEntry, frameIdx) {
  if (nalEntry.type === 'ps') return;
  const isKey = nalEntry.type === 19 || nalEntry.type === 20;
  const data = avccWrapUmi(nalEntry.data);
  const dur = Math.round(1e6 / 30);
  dec.decode(new EncodedVideoChunk({ type: isKey ? 'key' : 'delta', timestamp: frameIdx * dur, duration: dur, data }));
}
// Rate-controlled feeder: feed only as many frames as the rate allows
// per RAF tick (so 1x = 30 fps, 16x = 480 fps effective). Tracks
// frameBudget (fractional) so we don't drop frames on slow ticks.
let hmdFrameDebtL = 0;   // accumulated frames to feed (left)
let hmdFrameDebtR = 0;   // (right)
function primeHmdDecoders() {
  const rate = hmdRate || 1;
  // At 30 fps native, frames per second = 30 * rate. Per RAF tick
  // (~16.67 ms @ 60 Hz), frames = 30 * rate / 60 = rate / 2.
  const fps = 30 * rate;
  const framesPerTick = fps / 60;
  hmdFrameDebtL += framesPerTick;
  hmdFrameDebtR += framesPerTick;
  const maxBurst = Math.max(1, Math.ceil(rate) * 2);  // cap to avoid runaway
  let fL = 0, fR = 0;
  while (hmdState.leftIdx < hmdState.leftNals.length && fL < maxBurst && hmdFrameDebtL >= 1) {
    feedHmdFrame(hmdState.leftDec, hmdState.leftNals[hmdState.leftIdx], fL);
    hmdState.leftIdx++; fL++; hmdFrameDebtL--;
  }
  while (hmdState.rightIdx < hmdState.rightNals.length && fR < maxBurst && hmdFrameDebtR >= 1) {
    feedHmdFrame(hmdState.rightDec, hmdState.rightNals[hmdState.rightIdx], fR);
    hmdState.rightIdx++; fR++; hmdFrameDebtR--;
  }
}

function enableHmdControls(on) {
  ['hmdPlayBtn', 'hmdBackBtn', 'hmdFwdBtn', 'hmdSeek'].forEach(id =>
    document.getElementById(id).disabled = !on);
  if (on) {
    document.getElementById('hmdSeek').max = Math.round(hmdDurationSec) || 1;
    // Reset rate debt so the first tick at the new rate doesn't burst
    hmdFrameDebtL = 0; hmdFrameDebtR = 0;
  }
}

function setHmdPlaying(on) {
  hmdPlaying = on;
  document.getElementById('hmdPlayBtn').textContent = on ? '⏸' : '⏯';
  if (on) {
    if (hmdRafId) cancelAnimationFrame(hmdRafId);
    hmdRafId = requestAnimationFrame(hmdPlaybackLoop);
  } else {
    if (hmdRafId) cancelAnimationFrame(hmdRafId);
    hmdRafId = null;
  }
}
function hmdPlaybackLoop() {
  if (!hmdPlaying) return;
  // In MP4 mode, this loop should not run (video element handles playback)
  if (isMp4Mode()) {
    return;
  }
  if (hmdState.leftDec && hmdState.leftDec.decodeQueueSize < 6) primeHmdDecoders();
  if (hmdState.rightDec && hmdState.rightDec.decodeQueueSize < 6) primeHmdDecoders();
  // Update HUD
  const seek = document.getElementById('hmdSeek');
  const t = hmdState.leftIdx / 30;
  if (document.activeElement !== seek) seek.value = Math.min(parseInt(seek.max || 1), Math.round(t));
  document.getElementById('hmdTimeEl').textContent =
    `${fmtHmdTime(t)} / ${fmtHmdTime(hmdDurationSec)}`;
  document.getElementById('hmdHudEl').textContent =
    `L=${hmdState.leftIdx}/${hmdState.leftNals.length} R=${hmdState.rightIdx}/${hmdState.rightNals.length}`;
  if (hmdState.leftIdx >= hmdState.leftNals.length && hmdState.leftDec.decodeQueueSize === 0) {
    setHmdPlaying(false);
    return;
  }
  hmdRafId = requestAnimationFrame(hmdPlaybackLoop);
}

function stopHmdPlayback() {
  setHmdPlaying(false);
  if (hmdState.leftDec) try { hmdState.leftDec.close(); } catch {}
  if (hmdState.rightDec) try { hmdState.rightDec.close(); } catch {}
  if (hmdState.leftFrame) try { hmdState.leftFrame.close(); } catch {}
  if (hmdState.rightFrame) try { hmdState.rightFrame.close(); } catch {}
  hmdState.leftDec = null; hmdState.rightDec = null;
  hmdState.leftFrame = null; hmdState.rightFrame = null;
}

function fmtHmdTime(sec) {
  if (!isFinite(sec)) sec = 0;
  sec = Math.max(0, sec);
  const m = Math.floor(sec / 60);
  const s = sec - m * 60;
  return `${String(m).padStart(2,'0')}:${s.toFixed(1).padStart(4,'0')}`;
}

// Wire up toolbar buttons once DOM ready
function isMp4Mode() { return !!window.__hmdMp4Session; }
document.getElementById('hmdPlayBtn').onclick = () => {
  if (isMp4Mode()) {
    const nowPlaying = window.__hmdMp4Session.toggle();
    setHmdPlaying(nowPlaying);
  } else {
    setHmdPlaying(!hmdPlaying);
  }
};
document.getElementById('hmdBackBtn').onclick = () => {
  if (isMp4Mode()) { window.__hmdMp4Session.seekDelta(-5); return; }
  if (!hmdState.leftNals.length) return;
  const seek = document.getElementById('hmdSeek');
  seek.value = Math.max(0, parseInt(seek.value) - 5);
  seek.dispatchEvent(new Event('change'));
};
document.getElementById('hmdFwdBtn').onclick = () => {
  if (isMp4Mode()) { window.__hmdMp4Session.seekDelta(5); return; }
  if (!hmdState.leftNals.length) return;
  const seek = document.getElementById('hmdSeek');
  seek.value = Math.min(parseInt(seek.max), parseInt(seek.value) + 5);
  seek.dispatchEvent(new Event('change'));
};
// Rate buttons (1x / 5x / 10x / 16x) — only WebCodecs mode honours them
document.querySelectorAll('.hmd-rate-btn').forEach(btn => {
  btn.onclick = () => {
    hmdRate = parseFloat(btn.dataset.rate);
    hmdFrameDebtL = 0;
    hmdFrameDebtR = 0;
    document.querySelectorAll('.hmd-rate-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    if (isMp4Mode()) {
      const v = document.getElementById('hmdLeftVideo');
      v.playbackRate = hmdRate;
      const v2 = document.getElementById('hmdRightVideo');
      v2.playbackRate = hmdRate;
    }
  };
});
// Default: 1× active
document.querySelector('.hmd-rate-btn[data-rate="1"]').classList.add('active');

// ─── MP4 mode activation (uses preprocessed left.mp4 only via <video>) ───
async function activateInlineMp4Mode(mp4, folder) {
  window.__hmdMp4Session = mp4;
  const lc = document.getElementById('hmdLeftCanvas');
  const rc = document.getElementById('hmdRightCanvas');
  const lv = document.getElementById('hmdLeftVideo');
  const rv = document.getElementById('hmdRightVideo');
  lc.style.display = 'none';
  rc.style.display = 'none';
  // Hide the right video element entirely (we only play left)
  lv.hidden = false;
  if (rv) { rv.hidden = true; rv.removeAttribute('src'); rv.load(); }
  // Wait for left video metadata
  console.log('[DEBUG] activateInlineMp4Mode: Waiting for video metadata...');
  console.log('[DEBUG] leftVideo.src before load:', lv.src);
  
  // Add error listeners
  lv.onerror = () => {
    console.error('[DEBUG] Video error event:', lv.error);
    if (lv.error) {
      console.error('[DEBUG] Video error code:', lv.error.code);
      console.error('[DEBUG] Video error message:', lv.error.message);
    }
  };
  lv.onabort = () => console.warn('[DEBUG] Video load aborted');
  lv.onstalled = () => console.warn('[DEBUG] Video load stalled');
  lv.onsuspend = () => console.warn('[DEBUG] Video load suspended');
  
  lv.load();  // Force reload after setting src
  console.log('[DEBUG] leftVideo.src after load:', lv.src);
  console.log('[DEBUG] leftVideo.readyState after load:', lv.readyState);
  
  await new Promise((resolve) => {
    if (lv.readyState >= 1 && isFinite(lv.duration) && lv.duration > 0) {
      console.log('[DEBUG] Video metadata already loaded, duration:', lv.duration);
      resolve();
    } else {
      const onMeta = () => { 
        console.log('[DEBUG] Video metadata loaded, duration:', lv.duration);
        lv.removeEventListener('loadedmetadata', onMeta); 
        resolve(); 
      };
      lv.addEventListener('loadedmetadata', onMeta);
      setTimeout(() => {
        console.error('[DEBUG] Timeout waiting for video metadata, readyState:', lv.readyState);
        console.error('[DEBUG] Video error:', lv.error);
        resolve();
      }, 10000);  // Increase timeout to 10 seconds
    }
  });
  console.log('[DEBUG] Video metadata ready, binding events...');
  mp4.bindEvents({
    onPlay: () => setHmdPlaying(true),
    onPause: () => setHmdPlaying(false),
    onEnded: () => setHmdPlaying(false),
    onTimeUpdate: (tL, tR) => {
      const dur = mp4.getDuration() || 0;
      const seek = document.getElementById('hmdSeek');
      if (document.activeElement !== seek && dur > 0) {
        seek.value = Math.min(parseInt(seek.max || 1000), Math.round((tL / dur) * 1000));
      }
      document.getElementById('hmdTimeEl').textContent = `${fmtHmdTime(tL)} / ${fmtHmdTime(dur)}`;
      document.getElementById('hmdHudEl').textContent = `L=${tL.toFixed(2)}s R=${tR.toFixed(2)}s`;
      document.getElementById('hmdLeftStat').textContent = `${(lv.videoWidth||0)}x${lv.videoHeight||0} t=${tL.toFixed(2)}s`;
      document.getElementById('hmdRightStat').textContent = `${(rv.videoWidth||0)}x${rv.videoHeight||0} t=${tR.toFixed(2)}s`;
    },
  });
  enableHmdControls(true);
  // seek bar: 0..1000 normalized
  document.getElementById('hmdSeek').max = 1000;
  const dur = mp4.getDuration() || 0;
  document.getElementById('hmdPanelMeta').textContent =
    `${folder} · MP4 秒开 · ${fmtHmdTime(dur)}`;
  // Auto-play (may fail due to autoplay policy)
  console.log('[DEBUG] activateInlineMp4Mode: Attempting to play video');
  console.log('[DEBUG] leftVideo element:', lv);
  console.log('[DEBUG] leftVideo.readyState:', lv.readyState);
  console.log('[DEBUG] leftVideo.currentTime:', lv.currentTime);
  console.log('[DEBUG] leftVideo.paused:', lv.paused);
  
  const playPromise = mp4.play();
  if (playPromise instanceof Promise) {
    playPromise.then(() => {
      console.log('[DEBUG] Video playback started successfully');
    }).catch((err) => {
      console.warn('[DEBUG] Video playback failed (autoplay policy?):', err);
      console.log('[DEBUG] Video error:', lv.error);
      // Autoplay was prevented - show a message to user
      document.getElementById('hmdPanelMeta').textContent = '点击播放按钮开始播放';
    });
  }
}

document.getElementById('hmdSeek').onchange = () => {
  if (isMp4Mode()) {
    const mp4 = window.__hmdMp4Session;
    const dur = mp4.getDuration() || 0;
    if (dur > 0) mp4.seek(dur * (parseInt(document.getElementById('hmdSeek').value) / 1000));
    return;
  }
  if (!hmdState.leftNals.length) return;
  const seek = document.getElementById('hmdSeek');
  const sec = parseInt(seek.value);
  const targetL = sec * 30;
  const targetR = sec * 30;
  function findIdrAtOrBefore(nals, target, fallback) {
    let idr = fallback;
    for (let k = 0; k < target && k < nals.length; k++) {
      const t = nals[k].type;
      if (t === 19 || t === 20) idr = k;
    }
    return idr;
  }
  const idrL = findIdrAtOrBefore(hmdState.leftNals, targetL, hmdState.leftFirstIdr);
  const idrR = findIdrAtOrBefore(hmdState.rightNals, targetR, hmdState.rightFirstIdr);
  setupHmdDecoders();
  hmdState.leftIdx = idrL; hmdState.rightIdx = idrR;
  hmdFrameDebtL = 0; hmdFrameDebtR = 0;  // reset rate debt on seek
  for (let i = 0; i < idrL; i++) {
    feedHmdFrame(hmdState.leftDec, hmdState.leftNals[hmdState.leftIdx], i);
    hmdState.leftIdx++;
  }
  for (let i = 0; i < idrR; i++) {
    feedHmdFrame(hmdState.rightDec, hmdState.rightNals[hmdState.rightIdx], i);
    hmdState.rightIdx++;
  }
  setHmdPlaying(hmdPlaying);
};
