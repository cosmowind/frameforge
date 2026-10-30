// auto-upload.js — Batch auto-upload polling
// Extracted from index.html

async function startAutoUpload() {
  const rowIndex = _utRowIndex;
  if (rowIndex < 0) { alert('没有选中的视频'); return; }

  const btn = document.getElementById('btnUploadSingle');
  const videoName = document.getElementById('utVideoName').textContent || ('行 ' + rowIndex);
  btn.disabled = true;
  btn.textContent = '启动中...';

  // 显示进度条
  const progDiv = document.getElementById('uploadProgress');
  const progBar = document.getElementById('uploadProgressBar');
  const progLabel = document.getElementById('uploadProgressLabel');
  const progCount = document.getElementById('uploadProgressCount');
  const progMsg = document.getElementById('uploadProgressMsg');

  progDiv.style.display = 'block';
  progLabel.textContent = '准备上传: ' + videoName;
  progCount.textContent = '';
  progBar.style.width = '0%';
  progMsg.textContent = '';

  try {
    const runRes = await fetch('/api/auto-upload-start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ row_index: rowIndex, deleteAfterUpload: _utDeleteAfterUpload })
    });
    const runData = await runRes.json();
    if (!runData.ok) {
      alert('启动失败: ' + (runData.error || '未知错误'));
      btn.disabled = false;
      btn.textContent = '📤 上传本视频';
      progDiv.style.display = 'none';
      return;
    }

    showStatus('已启动上传: ' + videoName + (_utDeleteAfterUpload ? ' (传完即删)' : ''));

    // 轮询进度（最长 20 分钟）
    const deadline = Date.now() + 20 * 60 * 1000;
    while (Date.now() < deadline) {
      await _sleepMs(2000);
      try {
        const pRes = await fetch('/api/auto-upload-progress');
        const p = await pRes.json();

        if (p.total > 0) {
          const done = p.current || 0;
          const pct = Math.round(done / p.total * 100);
          progBar.style.width = pct + '%';
          progCount.textContent = done + '/' + p.total;
        }
        if (p.message) {
          progMsg.textContent = p.message;
          progLabel.textContent = p.message;
        }
        if (p.status === 'done') {
          progBar.style.width = '100%';
          progCount.textContent = '1/1';
          if (p.fail > 0 && p.success === 0) {
            // 全部失败
            progLabel.textContent = '❌ 上传失败: ' + videoName;
            progMsg.textContent = p.message || '未知错误';
            showStatus('上传失败: ' + (p.message || ''));
            btn.textContent = '❌ 失败';
          } else if (p.success > 0 && p.fail > 0) {
            // 部分成功
            progLabel.textContent = '⚠️ 部分完成: ' + videoName;
            progMsg.textContent = p.message || '';
            showStatus(p.success + ' 成功, ' + p.fail + ' 失败');
            btn.textContent = '⚠️ 部分完成';
          } else {
            // 全部成功
            progLabel.textContent = '✅ 上传完成: ' + videoName;
            progMsg.textContent = '';
            showStatus('上传完成! ' + videoName);
            btn.textContent = '✅ 已完成';
          }
          break;
        }
        if (p.status === 'error') {
          progLabel.textContent = '❌ 上传出错';
          progMsg.textContent = p.message || '未知错误';
          showStatus('上传出错: ' + (p.message || ''));
          btn.textContent = '❌ 错误';
          break;
        }
      } catch (e) { /* 轮询失败，继续 */ }
    }
  } catch (e) {
    alert('启动失败: ' + e.message);
    btn.disabled = false;
    btn.textContent = '📤 上传本视频';
    progDiv.style.display = 'none';
  }
}

/* ── 批量上传选中视频 ── */

/* 一键全选所有可上传的视频（未上传 + 录入员/任务/环境 已填），
   然后直接打开批量上传对话框 */
function selectAllReadyAndOpen() {
  const checks = document.querySelectorAll('.row-check');
  let selected = 0, skippedUploaded = 0, skippedIncomplete = 0;
  checks.forEach(cb => {
    if (cb.dataset.uploaded === 'Yes') {
      cb.checked = false;
      skippedUploaded++;
      return;
    }
    const cid = (cb.dataset.recorderId || '').trim();
    const tid = (cb.dataset.taskId || '').trim();
    const eid = (cb.dataset.envId || '').trim();
    if (!cid || !tid || !eid) {
      cb.checked = false;
      skippedIncomplete++;
      return;
    }
    cb.checked = true;
    selected++;
  });
  // 触发一次 change 让表格刷新视觉
  document.querySelectorAll('.row-check').forEach(cb => {
    cb.dispatchEvent(new Event('change', { bubbles: true }));
  });
  showStatus(`已自动勾选 ${selected} 个可上传视频${skippedIncomplete ? `（${skippedIncomplete} 个参数不完整已跳过）` : ''}${skippedUploaded ? `（${skippedUploaded} 个已上传已跳过）` : ''}`);
  if (selected === 0) {
    alert('没有可上传的视频。请确认：\n1) 视频未标记为已上传\n2) 已填写 录入员ID / Task ID / 环境ID');
    return;
  }
  openUploadSelectedDialog();
}

function openUploadSelectedDialog() {
  const checked = document.querySelectorAll('.row-check:checked');
  if (!checked.length) {
    alert('请先勾选要上传的视频');
    return;
  }
  const count = checked.length;

  // 检查哪些已经上传
  const skipped = [];
  const willUpload = [];
  checked.forEach(cb => {
    const uploaded = cb.dataset.uploaded === 'Yes';
    const row = cb.closest('tr');
    const nameCell = row ? row.querySelector('.path-cell') : null;
    const name = nameCell ? nameCell.textContent.trim().split(/[\\/]/).pop() : `行${parseInt(cb.dataset.index)+1}`;
    if (uploaded) {
      skipped.push(name);
    } else {
      willUpload.push(cb);
    }
  });

  document.getElementById('uploadSelectedCount').textContent = willUpload.length;

  const skippedEl = document.getElementById('uploadSelectedSkipped');
  const skippedListEl = document.getElementById('uploadSelectedSkippedList');
  if (skipped.length > 0) {
    skippedEl.style.display = '';
    skippedEl.textContent = `（已跳过 ${skipped.length} 个已上传视频）`;
    skippedListEl.style.display = '';
    skippedListEl.innerHTML = '<b>⏭️ 以下视频已标记为上传完成，将被跳过：</b><br>' +
      skipped.map(s => `&nbsp;&nbsp;· ${s}`).join('<br>');
  } else {
    skippedEl.style.display = 'none';
    skippedListEl.style.display = 'none';
  }

  document.getElementById('chkDeleteOriginal').checked = false;
  document.getElementById('chkDeletePreview').checked = false;
  document.getElementById('uploadSelectedDialog').classList.remove('hidden');
}

function closeUploadSelectedDialog() {
  document.getElementById('uploadSelectedDialog').classList.add('hidden');
}

function closeBatchUploadDialog() {
  document.getElementById('batchUploadProgressDialog').classList.add('hidden');
}

async function runUploadSelected() {
  const checked = document.querySelectorAll('.row-check:checked');
  if (!checked.length) {
    alert('没有选中的视频');
    return;
  }

  // ★ 校验选中视频的关键字段是否已填写
  const missingRecorder = [];
  const missingTask = [];
  const missingEnv = [];
  const missingAll = [];  // 三项全空
  checked.forEach(cb => {
    if (cb.dataset.uploaded === 'Yes') return; // 跳过已上传的
    const cid = (cb.dataset.recorderId || '').trim();
    const tid = (cb.dataset.taskId || '').trim();
    const eid = (cb.dataset.envId || '').trim();
    const idx = parseInt(cb.dataset.index) + 1; // 1-based for display
    if (!cid && !tid && !eid) {
      missingAll.push(idx);
    } else {
      if (!cid) missingRecorder.push(idx);
      if (!tid) missingTask.push(idx);
      if (!eid) missingEnv.push(idx);
    }
  });
  if (missingAll.length || missingRecorder.length || missingTask.length || missingEnv.length) {
    let msg = '以下视频的上传参数不完整，请先填写：\n\n';
    if (missingAll.length) {
      msg += `· 行 ${missingAll.join(', ')}：全部未填（recorder / task / env）\n`;
    }
    if (missingRecorder.length) {
      msg += `· 行 ${missingRecorder.join(', ')}：缺少 录制员ID\n`;
    }
    if (missingTask.length) {
      msg += `· 行 ${missingTask.join(', ')}：缺少 Task ID\n`;
    }
    if (missingEnv.length) {
      msg += `· 行 ${missingEnv.join(', ')}：缺少 环境ID\n`;
    }
    msg += '\n请双击对应行填写后重试。';
    alert(msg);
    return;
  }

  const rowIndices = Array.from(checked).map(cb => parseInt(cb.dataset.index));
  const deleteOriginal = document.getElementById('chkDeleteOriginal').checked;
  const deletePreview = document.getElementById('chkDeletePreview').checked;
  const deleteAfterUpload = deleteOriginal || deletePreview;
  const keepThumbs = deletePreview;  // 勾选"删除预览"时保留封面

  const btn = document.getElementById('btnRunUploadSelected');
  btn.disabled = true;
  btn.textContent = '启动中...';

  try {
    const res = await fetch('/api/auto-upload-start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ row_indices: rowIndices, deleteAfterUpload, keepThumbs })
    });
    const data = await res.json();
    if (!data.ok) {
      let errMsg = (data.error || '未知错误');
      if (data.details && data.details.length) {
        errMsg += '\n\n' + data.details.join('\n');
        if (data.hint) errMsg += '\n\n' + data.hint;
      }
      alert('启动失败: ' + errMsg);
      btn.disabled = false;
      btn.textContent = '开始上传';
      return;
    }
    const total = data.count || rowIndices.length;
    const skipped = data.skipped ? data.skipped.length : 0;
    const skippedMsg = skipped > 0 ? '（已跳过 ' + skipped + ' 个已上传）' : '';
    showStatus('已启动批量上传: ' + total + ' 个视频 ' + skippedMsg);
    closeUploadSelectedDialog();

    // 打开批量进度面板
    const batchDialog = document.getElementById('batchUploadProgressDialog');
    const batchProgBar = document.getElementById('batchProgBar');
    const batchProgLabel = document.getElementById('batchProgLabel');
    const batchProgCount = document.getElementById('batchProgCount');
    const batchProgMsg = document.getElementById('batchProgMsg');
    const batchTerminal = document.getElementById('batchTerminal');
    const btnClose = document.getElementById('btnBatchUploadClose');
    batchDialog.classList.remove('hidden');
    batchTerminal.innerHTML = '';
    batchProgBar.style.width = '0%';
    batchProgLabel.textContent = '正在启动...';
    batchProgCount.textContent = '0/' + total;
    batchProgMsg.textContent = '';
    btnClose.textContent = '关闭';
    btnClose.onclick = () => { batchDialog.classList.add('hidden'); };

    // 追加日志行（带时间戳+颜色）
    const _appendLog = (text, type) => {
      const ts = new Date().toLocaleTimeString('zh-CN', { hour12: false });
      const span = document.createElement('div');
      let color = '#c9d1d9';
      if (text.includes('✓')) color = '#3fb950';
      else if (text.includes('✗') || text.includes('失败') || text.includes('error')) color = '#f85149';
      else if (text.includes('⚠') || text.includes('超时')) color = '#d29922';
      else if (text.includes('inflight')) color = '#79c0ff';
      span.style.color = color;
      span.textContent = ts + ' ' + text;
      batchTerminal.appendChild(span);
      batchTerminal.scrollTop = batchTerminal.scrollHeight;
    };

    _appendLog('开始批量上传 ' + total + ' 个视频 ' + skippedMsg, 'start');

    // 轮询进度
    const deadline = Date.now() + 120 * 60 * 1000;  // 2小时超时
    let lastCurrent = 0;
    const _pollSelected = async () => {
      while (Date.now() < deadline) {
        await new Promise(r => setTimeout(r, 3000));
        try {
          const pRes = await fetch('/api/auto-upload-progress');
          const p = await pRes.json();

          // 更新进度条
          if (p.total > 0) {
            const pct = Math.round((p.current || 0) / p.total * 100);
            batchProgBar.style.width = pct + '%';
            batchProgCount.textContent = (p.current || 0) + '/' + p.total;
          }

          // 追加新日志
          if (p.message) {
            _appendLog(p.message, 'progress');
          }
          if (p.message && p.message.includes('已填:')) {
            batchProgLabel.textContent = '填表中: ' + (p.message.split('已填:')[1] || '').trim();
          } else if (p.message && p.message.includes('HMD')) {
            batchProgLabel.textContent = '上传: ' + p.message;
          }

          if (p.status === 'done') {
            batchProgBar.style.width = '100%';
            if (p.fail > 0 && p.success === 0) {
              batchProgLabel.textContent = '❌ 全部失败';
              batchProgMsg.textContent = p.message || '未知错误';
              _appendLog('❌ 批量上传失败: ' + (p.message || ''), 'error');
            } else if (p.success > 0 && p.fail > 0) {
              batchProgLabel.textContent = '⚠️ 部分完成: ' + p.success + ' 成功, ' + p.fail + ' 失败';
              batchProgMsg.textContent = p.success + ' 成功, ' + p.fail + ' 失败';
              _appendLog('⚠️ 部分完成: ' + p.success + ' 成功, ' + p.fail + ' 失败', 'warn');
            } else {
              batchProgLabel.textContent = '✅ 全部上传完成: ' + p.success + ' 个';
              batchProgMsg.textContent = '';
              _appendLog('✅ 批量上传完成: ' + p.success + ' 个视频', 'success');
            }
            showStatus('✅ 批量上传完成: ' + p.success + ' 成功, ' + p.fail + ' 失败');
            btnClose.textContent = '关闭并刷新';
            btnClose.onclick = () => { batchDialog.classList.add('hidden'); location.reload(); };
            return;
          }
          if (p.status === 'error') {
            batchProgLabel.textContent = '❌ 出错';
            batchProgMsg.textContent = p.message || '';
            _appendLog('❌ 批量上传出错: ' + (p.message || ''), 'error');
            btnClose.textContent = '关闭';
            return;
          }
        } catch (e) {
          _appendLog('⚠ 轮询异常: ' + e.message, 'warn');
        }
      }
      _appendLog('⚠ 批量上传超时', 'warn');
      batchProgLabel.textContent = '⚠️ 上传超时';
    };
    _pollSelected();
  } catch (e) {
    alert('启动失败: ' + e.message);
    btn.disabled = false;
    btn.textContent = '开始上传';
  }
}
