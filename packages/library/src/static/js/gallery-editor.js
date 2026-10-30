// gallery-editor.js — Same-as-above, gallery editor overlay, and upload template dialog
// Extracted from index.html

/* ============================================================ */
/* === 「同上」功能：复制上一条的录制员、Task、Env           === */
/* ============================================================ */
let _sameAsAboveUndo = null; // { type: 'table'|'gallery', originalIndex?, oldValues: {recorder_id, task_id, env_id} }

/** 表格页：「同上」按钮点击处理 */
function tableSameAsAbove(btn) {
  const tr = btn.closest('tr');
  const filteredIdx = parseInt(tr.dataset.filteredIdx);
  const originalIdx = parseInt(tr.dataset.index);
  // 重新计算当前筛选+排序结果
  const sorted = applySharedFilters(tableData).sort(compareRows);
  if (filteredIdx <= 0 || filteredIdx >= sorted.length) {
    showStatus('当前已是筛选结果的第一条，没有上一个');
    return;
  }
  const prevRow = sorted[filteredIdx - 1];
  const currentRow = tableData[originalIdx];
  if (!currentRow || !prevRow) return;

  // 保存 undo
  _sameAsAboveUndo = {
    type: 'table',
    originalIndex: originalIdx,
    oldValues: {
      recorder_id: currentRow.recorder_id || '',
      task_id: currentRow.task_id || '',
      env_id: currentRow.env_id || ''
    }
  };

  // 赋值
  currentRow.recorder_id = prevRow.recorder_id || '';
  currentRow.task_id = prevRow.task_id || '';
  currentRow.env_id = prevRow.env_id || '';

  markRowDirty(originalIdx);
  renderTable(); // 刷新表格以显示新值
  _showUndoSameAsAboveBar();
  // 立即强制保存（绕过 800ms debounce）—— 否则在 debounce 窗口内若点「扫描目录」，
  // scan 会用 read_csv() 的旧快照覆盖本次尚未落库的修改（导致用户看到"复制了但 PG 没存"）。
  if (typeof autoSaveTimer !== 'undefined' && autoSaveTimer) { clearTimeout(autoSaveTimer); autoSaveTimer = null; }
  saveDirtyRows(false);
}

/** 画廊编辑页：「同上」按钮点击处理 */
function gallerySameAsAbove() {
  if (galleryState.overlayIdx <= 0) {
    showStatus('当前已是筛选结果的第一张，没有上一个');
    return;
  }
  const card = galleryState.cards[galleryState.overlayIdx];
  const prevCard = galleryState.cards[galleryState.overlayIdx - 1];
  if (!card || !prevCard) return;

  // 保存 undo
  _sameAsAboveUndo = {
    type: 'gallery',
    oldValues: {
      recorder_id: card.recorder_id || '',
      task_id: card.task_id || '',
      env_id: card.env_id || ''
    }
  };

  // 赋值
  card.recorder_id = prevCard.recorder_id || '';
  card.task_id = prevCard.task_id || '';
  card.env_id = prevCard.env_id || '';

  // 写回 tableData
  const origIdx = tableData.findIndex(r => r.path === card.path);
  if (origIdx >= 0) markRowDirty(origIdx);
  // 刷新表单（按钮自动变成「↩ 撤回同上」）
  const panel = document.getElementById('galleryEditorPanel');
  if (panel) {
    panel.innerHTML = _buildGalleryEditorForm(card, _galleryEditorIdx);
    _bindGalleryEditorForm(card, _galleryEditorIdx);
  }
  // 同步表格
  try { renderTable(); } catch (e) { /* ignore */ }
  showStatus('已复制上一个视频的录制员、Task、Env');
  _showUndoSameAsAboveBar();
  // 立即强制保存（绕过 800ms debounce），原因同 tableSameAsAbove
  if (typeof autoSaveTimer !== 'undefined' && autoSaveTimer) { clearTimeout(autoSaveTimer); autoSaveTimer = null; }
  saveDirtyRows(true);  // 静默保存（已在上面 showStatus 给出"已复制"反馈）
}

/** 撤回最近一次「同上」操作 */
function sameAsAboveUndo() {
  if (!_sameAsAboveUndo) return;
  const state = _sameAsAboveUndo;
  _sameAsAboveUndo = null;

  if (state.type === 'table') {
    const row = tableData[state.originalIndex];
    if (!row) return;
    row.recorder_id = state.oldValues.recorder_id;
    row.task_id = state.oldValues.task_id;
    row.env_id = state.oldValues.env_id;
    markRowDirty(state.originalIndex);
    renderTable();
    showStatus('已撤回「同上」操作');
    // 立即强制保存（同上）
    if (typeof autoSaveTimer !== 'undefined' && autoSaveTimer) { clearTimeout(autoSaveTimer); autoSaveTimer = null; }
    saveDirtyRows(false);
  } else if (state.type === 'gallery') {
    const card = galleryState.cards[galleryState.overlayIdx];
    if (!card) return;
    card.recorder_id = state.oldValues.recorder_id;
    card.task_id = state.oldValues.task_id;
    card.env_id = state.oldValues.env_id;
    const origIdx = tableData.findIndex(r => r.path === card.path);
    if (origIdx >= 0) markRowDirty(origIdx);
    const panel = document.getElementById('galleryEditorPanel');
    if (panel) {
      panel.innerHTML = _buildGalleryEditorForm(card, _galleryEditorIdx);
      _bindGalleryEditorForm(card, _galleryEditorIdx);
    }
    try { renderTable(); } catch (e) { /* ignore */ }
    showStatus('已撤回「同上」操作');
    // 立即强制保存（同上）
    if (typeof autoSaveTimer !== 'undefined' && autoSaveTimer) { clearTimeout(autoSaveTimer); autoSaveTimer = null; }
    saveDirtyRows(true);  // 静默：showStatus 已给反馈
  }

  _hideUndoSameAsAboveBar();
}

/** 显示工具栏的撤回按钮 */
function _showUndoSameAsAboveBar() {
  const btn = document.getElementById('btnUndoSameAsAbove');
  if (btn) btn.style.display = '';
}

/** 隐藏工具栏的撤回按钮 */
function _hideUndoSameAsAboveBar() {
  const btn = document.getElementById('btnUndoSameAsAbove');
  if (btn) btn.style.display = 'none';
}

/* ============================================================ */

function _bindGalleryEditorForm(card, idx) {
  _galleryEditorIdx = idx;
  _galleryEditorOriginalRow = JSON.parse(JSON.stringify(card));
  const panel = document.getElementById('galleryEditorPanel');
  if (!panel) return;
  panel.removeEventListener('input', _onGalleryEditorInput);
  panel.removeEventListener('change', _onGalleryEditorInput);
  panel.addEventListener('input', _onGalleryEditorInput);
  panel.addEventListener('change', _onGalleryEditorInput);
}

function _onGalleryEditorInput() {
  // 800ms debounce auto-save（静默，不弹 toast）
  clearTimeout(_galleryEditorTimer);
  _galleryEditorTimer = setTimeout(() => galleryEditorSave(true), 800);
}

// 表格页保存后，刷新画廊浮层表单（如果当前卡片行被修改了）
function _refreshGalleryEditorForm(savedIndices) {
  const overlay = document.getElementById('galleryOverlay');
  if (!overlay || overlay.classList.contains('hidden')) return;
  const card = galleryState.cards[_galleryEditorIdx];
  if (!card) return;
  const cardIdx = tableData.findIndex(r => r.path === card.path);
  if (cardIdx >= 0 && savedIndices.includes(cardIdx)) {
    const panel = document.getElementById('galleryEditorPanel');
    if (panel) {
      panel.innerHTML = _buildGalleryEditorForm(card, _galleryEditorIdx);
      _bindGalleryEditorForm(card, _galleryEditorIdx);
    }
  }
}

async function galleryEditorSave(silent = false) {
  const card = galleryState.cards[_galleryEditorIdx];
  if (!card) return;
  const panel = document.getElementById('galleryEditorPanel');
  if (!panel) return;
  // Collect changes
  panel.querySelectorAll('[data-key]').forEach(el => {
    card[el.dataset.key] = el.value;
  });
  // Find tableData index and save only this row (card is a reference into tableData)
  const origIdx = tableData.findIndex(r => r.path === card.path);
  if (origIdx < 0) {
    if (!silent) showToast('找不到对应记录', 'warn');
    return;
  }
  markRowDirty(origIdx);
  // Force immediate save (clear timer so saveDirtyRows fires)
  if (autoSaveTimer) { clearTimeout(autoSaveTimer); autoSaveTimer = null; }
  await saveDirtyRows(true);  // 静默保存，不弹左下角提示
  // 跨视图同步：刷新表格视图以反映最新数据
  try { renderTable(); } catch (e) { /* 不在视频管理页则忽略 */ }
  if (!silent) showToast('已保存', 'success');
}
function galleryOverlayPlayVideo() {
  const card = galleryState.cards[galleryState.overlayIdx];
  if (!card) return;
  const isUmi = (card.file_type || '') === 'hmd';
  // HMD → 使用系统播放器打开预处理完成的视频（与表格预览一致）
  if (isUmi) {
    const ps = _preprocessStatusMap[card.path];
    if (ps && ps.hmd_preprocess === 'done') {
      openHmdPreviewInline(card.path);
    } else {
      const statusLabel = ps && ps.hmd_preprocess === 'processing' ? '处理中'
        : ps && ps.hmd_preprocess === 'error' ? '失败' : '等待';
      const progressHint = (ps && ps.hmd_progress) ? `（${ps.hmd_progress}%）` : '';
      showToast(`HMD 预处理${statusLabel}${progressHint}，暂无法预览。请等待预处理完成。`, 'warn');
    }
    return;
  }
  // 非 HMD：在左侧面板内嵌播放
  const videoContainer = document.querySelector('.gallery-editor-video');
  if (!videoContainer) return;
  const vidId = 'galleryOverlayVideo';
  videoContainer.innerHTML = `<video id="${vidId}" controls autoplay style="width:100%;max-height:88vh;border-radius:4px;"
    src="/api/video?path=${encodeURIComponent(card.path)}"></video>`;
  const vid = document.getElementById(vidId);
  if (vid) {
    vid.play().catch(() => {});
    vid.addEventListener('error', () => { alert('视频加载失败，文件可能不存在'); });
  }
}

function galleryOverlayClose() {
  const overlay = document.getElementById('galleryOverlay');
  const body = document.getElementById('galleryOverlayBody');
  // 关闭帧模态框
  closeGalleryFrameModal();
  // 停掉任何播放
  const vid = document.getElementById('galleryOverlayVideo');
  if (vid) { vid.pause(); vid.removeAttribute('src'); vid.load(); }
  body.innerHTML = '';
  overlay.classList.add('hidden');
  // 清除画廊 undo 状态
  if (_sameAsAboveUndo && _sameAsAboveUndo.type === 'gallery') {
    _sameAsAboveUndo = null;
    _hideUndoSameAsAboveBar();
  }
  // 清除刷新恢复路径
  try { localStorage.removeItem('galleryLastDetailPath'); } catch(e) {}
}
// ── 刷新恢复：自动回到之前打开的详情页 ──
function _restoreGalleryDetail() {
  try {
    // 只恢复 sharedFilterState（下拉筛选），不自动恢复 viewMode 以外的视图状态
    _restoreSharedFilters();

    // 仅在「视频管理」Tab 下恢复画廊详情，避免在其他 Tab 下错误触发
    let lastTab = 'videos';
    try { lastTab = localStorage.getItem('lastTab') || 'videos'; } catch (e) {}
    if (lastTab !== 'videos') return;

    // 检查是否之前处于画廊视图
    if (videoViewMode !== 'gallery') return;
    if (!galleryState.loaded && tableData.length > 0) {
      _populateSharedFilters();
      _bindSharedFilterChanges();
      galleryState.loaded = true;
    }
    if (!galleryState.loaded) return;

    const savedPath = localStorage.getItem('galleryLastDetailPath');
    if (!savedPath) return;

    // 切到画廊视图（按钮文案 / 显隐）
    const tableWrap = document.getElementById('tableWrap');
    const galleryWrap = document.getElementById('galleryWrap');
    const toolbarBtn = document.getElementById('btnViewToggle');
    if (tableWrap) tableWrap.classList.add('hidden');
    if (galleryWrap) galleryWrap.classList.remove('hidden');
    if (toolbarBtn) toolbarBtn.textContent = '📊 表格';

    _galleryRender();

    // 延迟等到 _galleryRender 完成后，在 galleryState.cards 中找到对应卡片
    setTimeout(() => {
      const idx = galleryState.cards.findIndex(c => c.path === savedPath);
      if (idx >= 0) {
        galleryOverlayOpen(idx);
      }
    }, 100);
  } catch (e) { /* ignore */ }
}
function galleryOverlayNav(delta) {
  if (galleryState.overlayIdx < 0) return;
  const next = galleryState.overlayIdx + delta;
  if (next < 0 || next >= galleryState.cards.length) return;
  // 导航到其他卡片时清除画廊 undo 状态
  if (_sameAsAboveUndo && _sameAsAboveUndo.type === 'gallery') {
    _sameAsAboveUndo = null;
    _hideUndoSameAsAboveBar();
  }
  galleryState.overlayIdx = next;
  galleryOverlayOpen(next);
}

// Esc 关闭 / 左右键导航
document.addEventListener('keydown', e => {
  const overlay = document.getElementById('galleryOverlay');
  if (!overlay || overlay.classList.contains('hidden')) return;
  if (e.key === 'Escape') galleryOverlayClose();
  else if (e.key === 'ArrowLeft') galleryOverlayNav(-1);
  else if (e.key === 'ArrowRight') galleryOverlayNav(1);
});

/* ── 上传模板（一键复制） ── */
let _utRowIndex = -1;
let _utPath = '';          // 视频路径，用作唯一标识符
let _utDeleteAfterUpload = false;

async function openUploadTemplate(rowIndex) {
  _utRowIndex = rowIndex;
  // 通过 tableData 获取 path（优先使用 path 查询，避免 rowIndex 不一致）
  const row = tableData[rowIndex];
  _utPath = (row && row.path) || '';
  const dialog = document.getElementById('utDialog');
  const body = document.getElementById('utBody');
  dialog.classList.remove('hidden');
  // 同步 checkbox 状态
  const chk = document.getElementById('utChkDeleteLocal');
  if (chk) chk.checked = _utDeleteAfterUpload;
  body.innerHTML = '<div style="text-align:center;padding:40px;color:#888;">加载中...</div>';
  try {
    const url = _utPath
      ? '/api/upload-template-by-path?path=' + encodeURIComponent(_utPath)
      : '/api/upload-template/' + rowIndex;
    const res = await fetch(url);
    const data = await res.json();
    if (data.error) { body.innerHTML = '<div style="color:#ff4d4f;padding:20px;">错误: ' + data.error + '</div>'; return; }
    document.getElementById('utVideoName').textContent = data.video_name || '--';
    // Build sections
    let html = '';
    const fieldMap = {};
    data.fields.forEach(f => { fieldMap[f.key] = f; });
    data.sections.forEach(sec => {
      html += '<div class="ut-section-title">' + esc(sec.title) + '</div>';
      const secFields = data.fields.filter(f => f.section_id === sec.id);
      secFields.forEach(f => {
        const hasVal = f.value && f.value.trim();
        const rowCls = hasVal ? 'filled' : 'empty';
        const displayVal = hasVal ? f.value : '';
        // 双语字段（工序 + 环境描述）：上传页是中文页面，只显示中文
        const isBilingual = (f.key === 'task_description' || f.key === 'environment_description') && (f.cn || f.value);
        if (isBilingual) {
          const zhText = f.cn || f.value;
          html += '<div class="ut-field-row ' + rowCls + '">'
            + '<span class="ut-field-label" title="' + esc(f.label) + '">' + esc(f.label) + '</span>'
            + '<span class="ut-field-value">'
              + '<span style="display:flex;align-items:center;gap:4px;">'
                + '<span style="font-size:13px;line-height:1.5;flex:1;">' + esc(zhText) + '</span>'
                + '<button class="ut-copy-btn" onclick="copyField(this,\'' + esc(zhText) + '\')" style="font-size:10px;padding:1px 5px;flex-shrink:0;">📋 复制</button>'
              + '</span>'
            + '</span>'
            + '</div>';
        } else {
          html += '<div class="ut-field-row ' + rowCls + '">'
            + '<span class="ut-field-label" title="' + esc(f.label) + '">' + esc(f.label) + '</span>'
            + '<span class="ut-field-value">' + esc(displayVal) + '</span>'
            + '<button class="ut-copy-btn" onclick="copyField(this,\'' + esc(f.value) + '\')">📋 复制</button>'
            + '</div>';
        }
      });
    });
    body.innerHTML = html;
  } catch (e) {
    body.innerHTML = '<div style="color:#ff4d4f;padding:20px;">加载失败: ' + e.message + '</div>';
  }
}

function closeUploadTemplate() {
  document.getElementById('utDialog').classList.add('hidden');
  _utRowIndex = -1;
  _utPath = '';
}

async function copyField(btn, text) {
  try {
    await navigator.clipboard.writeText(text || '');
    btn.textContent = '✓ 已复制';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = '📋 复制'; btn.classList.remove('copied'); }, 1500);
  } catch (e) {
    // Fallback
    const ta = document.createElement('textarea');
    ta.value = text || '';
    ta.style.position = 'fixed'; ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    btn.textContent = '✓ 已复制';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = '📋 复制'; btn.classList.remove('copied'); }, 1500);
  }
}

async function copyAllFields() {
  const rows = document.querySelectorAll('#utBody .ut-field-row.filled');
  let text = '';
  rows.forEach(row => {
    const label = row.querySelector('.ut-field-label').textContent.trim();
    const value = row.querySelector('.ut-field-value').textContent.trim();
    if (value) text += label + ': ' + value + '\n';
  });
  if (!text) { alert('没有可复制的字段'); return; }
  try {
    await navigator.clipboard.writeText(text);
  } catch (e) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed'; ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  }
  showStatus('已复制全部字段到剪贴板');
}

async function copyAllValuesOnly() {
  const rows = document.querySelectorAll('#utBody .ut-field-row.filled');
  const values = [];
  rows.forEach(row => {
    const v = row.querySelector('.ut-field-value').textContent.trim();
    if (v) values.push(v);
  });
  if (!values.length) { alert('没有可复制的字段'); return; }
  const text = values.join('\n');
  try {
    await navigator.clipboard.writeText(text);
  } catch (e) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed'; ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  }
  showStatus('已复制全部字段值到剪贴板');
}

/* ── 单视频上传 ── */
// 辅助：Promise 版 sleep
function _sleepMs(ms) { return new Promise(r => setTimeout(r, ms)); }
