// preview-player.js — Video preview player, navigation, and helper functions
// Extracted from index.html

/* ── preview ── */
function preview(index) {
  syncPreviewToData();
  previewIndex = index;
  const row = tableData[index];
  const area = document.getElementById('previewArea');
  const video = document.getElementById('videoPlayer');

  // HMD folder entry → 打开内嵌 HMD 预览面板（同页，不弹新窗口）
  // 优化：更准确地识别HMD session
  const rowIsUmi = row.file_type === 'hmd'
    || (row.path && (
      /session_\d+/.test(row.path) ||  // 路径包含 session_xxxxx
      row.path.endsWith('.mcap') ||  // .mcap 文件
      (row.extra_description && /HMD session/i.test(row.extra_description))  // extra_description 包含 HMD session
    ));
  if (rowIsUmi) {
    const folder = row.path;
    closePlayer();
    openHmdPreviewInline(folder);
    return;
  }

  area.classList.add('active');
  video.src = '/api/video?path=' + encodeURIComponent(row.path);
  video.play().catch(() => {});
  document.getElementById('previewPath').textContent = row.path;

  // build form
  const form = document.getElementById('previewForm');
  let fhtml = '';
  colConfig.forEach(col => {
    if (col.key === 'path') return;
    if (col.type === 'select-location') {
      fhtml += `<label><span>${col.label}</span><select data-key="${col.key}" onchange="updateLocationDisplay(this)">
        <option value="local" ${row[col.key]!=='history'?'selected':''}>本地</option>
        <option value="history" ${row[col.key]==='history'?'selected':''}>历史</option>
      </select></label>`;
    } else if (col.type === 'select-feasibility') {
      const opts = ['', '高', '中', '低'];
      const fc = row[col.key]==='高'?'feasibility-high':row[col.key]==='中'?'feasibility-mid':row[col.key]==='低'?'feasibility-low':'';
      fhtml += `<label><span>${col.label}</span><select data-key="${col.key}" class="${fc}" onchange="updateFeasibilityColor(this)">` +
        opts.map(o => `<option value="${o}" ${row[col.key]===o?'selected':''}>${o||'--'}</option>`).join('') +
        '</select></label>';
    } else if (col.type === 'select-yesno') {
      fhtml += `<label><span>${col.label}</span><select data-key="${col.key}" onchange="updateUploadedDisplay(this)">
        <option value="No" ${row[col.key]!=='Yes'?'selected':''}></option>
        <option value="Yes" ${row[col.key]==='Yes'?'selected':''}>✓</option>
      </select></label>`;
    } else if (col.key === 'extra_description') {
      fhtml += `<label><span>${col.label}</span><textarea data-key="${col.key}">${esc(row[col.key])}</textarea></label>`;
    } else if (col.type === 'duration') {
      const secVal = parseInt(row[col.key] || '', 10);
      const realDisplay = (!isNaN(secVal) && secVal > 0) ? fmtDur(secVal) : (row[col.key] || '--');
      let estimateHtml = '';
      const isUmi = (row.file_type || '') === 'hmd';
      if (isUmi) {
        let estSec = parseInt(row._estimate_sec || '0', 10);
        if (!estSec && row._size_mb && estimateRatioMbPerMin) {
          estSec = Math.round((row._size_mb / estimateRatioMbPerMin) * 60);
        }
        if (estSec > 0) {
          estimateHtml = ` <span style="color:#999;font-size:11px;">（估 ${fmtDur(estSec)}）</span>`;
        }
      }
      fhtml += `<label><span>${col.label}</span><span style="padding:6px 8px;color:#555;">${esc(realDisplay)}${estimateHtml}</span></label>`;
    } else if (col.type && col.type.startsWith('select-dimension:')) {
      const dim = col.type.split(':')[1];
      const dimRows = dimCache[dim] || [];
      const PRIMARY = { recorders: 'id', sd_cards: 'device_id', tasks: 'task_id' };
      const primary = PRIMARY[dim] || (dimRows[0] ? Object.keys(dimRows[0])[0] : 'id');
      const cur = row[col.key] || '';
      const matched = dimRows.some(r => (r[primary] || '') === cur);
      const labelFor = r => {
        if (dim === 'recorders') {
          return [r.id, r.name].filter(Boolean).join(' · ') || r[primary];
        }
        if (dim === 'sd_cards') {
          const parts = [r.device_id, r.device_name];
          if (r.volume_serial) parts.push('[' + r.volume_serial.slice(-6) + ']');
          return parts.filter(Boolean).join(' · ') || r[primary];
        }
        if (dim === 'tasks') {
          const ctx = [r.scene, r.product].filter(Boolean).join(' / ');
          const parts = [r.task_id];
          if (ctx) parts.push(ctx);
          if (r.task) parts.push(r.task);
          return parts.join(' · ') || r[primary];
        }
        return r[primary] || '';
      };
      // tasks 下拉按 产品→任务→工具 排序
      const sortedDimRows = dim === 'tasks'
        ? [...dimRows].sort((a, b) => _taskSortKey(a).localeCompare(_taskSortKey(b), 'zh'))
        : dimRows;
      const opts = sortedDimRows.map(r => {
        const v = r[primary] || '';
        return `<option value="${esc(v)}" ${v === cur && matched ? 'selected' : ''}>${esc(labelFor(r))}</option>`;
      }).join('');
      const orphan = !matched && cur
        ? `<option value="${esc(cur)}" selected>${esc(cur)} (未在 ${dim} 中)</option>`
        : '';
      fhtml += `<label><span>${col.label}</span><select data-key="${col.key}">`
        + `<option value="">--</option>` + orphan + opts + `</select></label>`;
    } else if (col.type === 'select-capture-mode') {
      const opts = (uploadOpts && uploadOpts.captureModes) || [];
      fhtml += `<label><span>${col.label}</span><select data-key="${col.key}">`
        + `<option value="">--</option>`
        + opts.map(o => `<option value="${o.value}" ${row[col.key]===o.value?'selected':''}>${o.label}</option>`).join('')
        + `</select></label>`;
    } else if (col.type === 'select-country') {
      const opts = (uploadOpts && uploadOpts.countries) || [];
      fhtml += `<label><span>${col.label}</span><select data-key="${col.key}">`
        + `<option value="">--</option>`
        + opts.map(o => `<option value="${o.value}" ${row[col.key]===o.value?'selected':''}>${o.label}</option>`).join('')
        + `</select></label>`;
    } else if (col.type === 'select-region') {
      const country = row['country_code'] || '';
      const regionRows = (uploadOpts && uploadOpts.regions && uploadOpts.regions[country]) || [];
      const cur = row[col.key] || '';
      if (regionRows.length > 0) {
        fhtml += `<label><span>${col.label}</span><select data-key="${col.key}">`
          + `<option value="">--</option>`
          + regionRows.map(r => `<option value="${r.value}" ${cur===r.value?'selected':''}>${r.label}</option>`).join('')
          + (cur && !regionRows.some(r => r.value === cur) ? `<option value="${esc(cur)}" selected>${esc(cur)}</option>` : '')
          + `</select></label>`;
      } else {
        fhtml += `<label><span>${col.label}</span><input type="text" data-key="${col.key}" value="${esc(cur)}"></label>`;
      }
    } else if (col.type === 'select-scene-category') {
      const opts = (uploadOpts && uploadOpts.sceneCategories) || [];
      fhtml += `<label><span>${col.label}</span><select data-key="${col.key}">`
        + `<option value="">--</option>`
        + opts.map(o => `<option value="${o.value}" ${row[col.key]===o.value?'selected':''}>${o.label}</option>`).join('')
        + `</select></label>`;
    } else if (col.type === 'select-scene-subcategory') {
      const catVal = row['scene_category'] || '';
      const cats = (uploadOpts && uploadOpts.sceneCategories) || [];
      const cat = cats.find(c => c.value === catVal);
      const subs = cat ? cat.subcategories : [];
      const cur = row[col.key] || '';
      fhtml += `<label><span>${col.label}</span><select data-key="${col.key}">`
        + `<option value="">--</option>`
        + subs.map(s => `<option value="${s.value}" ${cur===s.value?'selected':''}>${s.label}</option>`).join('')
        + (cur && !subs.some(s => s.value === cur) ? `<option value="${esc(cur)}" selected>${esc(cur)}</option>` : '')
        + `</select></label>`;
    } else if (col.type === 'select-environment') {
      const opts = (uploadOpts && uploadOpts.environments) || [];
      fhtml += `<label><span>${col.label}</span><select data-key="${col.key}">`
        + `<option value="">--</option>`
        + opts.map(o => `<option value="${o.value}" ${row[col.key]===o.value?'selected':''}>${o.label}</option>`).join('')
        + `</select></label>`;
    } else if (col.type === 'select-facility-venue') {
      const opts = (uploadOpts && uploadOpts.facilityVenues) || [];
      fhtml += `<label><span>${col.label}</span><select data-key="${col.key}">`
        + `<option value="">--</option>`
        + opts.map(o => `<option value="${o.value}" ${row[col.key]===o.value?'selected':''}>${o.label}</option>`).join('')
        + `</select></label>`;
    } else if (col.type === 'textarea') {
      fhtml += `<label><span>${col.label}</span><textarea data-key="${col.key}">${esc(row[col.key])}</textarea></label>`;
    } else if (col.key === 'work_content_en') {
      fhtml += `<label><span>${col.label}</span><input type="text" data-key="${col.key}" value="${esc(row[col.key])}"></label>`;
    } else {
      fhtml += `<label><span>${col.label}</span><input type="text" data-key="${col.key}" value="${esc(row[col.key])}"></label>`;
    }
  });
  form.innerHTML = fhtml;

  // sync preview form edits to tableData in real time
  form.oninput = form.onchange = e => {
    const el = e.target;
    if (el.dataset.key && tableData[previewIndex]) {
      tableData[previewIndex][el.dataset.key] = el.value;
    }
  };

  // highlight row
  document.querySelectorAll('tbody tr').forEach(tr => tr.classList.remove('active-row'));
  const tr = document.querySelector(`tr[data-index="${index}"]`);
  if (tr) tr.classList.add('active-row');

  area.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function navPreview(dir) {
  if (!tableData.length) return;
  syncPreviewToData();
  let next = previewIndex + dir;
  if (next < 0) next = tableData.length - 1;
  if (next >= tableData.length) next = 0;
  preview(next);
}

function closePlayer() {
  const area = document.getElementById('previewArea');
  const video = document.getElementById('videoPlayer');
  video.pause();
  video.src = '';
  area.classList.remove('active');
  previewIndex = -1;
  document.querySelectorAll('tbody tr').forEach(tr => tr.classList.remove('active-row'));
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}

// 把整数秒格式化为 M:SS 或 H:MM:SS（与后端 _fmt_duration 一致）
function fmtDur(sec) {
  sec = parseInt(sec, 10) || 0;
  if (sec <= 0) return '';
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  return `${m}:${String(s).padStart(2,'0')}`;
}

function updateUploadedDisplay(sel) {
  // visual feedback handled by option text (✓ vs empty)
}

function updateLocationDisplay(sel) {
  // Update the tag display in the table row
  const idx = previewIndex;
  if (idx < 0) return;
  tableData[idx].location_status = sel.value;
  // Re-render to update tag
  renderTable();
  // Restore preview state
  previewIndex = idx;
}

function updateFeasibilityColor(sel) {
  sel.classList.remove('feasibility-high', 'feasibility-mid', 'feasibility-low');
  const v = sel.value;
  if (v === '高') sel.classList.add('feasibility-high');
  else if (v === '中') sel.classList.add('feasibility-mid');
  else if (v === '低') sel.classList.add('feasibility-low');
}
