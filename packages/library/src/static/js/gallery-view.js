// gallery-view.js — Gallery grid, lazy thumbs, overlay, frames
// Extracted from index.html

/* ============================================================ */
/* === GALLERY VIEW                                           === */
/* ============================================================ */
const galleryState = {
  loaded: false,
  selectedKeys: new Set(),
  cards: [],
  overlayIdx: -1,
};
async function galleryLoad() {
  // 画廊视图是 videos 页面内的另一种渲染模式 — 没有独立的 status 元素
  try {
    const r = await fetch('/api/data');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    tableData = await r.json();
    // 一次性按当前 sortStack 排序 — 与 loadData 保持一致，避免表格/画廊顺序错位
    tableData.sort(compareRows);
    _populateSharedFilters();
    _bindSharedFilterChanges();
    galleryState.loaded = true;
    _galleryRender();
  } catch (e) {
    console.warn('[galleryLoad]', e);
  }
}
// 保留旧函数名以防兼容；实际上由共享筛选取代
function _galleryFillFilters() { _populateSharedFilters(); }
function _galleryRender() {
  const grid = document.getElementById('galleryGrid');
  const empty = document.getElementById('galleryEmpty');
  if (!grid) { console.warn('[galleryRender] no #galleryGrid'); return; }
  // 复用共享筛选 + 画廊独立排序：固定按视频路径升序（不跟随表格 sortStack）
  // 这样「同上」拿到的上一张是路径相邻的上一条，确定性可预测
  const filtered = applySharedFilters(tableData).sort((a, b) =>
    String(a.path || '').localeCompare(String(b.path || ''), 'zh-Hans-CN')
  );
  if (filtered.length === 0) {
    grid.innerHTML = '';
    if (empty) {
      // 区分两种空状态：表里压根没数据 vs 数据被筛选过滤掉
      empty.textContent = tableData.length === 0
        ? '尚无视频记录；先在「视频管理」扫描目录。'
        : '无匹配筛选；请调整筛选条件。';
      empty.classList.remove('hidden');
    }
    galleryState.cards = [];
    return;
  }
  if (empty) empty.classList.add('hidden');
  galleryState.cards = filtered;
  const html = filtered.map((r, idx) => {
    const key = r.path;
    const selected = galleryState.selectedKeys.has(key);
    const type = r.file_type || 'mp4';
    const fname = r.path.split(/[\\/]/).pop();
    const up = (r.uploaded || 'No');
    // 统一用 /api/thumbnail 生成封面（服务端智能 seek + luma 检测）— 不再走浏览器
    // 端的 video.currentTime，因为 HMD 拆分的 left.mp4 在某些浏览器/Codec 组合下
    // 渲染黑帧（UVC 启动暗帧未跳过去）。服务端 ffmpeg 处理更稳定。
    const thumbInner = `<img data-thumb-idx="${idx}" data-thumb-path="${esc(key)}" data-thumb-type="${esc(type)}"
            alt="" loading="lazy" style="display:none;">
         <span class="badge">${esc(type.toUpperCase())}</span>
         <span style="font-size:42px;" class="thumb-fallback">▶</span>`;
    return `<div class="gallery-card ${selected ? 'selected' : ''}" data-idx="${idx}" data-key="${esc(key)}" onclick="galleryCardClick(event, ${idx})">
      <div class="gallery-thumb" data-thumb-host="${idx}">
        ${thumbInner}
      </div>
      <div class="gallery-card-info">
        <div class="gallery-card-name" title="${esc(r.path)}">${esc(fname)}</div>
        <div class="gallery-card-chips">
          <span class="gallery-chip ${r.device_id ? '' : 'empty'}">${r.device_id || 'device: --'}</span>
          <span class="gallery-chip ${r.recorder_id ? 'filled-recorder' : 'empty'}">${r.recorder_id || 'recorder: --'}</span>
          <span class="gallery-chip ${r.task_id ? 'filled-task' : 'empty'}">${r.task_id || 'task: --'}</span>
          <span class="gallery-chip uploaded-${up === 'Yes' ? 'yes' : 'no'}">${up === 'Yes' ? '✓ 已上传' : '○ 未上传'}</span>
        </div>
      </div>
    </div>`;
  }).join('');
  grid.innerHTML = html;
  // 共享筛选的 change 监听在 loadData 时已绑定；这里只需触发懒加载
  _gallerySetupLazyThumbs();
}

let _thumbObserver = null;
function _gallerySetupLazyThumbs() {
  if (_thumbObserver) _thumbObserver.disconnect();
  const grid = document.getElementById('galleryGrid');
  if (!grid) { console.warn('[gallerySetupLazyThumbs] no grid'); return; }
  const imgs = grid.querySelectorAll('img[data-thumb-idx]');
  // 统一路径：所有 file_type 都走 /api/thumbnail — 服务端 ffmpeg 截帧（智能 seek + luma 检测）
  _thumbObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      const img = entry.target;
      _thumbObserver.unobserve(img);
      const idx = parseInt(img.dataset.thumbIdx, 10);
      const path = img.dataset.thumbPath;
      const type = img.dataset.thumbType || 'mp4';
      const url = '/api/thumbnail?path=' + encodeURIComponent(path);
      fetch(url)
        .then(r => {
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.blob();
        })
        .then(blob => {
          if (blob.size === 0) throw new Error('empty');
          const objUrl = URL.createObjectURL(blob);
          img.src = objUrl;
          img.style.display = 'block';
          img.onload = () => URL.revokeObjectURL(objUrl);
          const host = img.closest('.gallery-thumb');
          if (host) {
            const fb = host.querySelector('.thumb-fallback');
            if (fb) fb.style.display = 'none';
          }
        })
        .catch((e) => {
          console.warn('[galleryThumb] FAIL', url, e.message);
          const host = img.closest('.gallery-thumb');
          if (!host) return;
          const fb = host.querySelector('.thumb-fallback');
          if (fb) { fb.textContent = type === 'hmd' ? '🎬' : '⚠'; fb.setAttribute('title', '缩略图生成失败：' + e.message); }
        });
    });
  }, { root: grid, rootMargin: '200px' });
  const allImgs = grid.querySelectorAll('img[data-thumb-idx]');
  allImgs.forEach(img => _thumbObserver.observe(img));
  // 兜底：500ms 后如果 IntersectionObserver 还没触发（容器被隐藏、滚动容器没布局等），
  // 直接对所有可见卡片同步 fetch — 不阻塞主流程
  setTimeout(() => {
    allImgs.forEach((img) => {
      if (img.dataset.thumbLoaded === '1' || img.style.display === 'block') return;
      // 模拟一次 intersection：手动调用一次 fetch
      const path = img.dataset.thumbPath;
      if (!path) return;
      const idx = parseInt(img.dataset.thumbIdx, 10);
      const type = img.dataset.thumbType || 'mp4';
      const url = '/api/thumbnail?path=' + encodeURIComponent(path);
      img.dataset.thumbLoaded = '1';
      fetch(url)
        .then(r => {
          // Check for placeholder header → treat like missing thumbnail
          if (r.headers.get('X-Thumbnail-Placeholder') === '1') {
            return null; // signal no-thumbnail to next .then
          }
          if (!r.ok) throw new Error('HTTP ' + r.status);
          return r.blob();
        })
        .then(blob => {
          if (blob === null) return; // placeholder → keep fallback visible
          if (!blob || blob.size === 0) throw new Error('empty');
          const objUrl = URL.createObjectURL(blob);
          img.src = objUrl;
          img.style.display = 'block';
          img.onload = () => URL.revokeObjectURL(objUrl);
          const fb = img.closest('.gallery-thumb').querySelector('.thumb-fallback');
          if (fb) fb.style.display = 'none';
        })
        .catch(e => {
          if (e === null) return; // placeholder signal, already handled
          // 静默处理404错误，避免console中大量错误信息
          if (e.message && e.message.includes('404')) {
            // thumbnail not available — fallback icon already visible
          } else {
            console.warn('[galleryThumb-fallback] FAIL', url, e.message);
          }
        });
    });
  }, 500);
}
function galleryCardClick(ev, idx) {
  if (ev.shiftKey) {
    // 区间选择
    const cards = galleryState.cards;
    const lastIdx = galleryState._lastClickIdx;
    const start = Math.min(lastIdx == null ? idx : lastIdx, idx);
    const end = Math.max(lastIdx == null ? idx : lastIdx, idx);
    for (let i = start; i <= end; i++) galleryState.selectedKeys.add(cards[i].path);
  } else if (ev.ctrlKey || ev.metaKey) {
    if (galleryState.selectedKeys.has(galleryState.cards[idx].path)) {
      galleryState.selectedKeys.delete(galleryState.cards[idx].path);
    } else {
      galleryState.selectedKeys.add(galleryState.cards[idx].path);
    }
  } else {
    // 单击：清空选择 + 打开边看边填编辑器
    galleryState.selectedKeys.clear();
    galleryState.selectedKeys.add(galleryState.cards[idx].path);
    galleryState.overlayIdx = idx;
    galleryOverlayOpen(idx);
  }
  galleryState._lastClickIdx = idx;
  _galleryRender();
}
function galleryOverlayOpen(idx) {
  // 打开新卡片时清除画廊的「同上」撤回状态
  if (_sameAsAboveUndo && _sameAsAboveUndo.type === 'gallery') {
    _sameAsAboveUndo = null;
  }
  const card = galleryState.cards[idx];
  if (!card) return;
  const overlay = document.getElementById('galleryOverlay');
  const body = document.getElementById('galleryOverlayBody');
  const isHmd = (card.file_type || '') === 'hmd';
  // Normalize path separators to forward slashes for URL safety
  const normalizedPath = (card.path || '').replace(/\\/g, '/');
  
  // HMD 未完成预处理时不加载帧（避免 API 500）
  const ps = _preprocessStatusMap[card.path];
  const hmdNotReady = isHmd && ps && ps.hmd_preprocess && ps.hmd_preprocess !== 'done';
  const framesHint = hmdNotReady
    ? `<div class="gallery-frames-loading" style="color:#f0a020;">⏳ HMD 预处理${ps.hmd_preprocess==='processing'?'中':'未完成'}${ps.hmd_progress?'（'+ps.hmd_progress+'%）':''}，预览帧暂不可用</div>`
    : `<div class="gallery-frames-loading">加载预览帧...</div>`;
  
  // 边看边填：左帧网格 + 右编辑面板
  body.innerHTML = `
    <div class="gallery-editor-layout">
      <div class="gallery-editor-video">
        <div class="gallery-frames-toolbar">
          <button class="btn btn-small btn-outline" onclick="toggleFramesLayout()" title="切换2列/平铺">📐 平铺</button>
          <span style="color:#888;font-size:11px;margin-left:4px;">滚轮缩放</span>
        </div>
        <div id="galleryFramesContainer" class="gallery-frames-grid">
        ${framesHint}
        </div>
        <div id="galleryFrameModal" class="gallery-frame-modal hidden" onwheel="event.preventDefault()">
          <span class="gallery-frame-modal-close" onclick="closeGalleryFrameModal()">✕</span>
          <div id="galleryFrameModalImgWrap" class="gallery-frame-modal-img-wrap">
            <img id="galleryFrameModalImg" class="gallery-frame-modal-img" src="" alt="放大查看">
          </div>
          <div id="galleryFrameModalInfo" class="gallery-frame-modal-info"></div>
          <div class="gallery-frame-modal-toolbar">
            <button onclick="zoomGalleryFrame(-0.25)" title="缩小">−</button>
            <span class="zoom-label" id="galleryZoomLabel">100%</span>
            <button onclick="zoomGalleryFrame(0.25)" title="放大">+</button>
            <button onclick="resetGalleryFrameZoom()" title="重置">↺</button>
          </div>
        </div>
      </div>
      <div class="gallery-editor-panel" id="galleryEditorPanel">
        ${_buildGalleryEditorForm(card, idx)}
      </div>
    </div>`;
  
  // Bind form changes back to tableData + auto-save (debounced)
  _bindGalleryEditorForm(card, idx);
  overlay.classList.remove('hidden');
  
  // Persist current detail page path for refresh recovery
  try { localStorage.setItem('galleryLastDetailPath', card.path); } catch(e) {}
  
  // Load frames
  loadGalleryFrames(normalizedPath, isHmd);
}

function loadGalleryFrames(videoPath, isHmd) {
  const container = document.getElementById('galleryFramesContainer');
  if (!container) return;
  
  const apiUrl = isHmd
    ? `/api/hmd/frames?folder=${encodeURIComponent(videoPath)}`
    : `/api/video/frames?path=${encodeURIComponent(videoPath)}`;
  
  container.innerHTML = '<div class="gallery-frames-loading">加载预览帧...</div>';
  
  fetch(apiUrl)
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        container.innerHTML = `<div class="gallery-frames-error">加载失败: ${data.error}</div>`;
        return;
      }
      
      if (!data.frames || data.frames.length === 0) {
        container.innerHTML = '<div class="gallery-frames-error">暂无预览帧</div>';
        return;
      }
      
      // Build frames grid
      let html = '';
      data.frames.forEach((frame, idx) => {
        html += `
          <div class="gallery-frame-item" onclick="showGalleryFrameModal('${frame.url}', ${idx + 1}, ${data.frames.length})">
            <img src="${frame.url}" alt="帧 ${idx + 1}" loading="lazy">
            <div class="gallery-frame-label">帧 ${idx + 1}</div>
          </div>`;
      });
      container.innerHTML = html;
    })
    .catch(err => {
      container.innerHTML = `<div class="gallery-frames-error">加载失败: ${err.message}</div>`;
    });
}

// --- Gallery frame modal with zoom & drag ---
let _galleryZoom = { scale: 1, tx: 0, ty: 0, dragging: false, sx: 0, sy: 0 };

function showGalleryFrameModal(url, frameNum, totalFrames) {
  const modal = document.getElementById('galleryFrameModal');
  const img = document.getElementById('galleryFrameModalImg');
  const wrap = document.getElementById('galleryFrameModalImgWrap');
  const info = document.getElementById('galleryFrameModalInfo');
  
  if (!modal || !img) return;
  
  // Reset zoom state
  _galleryZoom = { scale: 1, tx: 0, ty: 0, dragging: false, sx: 0, sy: 0 };
  img.style.transform = 'scale(1) translate(0px, 0px)';
  img.style.maxWidth = '90vw';
  img.style.maxHeight = '85vh';
  img.src = url;
  info.textContent = `帧 ${frameNum} / ${totalFrames}`;
  document.getElementById('galleryZoomLabel').textContent = '100%';
  modal.classList.remove('hidden');
  
  // Don't close on image/wrap click - only on background
  modal.onclick = (e) => { if (e.target === modal) closeGalleryFrameModal(); };
  
  // Wheel zoom
  modal.onwheel = (e) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.15 : 0.15;
    _applyZoom(delta);
  };
  
  // Drag to pan (when zoomed in)
  if (wrap) {
    img.onmousedown = (e) => {
      if (_galleryZoom.scale <= 1) return;
      e.preventDefault();
      _galleryZoom.dragging = true;
      _galleryZoom.sx = e.clientX - _galleryZoom.tx;
      _galleryZoom.sy = e.clientY - _galleryZoom.ty;
      wrap.classList.add('grabbing');
    };
  }
  
  window.addEventListener('mousemove', _onFrameDrag);
  window.addEventListener('mouseup', _onFrameDragEnd);
}

function closeGalleryFrameModal() {
  const modal = document.getElementById('galleryFrameModal');
  if (modal) {
    modal.classList.add('hidden');
    modal.onwheel = null;
    const img = document.getElementById('galleryFrameModalImg');
    if (img) { img.src = ''; img.onmousedown = null; }
  }
  window.removeEventListener('mousemove', _onFrameDrag);
  window.removeEventListener('mouseup', _onFrameDragEnd);
}

function _onFrameDrag(e) {
  if (!_galleryZoom.dragging) return;
  _galleryZoom.tx = e.clientX - _galleryZoom.sx;
  _galleryZoom.ty = e.clientY - _galleryZoom.sy;
  _updateFrameTransform();
}

function _onFrameDragEnd() {
  _galleryZoom.dragging = false;
  const wrap = document.getElementById('galleryFrameModalImgWrap');
  if (wrap) wrap.classList.remove('grabbing');
}

function _applyZoom(delta) {
  const newScale = Math.min(4, Math.max(0.5, _galleryZoom.scale + delta));
  if (newScale === _galleryZoom.scale) return;
  _galleryZoom.scale = newScale;
  if (newScale <= 1) { _galleryZoom.tx = 0; _galleryZoom.ty = 0; }
  _syncZoomImgConstraints();
  _updateFrameTransform();
  document.getElementById('galleryZoomLabel').textContent = Math.round(newScale * 100) + '%';
}

function zoomGalleryFrame(delta) { _applyZoom(delta); }

function resetGalleryFrameZoom() {
  _galleryZoom = { scale: 1, tx: 0, ty: 0, dragging: false, sx: 0, sy: 0 };
  _syncZoomImgConstraints();
  _updateFrameTransform();
  document.getElementById('galleryZoomLabel').textContent = '100%';
}

function _syncZoomImgConstraints() {
  const img = document.getElementById('galleryFrameModalImg');
  if (!img) return;
  if (_galleryZoom.scale > 1) {
    // Remove size caps so the image can scale freely
    img.style.maxWidth = 'none';
    img.style.maxHeight = 'none';
  } else {
    img.style.maxWidth = '90vw';
    img.style.maxHeight = '85vh';
  }
}

function _updateFrameTransform() {
  const img = document.getElementById('galleryFrameModalImg');
  if (img) {
    img.style.transform = `scale(${_galleryZoom.scale}) translate(${_galleryZoom.tx}px, ${_galleryZoom.ty}px)`;
  }
}

// --- Toggle gallery frames layout (2-col / tiled) ---
let _framesTiled = false;
function toggleFramesLayout() {
  _framesTiled = !_framesTiled;
  const grid = document.getElementById('galleryFramesContainer');
  if (!grid) return;
  if (_framesTiled) {
    grid.style.gridTemplateColumns = '1fr';
    grid.style.maxWidth = '100%';
  } else {
    grid.style.gridTemplateColumns = 'repeat(2, 1fr)';
    grid.style.maxWidth = '';
  }
}

function _buildGalleryEditorForm(card, idx) {
  // 复用视频管理列配置，但只显示关键字段
  const editableKeys = ['recorder_id', 'task_id', 'env_id', 'device_id', 'uploaded', 'extra_description', 'score'];
  const labels = (window.colConfig || []).reduce((acc, c) => { acc[c.key] = c.label; return acc; }, {});
  const dimSelectKeys = new Set(['recorder_id', 'task_id', 'device_id', 'env_id']);
  const rows = editableKeys.map(key => {
    const label = labels[key] || key;
    const val = card[key] || '';
    let inputHtml = '';
    if (dimSelectKeys.has(key)) {
      // 维表下拉
      let dimName = '';
      if (key === 'recorder_id') dimName = 'recorders';
      else if (key === 'task_id') dimName = 'tasks';
      else if (key === 'device_id') dimName = 'sd_cards';
      else if (key === 'env_id') dimName = 'environments';
      const dimRows = (dimCache && dimCache[dimName]) || [];
      const PRIMARY = { recorders: 'id', sd_cards: 'device_id', tasks: 'task_id' };
      const primary = PRIMARY[dimName] || (dimRows[0] ? Object.keys(dimRows[0])[0] : 'id');
      const matched = dimRows.some(r => (r[primary] || '') === val);
      const labelFor = r => {
        if (dimName === 'recorders') return [r.id, r.name].filter(Boolean).join(' · ');
        if (dimName === 'sd_cards') return [r.device_id, r.device_name].filter(Boolean).join(' · ');
        if (dimName === 'tasks') return [r.product, r.task, r.process].filter(Boolean).join(' · ');
        if (dimName === 'environments') return r.environment_description || r[primary] || '';
        return r[primary] || '';
      };
      // tasks 下拉按 产品→任务→工具 排序，与表格页一致
      const sortedDimRows = dimName === 'tasks'
        ? [...dimRows].sort((a, b) => _taskSortKey(a).localeCompare(_taskSortKey(b), 'zh'))
        : dimRows;
      const opts = sortedDimRows.map(r => {
        const v = r[primary] || '';
        return `<option value="${esc(v)}" ${v === val && matched ? 'selected' : ''}>${esc(labelFor(r))}</option>`;
      }).join('');
      const orphan = !matched && val
        ? `<option value="${esc(val)}" selected>${esc(val)} (未在 ${dimName} 中)</option>`
        : '';
      inputHtml = `<select data-key="${key}" class="gallery-editor-input"><option value="">--</option>${orphan}${opts}</select>`;
    } else if (key === 'uploaded') {
      inputHtml = `<select data-key="${key}" class="gallery-editor-input">
        <option value="No" ${val !== 'Yes' ? 'selected' : ''}>未上传</option>
        <option value="Yes" ${val === 'Yes' ? 'selected' : ''}>已上传</option></select>`;
    } else if (key === 'extra_description') {
      inputHtml = `<textarea data-key="${key}" class="gallery-editor-input" rows="2">${esc(val)}</textarea>`;
    } else {
      inputHtml = `<input type="text" data-key="${key}" class="gallery-editor-input" value="${esc(val)}">`;
    }
    return `<label class="gallery-editor-row"><span>${esc(label)}</span>${inputHtml}</label>`;
  }).join('');
  // 头部：路径 + 时长
  const header = `
    <div class="gallery-editor-header">
      <div class="gallery-editor-path" title="${esc(card.path)}">${esc((card.path || '').split(/[\\\\/]/).pop())}</div>
      <div class="gallery-editor-meta">
        ${card.file_type === 'hmd' ? 'HMD 双眼' : 'MP4'}
        · ${card.duration_sec ? fmtDur(card.duration_sec) : '--'}
      </div>
    </div>`;
  // ── 「同上」按钮 ──
  const canSame = (idx != null && idx > 0);
  const isGalleryUndo = _sameAsAboveUndo && _sameAsAboveUndo.type === 'gallery';
  const sameBtnHtml = isGalleryUndo
    ? `<button class="btn btn-outline btn-small" onclick="sameAsAboveUndo()" title="撤回最近一次「同上」">↩ 撤回同上</button>`
    : (canSame
      ? `<button class="btn btn-outline btn-small" onclick="gallerySameAsAbove()" title="复制上一个视频的录制员、Task、Env">同上</button>`
      : '');

  // ── 播放/预览按钮（与表格页预览按钮状态一致）──
  const isHistory = (card.location_status || '').endsWith('_history');
  const isHmdCard = (card.file_type || '') === 'hmd';
  const ps = _preprocessStatusMap[card.path];
  const hmdNotReady = isHmdCard && (!ps || ps.hmd_preprocess !== 'done');
  let playBtnHtml;
  if (isHistory) {
    playBtnHtml = `<button class="btn btn-outline btn-small btn-preview-disabled" onclick="alert('历史视频无法预览（文件已删除）')">预览</button>`;
  } else if (hmdNotReady) {
    let statusLabel, statusTitle;
    if (!ps) {
      statusLabel = '检查中…';
      statusTitle = '预处理状态未知，请稍候刷新';
    } else if (ps.hmd_preprocess === 'processing') {
      statusLabel = '处理中';
      statusTitle = 'HMD 预处理处理中' + (ps.hmd_progress ? ` (${ps.hmd_progress}%)` : '');
    } else if (ps.hmd_preprocess === 'error') {
      statusLabel = '失败';
      statusTitle = 'HMD 预处理失败';
    } else {
      statusLabel = '等待';
      statusTitle = 'HMD 预处理等待中';
    }
    playBtnHtml = `<button class="btn btn-outline btn-small btn-preview-disabled" title="${statusTitle}" disabled>⏳ ${statusLabel}</button>`;
  } else {
    playBtnHtml = `<button class="btn btn-outline btn-small" onclick="galleryOverlayPlayVideo()">▶ 播放视频</button>`;
  }

  return header + `<div class="gallery-editor-fields">${rows}</div>
    <div class="gallery-editor-actions">
      <button class="btn btn-success btn-small" onclick="galleryEditorSave()">保存修改</button>
      ${sameBtnHtml}
      ${playBtnHtml}
      <button class="btn btn-gray btn-small" onclick="galleryOverlayClose()">关闭</button>
    </div>`;
}

function galleryEditorPrepareUpload() {
  const card = galleryState.cards[galleryState.overlayIdx];
  if (!card) return;
  // Find original tableData index by matching path
  const origIdx = tableData.findIndex(r => r.path === card.path);
  if (origIdx < 0) { alert('找不到视频记录'); return; }
  openUploadTemplate(origIdx);
}

let _galleryEditorTimer = null;
let _galleryEditorIdx = -1;
let _galleryEditorOriginalRow = null;

