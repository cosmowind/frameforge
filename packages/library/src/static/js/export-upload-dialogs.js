// export-upload-dialogs.js — Export TXT and Upload dialog functions
// Extracted from index.html

/* ── export ── */
function openExportDialog() {
  if (!tableData.length) { alert('无数据可导出'); return; }
  const dialog = document.getElementById('exportDialog');

  // build column list
  const colList = document.getElementById('exportColList');
  colList.innerHTML = '';
  colConfig.forEach(col => {
    const chip = document.createElement('span');
    chip.className = 'dialog-col-item';
    chip.textContent = col.label;
    chip.dataset.key = col.key;
    chip.onclick = () => chip.classList.toggle('on');
    colList.appendChild(chip);
  });

  // build row list
  const rowList = document.getElementById('exportRowList');
  rowList.innerHTML = '';
  // "全部" option
  const allChip = document.createElement('span');
  allChip.className = 'dialog-row-item all on';
  allChip.textContent = '全部';
  allChip.dataset.val = 'all';
  allChip.onclick = () => {
    if (allChip.classList.contains('on')) {
      allChip.classList.remove('on');
    } else {
      allChip.classList.add('on');
      document.querySelectorAll('.dialog-row-item:not(.all)').forEach(c => c.classList.remove('on'));
    }
  };
  rowList.appendChild(allChip);

  tableData.forEach((_, i) => {
    const chip = document.createElement('span');
    chip.className = 'dialog-row-item';
    chip.textContent = '#' + (i + 1);
    chip.dataset.val = i;
    chip.onclick = () => {
      chip.classList.toggle('on');
      allChip.classList.remove('on');
    };
    rowList.appendChild(chip);
  });

  document.getElementById('exportSep').value = '.';
  document.getElementById('exportRowRange').value = '';
  dialog.classList.remove('hidden');
}

function onExportRangeInput() {
  const rangeStr = document.getElementById('exportRowRange').value.trim();
  const allChip = document.querySelector('#exportRowList .dialog-row-item.all');
  const rowChips = document.querySelectorAll('#exportRowList .dialog-row-item:not(.all)');

  // Clear all individual selections
  rowChips.forEach(c => c.classList.remove('on'));
  if (allChip) allChip.classList.remove('on');

  if (!rangeStr) return;

  const [start, end] = parseRange(rangeStr);
  if (start < 0) return;

  rowChips.forEach(c => {
    const idx = parseInt(c.dataset.val);
    if (idx >= start && idx <= end) {
      c.classList.add('on');
    }
  });
}

function parseRange(rangeStr) {
  // Parse "x-y" → [start_idx_0based, end_idx_0based]. Returns [-1, -1] on invalid.
  const m = rangeStr.match(/^(\d+)\s*-\s*(\d+)$/);
  if (!m) return [-1, -1];
  let s = parseInt(m[1]) - 1;
  let e = parseInt(m[2]) - 1;
  if (s < 0 || e < 0 || s > e) return [-1, -1];
  if (e >= tableData.length) e = tableData.length - 1;
  return [s, e];
}

function closeExportDialog() {
  document.getElementById('exportDialog').classList.add('hidden');
}

/* helper: get sorted mapping from display position to original tableData index */
function getSortedMapping() {
  return [...tableData]
    .map((row, i) => ({ orig: i, row }))
    .sort((a, b) => compareRows(a.row, b.row))
    .map(x => x.orig);
}

/* parse range against an explicit max length */
function parseRangeLen(rangeStr, maxLen) {
  const m = rangeStr.match(/^(\d+)\s*-\s*(\d+)$/);
  if (!m) return [-1, -1];
  let s = parseInt(m[1]) - 1;
  let e = parseInt(m[2]) - 1;
  if (s < 0 || e < 0 || s > e) return [-1, -1];
  if (e >= maxLen) e = maxLen - 1;
  return [s, e];
}

/* ── upload dialog ── */
async function openUploadDialog() {
  const dialog = document.getElementById('uploadDialog');
  const rowList = document.getElementById('uploadRowList');
  const resultDiv = document.getElementById('uploadResult');

  // Reset state
  resultDiv.style.display = 'none';
  document.getElementById('btnGenerateScript').style.display = '';
  document.getElementById('btnGenerateScript').disabled = false;
  document.getElementById('btnRunUpload').style.display = 'none';
  document.getElementById('btnRunUpload').disabled = false;
  document.getElementById('btnUploadCancel').textContent = '取消';

  // Fetch upload config
  try {
    const res = await fetch('/api/upload-config');
    const cfg = await res.json();
    document.getElementById('uploadCountry').textContent = cfg.country;
    document.getElementById('uploadRegion').textContent = cfg.region;
    document.getElementById('uploadRecorder').textContent = cfg.recorder;
    document.getElementById('uploadCategory').textContent = cfg.category;
    document.getElementById('uploadSubcategory').textContent = cfg.subcategory;
  } catch (e) { console.error(e); }

  // Build row list sorted consistently with the main table
  rowList.innerHTML = '';
  const allChip = document.createElement('span');
  allChip.className = 'dialog-row-item all on';
  allChip.textContent = '全部本地视频';
  allChip.dataset.val = 'all';
  allChip.onclick = () => {
    if (allChip.classList.contains('on')) {
      allChip.classList.remove('on');
    } else {
      allChip.classList.add('on');
      document.querySelectorAll('#uploadRowList .dialog-row-item:not(.all)').forEach(c => c.classList.remove('on'));
    }
  };
  rowList.appendChild(allChip);

  const sortedMapping = getSortedMapping();
  sortedMapping.forEach((origIndex, displayPos) => {
    const row = tableData[origIndex];
    if (!(row.location_status || '').endsWith('_local')) return;
    const chip = document.createElement('span');
    chip.className = 'dialog-row-item';
    const label = (row.work_content_cn || row.path.split('\\').pop() || '').substring(0, 20);
    chip.textContent = '#' + (displayPos + 1) + (label ? ' ' + label : '');
    chip.dataset.val = origIndex;
    chip.onclick = () => {
      chip.classList.toggle('on');
      allChip.classList.remove('on');
    };
    rowList.appendChild(chip);
  });

  document.getElementById('uploadRowRange').value = '';
  dialog.classList.remove('hidden');
}

function onUploadRangeInput() {
  const rangeStr = document.getElementById('uploadRowRange').value.trim();
  const allChip = document.querySelector('#uploadRowList .dialog-row-item.all');
  const rowChips = document.querySelectorAll('#uploadRowList .dialog-row-item:not(.all)');

  rowChips.forEach(c => c.classList.remove('on'));
  if (allChip) allChip.classList.remove('on');

  if (!rangeStr) return;

  const sortedMapping = getSortedMapping();
  const [start, end] = parseRangeLen(rangeStr, sortedMapping.length);
  if (start < 0) return;

  const selectedOrigIndices = new Set();
  for (let pos = start; pos <= end; pos++) {
    if (pos < sortedMapping.length) selectedOrigIndices.add(sortedMapping[pos]);
  }

  rowChips.forEach(c => {
    const idx = parseInt(c.dataset.val);
    if (selectedOrigIndices.has(idx)) {
      c.classList.add('on');
    }
  });
}

function closeUploadDialog() {
  document.getElementById('uploadDialog').classList.add('hidden');
}

async function generateUploadScript() {
  const allSelected = document.querySelector('#uploadRowList .dialog-row-item.all.on');
  const resultDiv = document.getElementById('uploadResult');
  const btnGen = document.getElementById('btnGenerateScript');
  let selectedRows = [];
  let rowRange = '';

  if (!allSelected) {
    const rangeStr = document.getElementById('uploadRowRange').value.trim();
    if (rangeStr) rowRange = rangeStr;
    selectedRows = [...document.querySelectorAll('#uploadRowList .dialog-row-item:not(.all).on')]
      .map(el => parseInt(el.dataset.val));
  }

  resultDiv.style.display = 'block';
  resultDiv.innerHTML = '<span class="loading"></span>正在生成上传脚本...';
  btnGen.disabled = true;

  try {
    const deleteAfter = document.getElementById('chkDeleteAfterUpload').checked || false;
    const res = await fetch('/api/upload-generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rows: selectedRows, rowRange, selectedOnly: !allSelected, deleteAfterUpload: deleteAfter })
    });
    const data = await res.json();

    if (data.error) {
      resultDiv.innerHTML = '<span style="color:#ff4d4f;">✗ ' + data.error + '</span>';
      btnGen.disabled = false;
      return;
    }

    let html = '';
    if (data.skippedAlready && data.skippedAlready > 0) {
      const names = (data.skippedNames || []).join(', ');
      html += '<div style="color:#faad14;">⚠ 已跳过 ' + data.skippedAlready + ' 个已上传视频: ' + names + '</div>';
    }
    html += '<div style="margin-top:8px;color:#52c41a;">✓ ' + data.message + '</div>';
    html += '<div style="margin-top:8px;">脚本文件: <code style="background:#e8e8e8;padding:2px 6px;border-radius:3px;">_upload_now.cmd</code></div>';
    resultDiv.innerHTML = html;

    // Show the "开始上传" button
    document.getElementById('btnRunUpload').style.display = '';
    btnGen.textContent = '重新生成';

  } catch (e) {
    resultDiv.innerHTML = '<span style="color:#ff4d4f;">✗ 请求失败: ' + e.message + '</span>';
  } finally {
    btnGen.disabled = false;
  }
}

async function runUploadCmd() {
  const resultDiv = document.getElementById('uploadResult');
  const btnRun = document.getElementById('btnRunUpload');
  btnRun.disabled = true;
  btnRun.textContent = '启动中...';

  try {
    const res = await fetch('/api/upload-run-cmd', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    const data = await res.json();

    if (data.error) {
      alert(data.error);
      btnRun.disabled = false;
      btnRun.textContent = '开始上传';
      return;
    }

    // Append launch info to result
    resultDiv.innerHTML +=
      '<div style="margin-top:8px;color:#1677ff;">▶ 上传窗口已打开，运行结果将保存到: <code style="background:#e8e8e8;padding:2px 6px;border-radius:3px;">logs/</code> 目录</div>';
    btnRun.textContent = '已启动 ✓';

  } catch (e) {
    alert('启动失败: ' + e.message);
    btnRun.disabled = false;
    btnRun.textContent = '开始上传';
  }
}

async function doExport() {
  const selectedCols = [...document.querySelectorAll('.dialog-col-item.on')].map(el => el.dataset.key);
  if (!selectedCols.length) { alert('请选择至少一列'); return; }

  const allSelected = document.querySelector('.dialog-row-item.all.on');
  let selectedRows = [];
  let rowRange = '';
  if (!allSelected) {
    // Check if range input is non-empty
    const rangeStr = document.getElementById('exportRowRange').value.trim();
    if (rangeStr) {
      rowRange = rangeStr;
    }
    selectedRows = [...document.querySelectorAll('.dialog-row-item:not(.all).on')]
      .map(el => parseInt(el.dataset.val));
  }

  const separator = document.getElementById('exportSep').value || '.';

  try {
    const res = await fetch('/api/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ columns: selectedCols, rows: selectedRows, rowRange, separator })
    });
    if (!res.ok) { const err = await res.json(); alert(err.error || '导出失败'); return; }
    const text = await res.text();
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'export.txt';
    a.click();
    URL.revokeObjectURL(url);
    closeExportDialog();
    showStatus('导出成功');
  } catch (e) { alert('导出失败: ' + e.message); }
}
