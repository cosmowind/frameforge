// upload-options-cache.js — Upload options caching + select-search
// Extracted from index.html

/* ============================================================ */
/* === UPLOAD OPTIONS CACHE (枚举数据：国家、场景等)            === */
/* ============================================================ */
async function loadUploadOpts() {
  if (uploadOpts) return uploadOpts;
  try {
    const r = await fetch('/api/upload-options');
    if (r.ok) {
      uploadOpts = await r.json();
      // also load editable dim options
      await loadEditableOpts();
      return uploadOpts;
    }
  } catch (e) {
    console.warn('[uploadOpts]', e);
  }
  // fallback
  uploadOpts = {
    captureModes: [
      {value: 'single', label: '单目'},
      {value: 'stereo', label: '双目立体'},
      {value: 'three_views', label: '三目'},
    ],
    countries: [],
    regions: {},
    sceneCategories: [],
    scenes: [],
    sceneNames: [],
    gloves: [
      {value: 'No — bare hands', label: '否 — 裸手'},
      {value: 'Yes — wearing gloves', label: '是 — 佩戴手套'},
    ],
    environments: [],
    facilityVenues: [],
  };
  return uploadOpts;
}

let editableOpts = {}; // { scene: [{value,label}], business_type: [...], business_name: [...] }

async function loadEditableOpts() {
  try {
    const r = await fetch('/api/dim-editable-options');
    if (r.ok) {
      editableOpts = await r.json();
    }
  } catch (e) {
    console.warn('[editableOpts]', e);
  }
}

function getEditableOptions(field) {
  // Merge taxonomy defaults with user-stored options
  if (!editableOpts || !editableOpts[field]) return [];
  return editableOpts[field] || [];
}

async function saveEditableOption(field, action, option, value) {
  try {
    const body = { field, action };
    if (action === 'add' && option) body.option = option;
    if (action === 'remove' && value) body.value = value;
    if (action === 'set' && Array.isArray(option)) body.options = option;
    const r = await fetch('/api/dim-editable-options', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (r.ok) {
      await loadEditableOpts();
    }
    return r.ok;
  } catch (e) {
    console.warn('[saveEditableOption]', e);
    return false;
  }
}

/* -- Editable options modal -- */
let _editOptField = '';
let _editOptName = '';

function openEditOptionsModal(name, fieldName) {
  _editOptField = fieldName;
  _editOptName = name;
  const opts = getEditableOptions(fieldName);
  const content = document.getElementById('editOptContent');
  let html = `<div style="margin-bottom:8px;font-size:12px;color:#888;">管理「${fieldName}」下拉选项（中文=显示，英文=上传值）</div>`;
  html += '<table style="width:100%;font-size:12px;border-collapse:collapse;">';
  html += '<tr><th style="text-align:left;padding:4px;">中文标签</th><th style="text-align:left;padding:4px;">英文值</th><th style="width:40px;"></th></tr>';
  opts.forEach(o => {
    html += `<tr><td style="padding:2px 4px;">${esc(o.label||'')}</td><td style="padding:2px 4px;color:#888;">${esc(o.value||'')}</td><td><button class="btn btn-danger btn-tiny" onclick="delEditOpt('${esc(o.value)}')">×</button></td></tr>`;
  });
  html += '</table>';
  html += `<div style="margin-top:8px;display:flex;gap:4px;">
    <input id="editOptLabel" placeholder="中文标签" style="flex:1;padding:4px;font-size:12px;">
    <input id="editOptValue" placeholder="英文值" style="flex:1;padding:4px;font-size:12px;">
    <button class="btn btn-primary btn-tiny" onclick="addEditOpt()">添加</button>
  </div>`;
  content.innerHTML = html;
  document.getElementById('editOptionsOverlay').classList.remove('hidden');
}

function closeEditOptionsModal() {
  document.getElementById('editOptionsOverlay').classList.add('hidden');
}

async function addEditOpt() {
  const label = document.getElementById('editOptLabel').value.trim();
  const value = document.getElementById('editOptValue').value.trim();
  if (!label || !value) return;
  await saveEditableOption(_editOptField, 'add', { label, value });
  // re-render table
  if (_editOptName === 'tasks') dimRenderTable(_editOptName);
  openEditOptionsModal(_editOptName, _editOptField);
}

async function delEditOpt(value) {
  await saveEditableOption(_editOptField, 'remove', null, value);
  if (_editOptName === 'tasks') dimRenderTable(_editOptName);
  openEditOptionsModal(_editOptName, _editOptField);
}

/* ── 可搜索下拉（scene 等大量选项字段）── */
let _ssTimer = null;
let _ssHlIdx = -1; // keyboard highlight index

function ssOpen(uid) {
  const inp = document.getElementById(uid + '_inp');
  const drop = document.getElementById(uid + '_drop');
  if (!inp || !drop) return;
  const opts = (window._ssOpts && window._ssOpts[uid]) || [];
  _ssHlIdx = -1;
  // 用 fixed 定位，避免被 overflow:hidden 裁剪
  const rect = inp.getBoundingClientRect();
  drop.style.left = rect.left + 'px';
  drop.style.top = (rect.bottom + 2) + 'px';
  drop.style.minWidth = rect.width + 'px';
  ssRenderList(uid, opts);
  drop.style.display = 'block';
}

function ssFilter(uid) {
  const inp = document.getElementById(uid + '_inp');
  const drop = document.getElementById(uid + '_drop');
  if (!inp || !drop) return;
  const q = (inp.value || '').toLowerCase();
  const opts = (window._ssOpts && window._ssOpts[uid]) || [];
  const filtered = q ? opts.filter(o => o.d.toLowerCase().includes(q) || o.v.toLowerCase().includes(q)) : opts;
  _ssHlIdx = -1;
  // reposition in case of scroll
  const rect = inp.getBoundingClientRect();
  drop.style.left = rect.left + 'px';
  drop.style.top = (rect.bottom + 2) + 'px';
  drop.style.minWidth = rect.width + 'px';
  ssRenderList(uid, filtered);
  drop.style.display = 'block';
}

function ssBlur(uid) {
  // 延迟关闭，让 mousedown 有机会触发选项点击
  clearTimeout(_ssTimer);
  _ssTimer = setTimeout(() => {
    const drop = document.getElementById(uid + '_drop');
    if (drop) drop.style.display = 'none';
  }, 180);
}

function ssKeyNav(e, uid) {
  const drop = document.getElementById(uid + '_drop');
  if (!drop || drop.style.display === 'none') return;
  const items = drop.querySelectorAll('.ss-item');
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    if (items.length) { _ssHlIdx = Math.min(_ssHlIdx + 1, items.length - 1); ssUpdateHl(items, _ssHlIdx); }
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    if (items.length) { _ssHlIdx = Math.max(_ssHlIdx - 1, 0); ssUpdateHl(items, _ssHlIdx); }
  } else if (e.key === 'Enter') {
    e.preventDefault();
    if (_ssHlIdx >= 0 && items[_ssHlIdx]) {
      const el = items[_ssHlIdx];
      ssSelect(uid, el.dataset.v, el.dataset.d);
    }
  } else if (e.key === 'Escape') {
    drop.style.display = 'none';
    document.getElementById(uid + '_inp').focus();
  }
}

function ssUpdateHl(items, idx) {
  items.forEach((el, i) => { el.style.background = i === idx ? '#e6f7ff' : ''; });
  if (items[idx]) items[idx].scrollIntoView({ block: 'nearest' });
}

function ssRenderList(uid, opts) {
  const drop = document.getElementById(uid + '_drop');
  if (!drop) return;
  let html = '';
  if (opts.length === 0) {
    html = '<div style="padding:8px;color:#999;">无匹配结果</div>';
  } else {
    const max = Math.min(opts.length, 100);
    for (let i = 0; i < max; i++) {
      const o = opts[i];
      html += `<div class="ss-item" data-v="${esc(o.v)}" data-d="${esc(o.d)}" style="padding:4px 8px;cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${esc(o.d)}</div>`;
    }
    if (opts.length > 100)
      html += `<div style="padding:4px 8px;color:#999;font-size:11px;">…还有 ${opts.length - 100} 项，请继续输入关键词</div>`;
  }
  drop.innerHTML = html;
  drop.querySelectorAll('.ss-item').forEach(el => {
    el.addEventListener('mousedown', function(ev) {
      ev.preventDefault();
      ssSelect(uid, this.dataset.v, this.dataset.d);
    });
  });
}

function ssSelect(uid, value, display) {
  const inp = document.getElementById(uid + '_inp');
  const valEl = document.getElementById(uid + '_val');
  inp.value = display;
  valEl.value = value;
  const drop = document.getElementById(uid + '_drop');
  if (drop) drop.style.display = 'none';
  _ssHlIdx = -1;

  // ── 视频管理页面：直接更新 tableData，并立即触发保存 ──
  if (uid.startsWith('rt-')) {
    // uid 格式：rt-{originalIndex}-{fieldName}，originalIndex 是 tableData 的真实索引
    const parts = uid.split('-');
    const originalIndex = parseInt(parts[1], 10);
    const field = valEl && valEl.dataset && valEl.dataset.field;
    console.log('[ssSelect rt-] uid=', uid, 'originalIndex=', originalIndex, 'field=', field, 'tableData length=', tableData.length);
    if (!isNaN(originalIndex) && tableData[originalIndex] !== undefined && field) {
      console.log('[ssSelect rt-] BEFORE tableData[originalIndex][field]=', tableData[originalIndex][field], '-> setting to', value);
      tableData[originalIndex][field] = value;
      markRowDirty(originalIndex);
      console.log('[ssSelect rt-] AFTER tableData[originalIndex][field]=', tableData[originalIndex][field], 'dirtyRows size=', dirtyRows.size);
      // 立即触发保存（silent 避免和预览区 saveAll 的 toast 冲突）
      saveDirtyRows(true);
    } else {
      console.warn('[ssSelect rt-] index out of bounds or field missing: originalIndex=', originalIndex, 'tableData[originalIndex]=', tableData[originalIndex]);
    }
    return;
  }

  // ── 维表 / filter-dropdown ──
  const optEntry = (window._ssOpts && window._ssOpts[uid]) || {};
  if (typeof optEntry.onSelect === 'function') {
    optEntry.onSelect(value, display);
  } else {
    const name = uid.split('-')[1];
    if (typeof dimRowInput === 'function') dimRowInput(name, valEl);
  }
}

// 点击外部关闭所有搜索下拉
document.addEventListener('click', function(e) {
  if (!e.target.closest('.searchable-sel')) {
    document.querySelectorAll('.searchable-sel-drop').forEach(d => d.style.display = 'none');
    _ssHlIdx = -1;
  }
});

/* ── 级联下拉：国家 → 地区 ── */
function onCountryChange(el) {
  const tr = el.closest('tr');
  if (!tr) return;
  const idx = parseInt(tr.dataset.index);
  if (isNaN(idx) || !tableData[idx]) return;
  const country = el.value;
  tableData[idx]['country_code'] = country;
  // 重置 region
  tableData[idx]['region'] = '';
  renderTable();
}

/* ── 级联下拉：场景大类 → 场景子类 ── */
function onSceneCategoryChange(el) {
  const tr = el.closest('tr');
  if (!tr) return;
  const idx = parseInt(tr.dataset.index);
  if (isNaN(idx) || !tableData[idx]) return;
  tableData[idx]['scene_category'] = el.value;
  tableData[idx]['scene_subcategory'] = '';
  renderTable();
}

/* ── 场景子类变化 ── */
function onSceneSubcategoryChange(el) {
  const tr = el.closest('tr');
  if (!tr) return;
  const idx = parseInt(tr.dataset.index);
  if (isNaN(idx) || !tableData[idx]) return;
  tableData[idx]['scene_subcategory'] = el.value;
  renderTable();
}

/* ── 级联下拉（DIM表版本）：场景大类 → 场景子类 ── */
function dimOnSceneCategoryChange(name, el) {
  const tr = el.closest('tr');
  if (!tr) return;
  const st = dimPageState[name];
  if (!st) return;
  const key = tr.dataset.key || '';
  const primary = st.schema[0];
  const row = st.rows.find(r => (r[primary] || '') === key) || st.rows.find(r => r._tmpKey === key);
  if (!row) return;
  row['scene_subcategory'] = '';
  st.dirty.add(key);
  tr.classList.add('dirty');
  _updateDimSaveCount(name);
  dimRenderTable(name); // 重新渲染以联动子类下拉
}

/* ── 场景子类变化（DIM表版本） ── */
function dimOnSceneSubcategoryChange(name, el) {
  const sub = el.value;
  // no-op for now (was clearing scene_custom_label)
}
