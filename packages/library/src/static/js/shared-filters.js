// shared-filters.js — Shared filter bar for video manager + gallery views
// Extracted from index.html

/* ============================================================ */
/* === SHARED FILTERS (video manager + gallery both read)    === */
/* ============================================================ */
const FILTER_IDS = ['vFilterDevice', 'vFilterRecorder', 'vFilterTask', 'vFilterUploaded', 'vFilterLocation', 'vFilterType'];

function getSharedFilters() {
  return {
    device:    document.getElementById('vFilterDevice')?.value || '',
    recorder: document.getElementById('vFilterRecorder')?.value || '',
    task:      document.getElementById('vFilterTask')?.value || '',
    uploaded:  document.getElementById('vFilterUploaded')?.value || '',
    location:  document.getElementById('vFilterLocation')?.value || '',
    type:      document.getElementById('vFilterType')?.value || '',
  };
}

function applySharedFilters(rows) {
  const f = getSharedFilters();
  return rows.filter(r => {
    if (f.device    && (r.device_id    || '') !== f.device) return false;
    if (f.recorder && (r.recorder_id || '') !== f.recorder) return false;
    if (f.task      && (r.task_id      || '') !== f.task) return false;
    if (f.uploaded  && (r.uploaded     || '') !== f.uploaded) return false;
    if (f.location  && (r.location_status || 'local') !== f.location) return false;
    if (f.type      && (r.file_type    || 'mp4') !== f.type) return false;
    return true;
  });
}

function _updateFilterCountLabel(visibleCount) {
  const el = document.getElementById('vFilterCount');
  if (!el) return;
  const f = getSharedFilters();
  const anyFilter = Object.values(f).some(v => v);
  el.textContent = anyFilter ? `筛选后 ${visibleCount} 条` : '';
}

// 同步 dim 页面的「保存」按钮 + dirty 计数
const _DIM_NAME_MAP = {
  recorders: 'Recorders',
  sd_cards:   'SdCards',
  tasks:      'Tasks',
};
function _updateDimSaveCount(name) {
  const cap = _DIM_NAME_MAP[name];
  if (!cap) return;
  const st = dimPageState[name];
  const countEl = document.getElementById('dirtyCount' + cap);
  const btnEl = document.getElementById('btnSave' + cap);
  const count = st && st.dirty ? st.dirty.size : 0;
  if (countEl) countEl.textContent = `(${count})`;
  if (btnEl) {
    btnEl.style.fontWeight = count > 0 ? '700' : '400';
    btnEl.style.boxShadow = count > 0 ? '0 0 0 2px rgba(82,196,26,.5)' : 'none';
  }
}

function resetSharedFilters() {
  FILTER_IDS.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  renderTable();
  if (galleryState.loaded) _galleryRender();
}

function _populateSharedFilters() {
  // 从 tableData + 维表缓存中收集可选项
  const devices = new Set();
  const recorders = new Set();
  const tasks = new Set();
  tableData.forEach(r => {
    if (r.device_id) devices.add(r.device_id);
    if (r.recorder_id) recorders.add(r.recorder_id);
    if (r.task_id) tasks.add(r.task_id);
  });
  // 也加上维表里已有的（即便还没有视频引用）
  (dimCache.recorders || []).forEach(c => recorders.add(c.id));
  (dimCache.sd_cards || []).forEach(c => { if (c.device_id) devices.add(c.device_id); });
  (dimCache.tasks || []).forEach(t => { if (t.task_id) tasks.add(t.task_id); });

  function fill(sel, items, defaultText, sortFn) {
    const el = document.getElementById(sel);
    if (!el) return;
    const cur = el.value;
    const sorted = sortFn ? [...items].sort(sortFn) : [...items].sort();
    el.innerHTML = '<option value="">' + defaultText + '</option>' +
      sorted.map(v => `<option value="${esc(v)}">${esc(v)}</option>`).join('');
    el.value = cur;
  }
  // tasks 筛选下拉：按 产品→任务→工具 排序
  const taskSortMap = {};
  (dimCache.tasks || []).forEach(t => {
    taskSortMap[t.task_id] = _taskSortKey(t);
  });
  fill('vFilterDevice', devices, '所有设备');
  fill('vFilterRecorder', recorders, '所有录入员');
  fill('vFilterTask', tasks, '所有任务', (a, b) => {
    const ka = taskSortMap[a] || a.toLowerCase();
    const kb = taskSortMap[b] || b.toLowerCase();
    return ka.localeCompare(kb, 'zh');
  });
}

// 绑定 change 事件（首次）
function _bindSharedFilterChanges() {
  FILTER_IDS.forEach(id => {
    const el = document.getElementById(id);
    if (el && !el._sharedBound) {
      el.addEventListener('change', () => {
        // 筛选改动：两个视图都重新渲染（共用同一组筛选 state）
        _saveSharedFilters();
        renderTable();
        _galleryRender();
      });
      el._sharedBound = true;
    }
  });
}
function _saveSharedFilters() {
  try {
    const state = {};
    FILTER_IDS.forEach(id => {
      const el = document.getElementById(id);
      if (el) state[id] = el.value;
    });
    localStorage.setItem('sharedFilterState', JSON.stringify(state));
  } catch (e) { /* ignore */ }
}
function _restoreSharedFilters() {
  try {
    const raw = localStorage.getItem('sharedFilterState');
    if (!raw) {
      // 无保存状态时，默认筛选"本机本地 + 未上传"
      const locEl = document.getElementById('vFilterLocation');
      if (locEl) locEl.value = 'thisPC_local';
      const upEl = document.getElementById('vFilterUploaded');
      if (upEl) upEl.value = 'No';
      return;
    }
    const state = JSON.parse(raw);
    FILTER_IDS.forEach(id => {
      const el = document.getElementById(id);
      if (el && state[id] !== undefined) el.value = state[id];
    });
    // 如果保存的状态中没有 location 筛选，默认为"本机本地"
    const locEl = document.getElementById('vFilterLocation');
    if (locEl && state['vFilterLocation'] === undefined) locEl.value = 'thisPC_local';
    // 如果保存的状态中没有 uploaded 筛选，默认为"未上传"
    const upEl = document.getElementById('vFilterUploaded');
    if (upEl && state['vFilterUploaded'] === undefined) upEl.value = 'No';
  } catch (e) { /* ignore */ }
}
