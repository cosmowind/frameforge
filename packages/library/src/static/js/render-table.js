// render-table.js — Main table rendering
// Extracted from index.html

/* ── render table ── */
function renderTable() {
  const wrap = document.getElementById('tableWrap');
  const filtered = applySharedFilters(tableData);
  document.getElementById('countLabel').textContent = filtered.length ? `共 ${filtered.length} / ${tableData.length} 条` : (tableData.length ? '无匹配' : '');
  _updateFilterCountLabel(filtered.length);

  if (!tableData.length) {
    wrap.innerHTML = '<div class="empty-state"><h2>暂无数据</h2><p>扫描目录后视频会出现在这里</p></div>';
    return;
  }
  if (!filtered.length) {
    wrap.innerHTML = '<div class="empty-state"><h2>无匹配筛选</h2><p>请清空筛选条件或扫描新目录</p></div>';
    return;
  }

  // Sort filtered data (shared filter applied above)
  const sortedData = [...filtered].sort(compareRows);

  let html = '<table><thead><tr>';
  html += '<th class="col-sel" style="width:36px;text-align:center;"><input type="checkbox" id="selectAll" onchange="toggleSelectAll(this)" title="全选/取消全选"></th>';
  html += '<th class="col-idx">#</th><th class="col-act">操作</th>';
  colConfig.forEach((h, i) => {
    const sortIdx = sortStack.findIndex(s => s.col === h.key);
    let sortIcon, sortedClass;
    if (sortIdx === -1) {
      sortIcon = '<span style="color:#ddd;font-size:10px;">▲</span>';
      sortedClass = '';
    } else {
      const dir = sortStack[sortIdx].dir;
      const arrow = dir === 'asc' ? '▲' : '▼';
      // 多列时显示小角标表示优先级（数字小=优先级高）
      const priority = sortStack.length > 1
        ? `<sup style="font-size:9px;color:#888;margin-left:1px;">${sortIdx + 1}</sup>`
        : '';
      sortIcon = `<span style="color:#1677ff;">${arrow}</span>${priority}`;
      sortedClass = ' sorted';
    }
    html += `<th class="col-${i}${h.visible?'':' col-hidden'} sortable${sortedClass}" data-col="${i}" style="${h.width ? 'width:' + h.width + 'px' : ''}" onclick="toggleSort('${h.key}')" title="点击切换：无 → 升序 → 降序">${h.label}<span class="sort-icon" style="margin-left:4px;">${sortIcon}</span><div class="resize-handle" data-col="${i}"></div></th>`;
  });
  html += '</tr></thead><tbody>';

  sortedData.forEach((row, i) => {
    // Find original index in tableData
    const originalIndex = tableData.indexOf(row);
    const activeClass = (row === tableData[previewIndex]) ? ' active-row' : '';
    const isHistory = (row.location_status || '').endsWith('_history');
    const historyClass = isHistory ? ' history-row' : '';
    html += `<tr data-index="${originalIndex}" data-filtered-idx="${i}" class="${activeClass}${historyClass}">`;
    const isUmi = row.file_type === 'hmd';
    const ps = _preprocessStatusMap[row.path];
    // HMD 未完成预处理时禁用预览按钮
    // 注意：_preprocessStatusMap 初始为空，ps 为 undefined 也表示状态未知 → 禁用
    const hmdNotReady = isUmi && (!ps || ps.hmd_preprocess !== 'done');
    let previewBtn;
    if (isHistory) {
      previewBtn = `<button class="btn btn-outline btn-small btn-preview-disabled" onclick="alert('历史视频无法预览（文件已删除）')">预览</button>`;
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
      previewBtn = `<button class="btn btn-outline btn-small btn-preview-disabled" title="${statusTitle}" disabled>⏳ ${statusLabel}</button>`;
    } else {
      previewBtn = `<button class="btn btn-outline btn-small" onclick="preview(${originalIndex})">预览</button>`;
    }
    html += `<td class="col-sel" style="text-align:center;"><input type="checkbox" class="row-check" data-index="${originalIndex}" data-uploaded="${row.uploaded || 'No'}" data-recorder-id="${row.recorder_id || ''}" data-task-id="${row.task_id || ''}" data-env-id="${row.env_id || ''}" onchange="onCheckChange()"></td>`;
    html += `<td class="col-idx" style="color:#aaa;font-size:12px;white-space:nowrap">${i + 1}</td>`;
    const sameAboveBtn = i > 0 ? ` <button class="btn btn-outline btn-small btn-same-above" onclick="tableSameAsAbove(this)" title="复制上一条的录制员、Task、Env">同上</button>` : '';
    html += `<td class="col-act">${previewBtn}${sameAboveBtn} <button class="btn btn-warning btn-small" onclick="openUploadTemplate(${originalIndex})" title="查看/复制上传参数">📋</button> <button class="btn btn-danger btn-small" onclick="deleteSingle(${originalIndex})" title="删除此条记录">✕</button></td>`;
    colConfig.forEach((col, ci) => {
      const key = col.key, type = col.type;
      const cls = `col-${ci}${col.visible?'':' col-hidden'}`;
      const style = col.width ? ` style="width:${col.width}px"` : '';
      if (type === 'path') {
        html += `<td class="path-cell ${cls}"${style} title="${esc(row[key])}">${esc(row[key])}</td>`;
      } else if (type === 'select-location') {
        // location_status 格式: thisPC_local | thisPC_history | otherPC_local | otherPC_history
        const loc = row[key] || '';
        const parts = loc ? loc.split('_') : [];
        const computer = parts[0] || '';  // 'thisPC' | 'otherPC'
        const state = parts[1] || '';     // 'local' | 'history'
        const tagClass = state === 'history' ? 'history' : 'local';
        const tagText = (computer === 'thisPC' ? '本机' : computer === 'otherPC' ? '其他' : '')
                      + (state === 'history' ? '历史' : state === 'local' ? '本地' : loc);
        html += `<td class="${cls}"${style}><span class="loc-tag ${tagClass}">${tagText}</span></td>`;
      } else if (type === 'select-feasibility') {
        const opts = ['', '高', '中', '低'];
        const fc = row[key]==='高'?'feasibility-high':row[key]==='中'?'feasibility-mid':row[key]==='低'?'feasibility-low':'';
        html += `<td class="${cls}"${style}><select data-key="${key}" class="${fc}" onchange="updateFeasibilityColor(this)">` +
          opts.map(o => `<option value="${o}" ${row[key]===o?'selected':''}>${o||'--'}</option>`).join('') +
          '</select></td>';
      } else if (type === 'select-yesno') {
        html += `<td class="${cls}"${style}><select data-key="${key}" onchange="updateUploadedDisplay(this)">
          <option value="No" ${row[key]!=='Yes'?'selected':''}></option>
          <option value="Yes" ${row[key]==='Yes'?'selected':''}>✓</option>
        </select></td>`;
      } else if (type === 'duration') {
        // duration_sec 显示为 M:SS / H:MM:SS（从整数秒格式化）；HMD 行附 size 粗算的 (估 M:SS) 参考
        const secVal = parseInt(row[key] || '', 10);
        const realDisplay = (!isNaN(secVal) && secVal > 0) ? fmtDur(secVal) : esc(row[key] || '');
        let estimateHtml = '';
        const isUmi = (row.file_type || '') === 'hmd';
        if (isUmi) {
          // 优先用后端预计算的 _estimate_sec；前端也能即时算
          let estSec = parseInt(row._estimate_sec || '0', 10);
          if (!estSec && row._size_mb && estimateRatioMbPerMin) {
            estSec = Math.round((row._size_mb / estimateRatioMbPerMin) * 60);
          }
          if (estSec > 0) {
            const ratioLabel = (!isNaN(secVal) && secVal > 0)
              ? ` · ${(estSec / Math.max(secVal, 1) * 100).toFixed(0)}%`
              : '';
            estimateHtml = `<span style="color:#999;font-size:11px;">（估 ${fmtDur(estSec)}${ratioLabel}）</span>`;
          } else {
            estimateHtml = `<span style="color:#bbb;font-size:11px;">（未处理）</span>`;
          }
        }
        html += `<td class="${cls}"${style}><span>${realDisplay || (isUmi ? '<span style=\"color:#bbb;\">--</span>' : '')}</span> ${estimateHtml}</td>`;
      } else if (type && type.startsWith('select-dimension:')) {
        // 维表 select：改为 searchable-sel，输入即可搜索
        const dim = type.split(':')[1];
        const dimRows = dimCache[dim] || [];
        const PRIMARY = { recorders: 'id', sd_cards: 'device_id', tasks: 'task_id' };
        const primary = PRIMARY[dim] || (dimRows[0] ? Object.keys(dimRows[0])[0] : 'id');
        const cur = row[key] || '';
        const labelFor = r => {
          if (dim === 'recorders') return [r.id, r.name].filter(Boolean).join(' · ') || r[primary];
          if (dim === 'sd_cards') {
            const parts = [r.device_id, r.device_name];
            if (r.volume_serial) parts.push('[' + r.volume_serial.slice(-6) + ']');
            return parts.filter(Boolean).join(' · ') || r[primary];
          }
          if (dim === 'tasks') return [r.product, r.task, r.process].filter(Boolean).join(' · ') || r[primary];
          if (dim === 'environments') return r.environment_description || r[primary] || '';
          return r[primary] || '';
        };
        const sortedDimRows = dim === 'tasks'
          ? [...dimRows].sort((a, b) => _taskSortKey(a).localeCompare(_taskSortKey(b), 'zh'))
          : dimRows;
        const ssUid = 'rt-' + originalIndex + '-' + key.replace(/[^a-zA-Z0-9]/g, '_');
        if (!window._ssOpts) window._ssOpts = {};
        window._ssOpts[ssUid] = sortedDimRows.map(r => ({ v: r[primary] || '', d: labelFor(r) }));
        // 未匹配的值作为 phantom 项加入
        if (cur && !dimRows.some(r => (r[primary] || '') === cur)) {
          window._ssOpts[ssUid].push({ v: cur, d: cur + ' (未在 ' + dim + ' 中)' });
        }
        const ssOpts = window._ssOpts[ssUid];
        let curDisplay = cur;
        if (cur) {
          const found = ssOpts.find(o => o.v === cur);
          if (found) curDisplay = found.d;
        }
        window._ssOpts[ssUid].onSelect = function(value) {
          const valEl = document.getElementById(ssUid + '_val');
          if (valEl) dimRowInput('videos', valEl);
        };
        html += `<td class="${cls}"${style}><span class="searchable-sel" style="position:relative;display:inline-block;width:100%;">
          <input class="searchable-sel-input" id="${ssUid}_inp" type="text" value="${esc(curDisplay)}"
            onfocus="ssOpen('${ssUid}')" oninput="ssFilter('${ssUid}')"
            onkeydown="ssKeyNav(event,'${ssUid}')"
            placeholder="搜索…" autocomplete="off" style="width:100%;box-sizing:border-box;">
          <input type="hidden" data-field="${key}" class="searchable-sel-val" id="${ssUid}_val" value="${esc(cur)}">
          <div class="searchable-sel-drop" id="${ssUid}_drop" style="display:none;position:fixed;z-index:2147483647;background:#fff;border:1px solid #d9d9d9;border-radius:4px;max-height:240px;overflow-y:auto;box-shadow:0 4px 12px rgba(0,0,0,0.18);font-size:13px;"></div>
        </span></td>`;
      } else if (type === 'select-capture-mode') {
        const opts = (uploadOpts && uploadOpts.captureModes) || [];
        html += `<td class="${cls}"${style}><select data-key="${key}" onchange="dimRowInput('videos', this)">
          <option value="">--</option>` +
          opts.map(o => `<option value="${o.value}" ${row[key]===o.value?'selected':''}>${o.label}</option>`).join('') +
          `</select></td>`;
      } else if (type === 'select-country') {
        const opts = (uploadOpts && uploadOpts.countries) || [];
        html += `<td class="${cls}"${style}><select data-key="${key}" onchange="onCountryChange(this); dimRowInput('videos', this)">
          <option value="">--</option>` +
          opts.map(o => `<option value="${o.value}" ${row[key]===o.value?'selected':''}>${o.label}</option>`).join('') +
          `</select></td>`;
      } else if (type === 'select-region') {
        // region 依赖 country_code；显示当前值 + 对应国家下的选项
        const country = row['country_code'] || '';
        const regionRows = (uploadOpts && uploadOpts.regions && uploadOpts.regions[country]) || [];
        const cur = row[key] || '';
        if (regionRows.length > 0) {
          html += `<td class="${cls}"${style}><select data-key="${key}" onchange="dimRowInput('videos', this)">
            <option value="">--</option>` +
            regionRows.map(r => `<option value="${r.value}" ${cur===r.value?'selected':''}>${r.label}</option>`).join('') +
            (cur && !regionRows.some(r => r.value === cur) ? `<option value="${esc(cur)}" selected>${esc(cur)}</option>` : '') +
            `</select></td>`;
        } else {
          html += `<td class="${cls}"${style}><input type="text" data-key="${key}" value="${esc(cur)}"></td>`;
        }
      } else if (type === 'select-scene-category') {
        const opts = (uploadOpts && uploadOpts.sceneCategories) || [];
        html += `<td class="${cls}"${style}><select data-key="${key}" onchange="onSceneCategoryChange(this); dimRowInput('videos', this)">
          <option value="">--</option>` +
          opts.map(o => `<option value="${o.value}" ${row[key]===o.value?'selected':''}>${o.label}</option>`).join('') +
          `</select></td>`;
      } else if (type === 'select-scene-subcategory') {
        // 依赖 scene_category 的值
        const catVal = row['scene_category'] || '';
        const cats = (uploadOpts && uploadOpts.sceneCategories) || [];
        const cat = cats.find(c => c.value === catVal);
        const subs = cat ? cat.subcategories : [];
        const cur = row[key] || '';
        html += `<td class="${cls}"${style}><select data-key="${key}" onchange="onSceneSubcategoryChange(this); dimRowInput('videos', this)">
          <option value="">--</option>` +
          subs.map(s => `<option value="${s.value}" ${cur===s.value?'selected':''}>${s.label}</option>`).join('') +
          (cur && !subs.some(s => s.value === cur) ? `<option value="${esc(cur)}" selected>${esc(cur)}</option>` : '') +
          `</select></td>`;
      } else if (type === 'select-environment') {
        const opts = (uploadOpts && uploadOpts.environments) || [];
        html += `<td class="${cls}"${style}><select data-key="${key}" onchange="dimRowInput('videos', this)">
          <option value="">--</option>` +
          opts.map(o => `<option value="${o.value}" ${row[key]===o.value?'selected':''}>${o.label}</option>`).join('') +
          `</select></td>`;
      } else if (type === 'select-facility-venue') {
        const opts = (uploadOpts && uploadOpts.facilityVenues) || [];
        html += `<td class="${cls}"${style}><select data-key="${key}" onchange="dimRowInput('videos', this)">
          <option value="">--</option>` +
          opts.map(o => `<option value="${o.value}" ${row[key]===o.value?'selected':''}>${o.label}</option>`).join('') +
          `</select></td>`;
      } else if (type === 'textarea') {
        html += `<td class="${cls}"${style}><textarea data-key="${key}" rows="2">${esc(row[key])}</textarea></td>`;
      } else if (key === 'work_content_en') {
        html += `<td class="${cls}"${style}><input type="text" data-key="${key}" value="${esc(row[key])}"></td>`;
      } else if (key === 'scan_date') {
        // 录入日期：默认只读，避免误改；点 ✏️ 才解锁（解锁后显示红边）
        html += `<td class="${cls}"${style}>
          <div style="display:flex;gap:4px;align-items:center;">
            <input type="text" data-key="${key}" value="${esc(row[key])}"
                   readonly title="默认锁定，点右侧 ✏️ 解锁后才能编辑"
                   style="flex:1;min-width:0;background:#fafafa;color:#555;">
            <button class="btn btn-outline btn-small btn-unlock-date" data-row="${originalIndex}"
                    title="解锁后即可手动修改此日期（不推荐；后端会保护不被清空）"
                    onclick="event.stopPropagation();toggleScanDateLock(this)"
                    style="padding:2px 6px;font-size:11px;">✏️</button>
          </div>
        </td>`;
      } else {
        html += `<td class="${cls}"${style}><input type="text" data-key="${key}" value="${esc(row[key])}"></td>`;
      }
    });
    html += '</tr>';
  });

  html += '</tbody></table>';
  wrap.innerHTML = html;
}
