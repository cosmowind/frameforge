// hmd-progress.js — HMD preprocessing progress panel
// Extracted from index.html

// ---- 预处理进度面板 ----
let _progressTimer = null;

function toggleProgressPanel() {
  const panel = document.getElementById('progressPanel');
  if (panel.style.display === 'none') {
    panel.style.display = 'block';
    refreshProgress();
    startAutoRefresh();
  } else {
    panel.style.display = 'none';
    stopAutoRefresh();
  }
}

function startAutoRefresh() {
  stopAutoRefresh();
  if (document.getElementById('chkAutoRefresh').checked) {
    _progressTimer = setInterval(refreshProgress, 3000);
  }
}

function stopAutoRefresh() {
  if (_progressTimer) { clearInterval(_progressTimer); _progressTimer = null; }
}

function toggleAutoRefresh() {
  if (document.getElementById('chkAutoRefresh').checked) {
    refreshProgress();
    startAutoRefresh();
  } else {
    stopAutoRefresh();
  }
}

async function refreshProgress() {
  try {
    // Refresh queue cache in parallel with overview
    const [overviewRes, queueRes] = await Promise.all([
      fetch('/api/preprocess-overview'),
      fetch('/api/hmd/queue-status').catch(() => null),
    ]);
    if (queueRes && queueRes.ok) {
      _hmdQueueCache = await queueRes.json();
    }
    const data = await overviewRes.json();
    renderProgress(data);
    
    // 缓存预处理状态，供 renderTable 按钮状态判断
    _preprocessStatusMap = {};
    (data.items || []).forEach(it => { _preprocessStatusMap[it.path] = it; });
    
    // Auto-trigger frame generation for videos that have completed HMD preprocess
    // but don't have frames yet
    // DISABLED: 磁盘满时禁止自动生成预览帧
    // const items = data.items || [];
    // const needFrames = items.filter(it => 
    //   it.hmd_preprocess === 'done' && 
    //   (it.frames === 'pending' || it.frames === 'error') &&
    //   it.file_type === 'hmd'
    // );
    // if (needFrames.length > 0 && !_framesWarmInProgress) {
    //   _framesWarmInProgress = true;
    //   const framePaths = needFrames.map(it => it.path);
    //   fetch('/api/frames/warm', { 
    //     method: 'POST', 
    //     headers: {'Content-Type': 'application/json'}, 
    //     body: JSON.stringify({paths: framePaths}) 
    //   }).finally(() => {
    //     _framesWarmInProgress = false;
    //   });
    // }
  } catch (e) { /* ignore */ }
}

let _framesWarmInProgress = false;  // Prevent multiple simultaneous frame warm requests

let _hmdQueueCache = null;  // {active_folder, queue} cached from /api/hmd/queue-status
let _preprocessStatusMap = {};  // {path: {hmd_preprocess, frames, thumb, ...}} 索引预处理状态

async function _refreshHmdQueueCache() {
  try {
    const res = await fetch('/api/hmd/queue-status');
    _hmdQueueCache = await res.json();
  } catch (e) {
    _hmdQueueCache = null;
  }
}

function _getHmdQueueLabel(folder) {
  /**Return a human-readable label for this folder's queue position, or '' if not in queue. */
  const q = _hmdQueueCache;
  if (!q) return '';
  if (q.active_folder === folder) return '🎬处理中';
  const pos = q.queue ? q.queue.indexOf(folder) : -1;
  if (pos >= 0) return `🎬排队${pos + 1}/${q.queue.length}`;
  return '';
}

function renderProgress(data) {
  const summary = document.getElementById('progressSummary');
  const bars = document.getElementById('progressBars');
  const details = document.getElementById('progressDetails');

  // 简化 summary：只显示"正在处理 X / 已完成 Y / 总 Z"
  const t = data.total;
  const td = data.thumb.done;
  const fd = data.frames.done || 0;
  const up = data.hmd_preprocess;
  const hmdTotal = (up.done||0) + (up.processing||0) + (up.pending||0) + (up.error||0);
  const hmdDone = up.done || 0;
  const hmdProc = up.processing || 0;
  const queueLen = (_hmdQueueCache && _hmdQueueCache.queue) ? _hmdQueueCache.queue.length : 0;

  // 找"正在处理"和"下一个排队"
  const active = (_hmdQueueCache && _hmdQueueCache.active_folder)
    ? _hmdQueueCache.active_folder.split(/[\\/]/).pop()
    : null;
  const next = (_hmdQueueCache && _hmdQueueCache.queue && _hmdQueueCache.queue[0])
    ? _hmdQueueCache.queue[0].split(/[\\/]/).pop()
    : null;

  // 拼装简洁文本
  let parts = [];
  if (active) {
    parts.push(`⏳ 正在：<b>${active}</b>`);
    if (hmdDone) parts.push(`已完成 <b>${hmdDone}</b>/${hmdTotal}`);
    if (queueLen) parts.push(`排队 <b>${queueLen}</b>`);
  } else if (hmdTotal > 0) {
    if (hmdDone === hmdTotal && hmdTotal > 0) {
      parts.push('<b style="color:#52c41a;">✅ 全部预处理完成</b>');
    } else if (hmdDone > 0) {
      parts.push(`已完成 <b>${hmdDone}</b>/${hmdTotal}`);
    } else {
      parts.push(`待处理 <b>${hmdTotal}</b>`);
    }
  } else {
    parts.push('无预处理任务');
  }
  if (next && !active) {
    parts.push(`下一个：${next}`);
  }
  summary.innerHTML = parts.join(' · ');

  // Progress bars - 简化为单个 HMD 总进度
  bars.innerHTML = '';
  if (hmdTotal > 0) {
    const hmdPct = Math.round((hmdDone / hmdTotal) * 100);
    bars.appendChild(_makeBar('HMD 预处理', hmdPct, {
      done: hmdDone, processing: hmdProc, pending: up.pending, error: up.error
    }));
  }
  // Frames bar (6-frame preview)
  const framesPct = t > 0 ? Math.round(((data.frames.done||0) / t) * 100) : 0;
  bars.appendChild(_makeBar('预览帧', framesPct, data.frames));
  // Duration bar
  const durPct = t > 0 ? Math.round(((data.duration.done||0) / t) * 100) : 0;
  bars.appendChild(_makeBar('时长', durPct, data.duration));
  // HMD preprocess bar (only if there are HMD videos)
  if (hmdTotal > 0) {
    const hmdDone = (up.done||0) + (up.error||0);  // count errors as "finished"
    const hmdPct = hmdTotal > 0 ? Math.round((hmdDone / hmdTotal) * 100) : 0;
    bars.appendChild(_makeBar('HMD预处理', hmdPct, up));
  }

  // Details table
  details.innerHTML = '';
  if (data.items && data.items.length > 0) {
    const active = data.items.filter(it =>
      it.thumb === 'processing' || it.thumb === 'pending' || it.thumb === 'error' ||
      (it.hmd_preprocess === 'processing' || it.hmd_preprocess === 'pending' || it.hmd_preprocess === 'error') ||
      (_getHmdQueueLabel(it.path) && it.hmd_preprocess !== 'done') ||
      // Show videos that have completed HMD preprocess but missing frames
      (it.file_type === 'hmd' && it.hmd_preprocess === 'done' && it.frames !== 'done') ||
      // Show MP4 videos missing frames
      (it.file_type === 'mp4' && it.frames !== 'done')
    );
    if (active.length === 0) {
      details.innerHTML = '<div style="color:#999;">所有视频已处理完成 ✓</div>';
    } else {
      for (const it of active.slice(0, 80)) {
        const div = document.createElement('div');
        div.style.cssText = 'display:flex; gap:12px; padding:4px 0; border-bottom:1px solid #f0f0f0; align-items:center;';
        const name = it.path.split(/[\\/]/).pop();
        let statusText = '';
        // Thumb status
        if (it.thumb === 'processing') statusText += '🖼️处理中 ';
        else if (it.thumb === 'pending') statusText += '🖼️等待 ';
        else if (it.thumb === 'done') statusText += '🖼️✓ ';
        else if (it.thumb === 'error') statusText += '🖼️失败 ';
        // Frames status
        if (it.frames === 'processing') statusText += `🎞️${it.frames_progress||0}% `;
        else if (it.frames === 'pending') statusText += '🎞️等待 ';
        else if (it.frames === 'done') statusText += '🎞️✓ ';
        else if (it.frames === 'error') statusText += '🎞️失败 ';
        // HMD status: prefer queue cache, fall back to hmd_preprocess field
        const qLabel = _getHmdQueueLabel(it.path);
        if (qLabel) {
          statusText += qLabel + ' ';
        } else if (it.hmd_preprocess) {
          if (it.hmd_preprocess === 'processing') statusText += `🎬${it.hmd_stage||'处理中'} ${it.hmd_progress||0}% `;
          else if (it.hmd_preprocess === 'pending') statusText += '🎬等待 ';
          else if (it.hmd_preprocess === 'done') statusText += '🎬✓ ';
          else if (it.hmd_preprocess === 'error') statusText += '🎬失败 ';
        }
        // Show duration if available
        if (it.duration_sec) {
          const d = parseFloat(it.duration_sec);
          if (d > 0) {
            const m = Math.floor(d / 60);
            const s = Math.round(d % 60);
            statusText += `⏱${m}:${String(s).padStart(2,'0')} `;
          }
        }
        let retryBtn = '';
        if (it.file_type === 'hmd' && it.hmd_preprocess === 'error') {
          const safePath = it.path.replace(/"/g, '&quot;');
          retryBtn = ` <button class="btn btn-small btn-warning" data-folder="${safePath}" onclick="retryHmdFromBtn(this)" title="重新预处理">重试</button>`;
        }
        div.innerHTML = `<span style="color:#888; flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; min-width:0;" title="${it.path}">${name}</span><span style="color:#666; white-space:nowrap;">${statusText}</span>${retryBtn}`;
        details.appendChild(div);
      }
      if (active.length > 80) {
        const more = document.createElement('div');
        more.style.cssText = 'color:#999; padding:4px 0;';
        more.textContent = `... 还有 ${active.length - 80} 个视频`;
        details.appendChild(more);
      }
    }
  }
}

function _makeBar(label, pct, counts) {
  const wrap = document.createElement('div');
  wrap.style.cssText = 'flex:1; min-width:160px;';
  const labelEl = document.createElement('div');
  labelEl.style.cssText = 'font-size:11px; color:#888; margin-bottom:3px;';
  labelEl.textContent = `${label} ${pct}%`;
  wrap.appendChild(labelEl);
  const track = document.createElement('div');
  track.style.cssText = 'height:10px; background:#f0f0f0; border-radius:5px; overflow:hidden;';
  const fill = document.createElement('div');
  fill.style.cssText = `height:100%; width:${pct}%; background:linear-gradient(90deg,#1677ff,#52c41a); border-radius:5px; transition:width 0.4s;`;
  track.appendChild(fill);
  wrap.appendChild(track);
  return wrap;
}

async function retryHmd(folder) {
  if (!confirm('确认重新预处理：' + folder.split(/[\\/]/).pop())) return;
  try {
    const res = await fetch('/api/hmd/retry', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({folder: folder})
    });
    const data = await res.json();
    if (data.status === 'processing') {
      showStatus('已重新启动预处理');
      refreshProgress();
    } else {
      showStatus('重试失败：' + (data.error || '未知错误'));
    }
  } catch (e) {
    showStatus('重试请求失败：' + e.message);
  }
}

function retryHmdFromBtn(btn) {
  const folder = btn.getAttribute('data-folder');
  if (folder) retryHmd(folder);
}
