// task-wizard.js — Task wizard and batch task creation
// Extracted from index.html

function openTaskWizard() {
  // 打开 modal + 绑定 4 个字段 input 事件实时调用 next-id
  const overlay = document.getElementById('taskWizardOverlay');
  overlay.classList.remove('hidden');
  ['tw_product','tw_task','tw_tool','tw_process','tw_difficulty','tw_notes'].forEach(id => {
    const el = document.getElementById(id);
    if (!el._bound) {
      el.addEventListener('input', taskWizardPreview);
      el.addEventListener('change', taskWizardPreview);
      el._bound = true;
    }
    if (el.tagName === 'INPUT') el.value = '';
  });
  document.getElementById('tw_difficulty').value = '';
  document.getElementById('tw_result').textContent = '填写 4 个字段后预览 task_id →';
  document.getElementById('tw_result').className = 'wizard-result';
}

function closeTaskWizard() {
  document.getElementById('taskWizardOverlay').classList.add('hidden');
}

/* ============================================================ */
/* === BATCH TASK WIZARD (paste TSV / | -separated)            === */
/* ============================================================ */

function _validateBatchRow(fields) {
  // fields: [product, task, tool, process, difficulty, notes]
  // difficulty 不再校验：前端下拉是中文（简单/中等/困难），后端 quota 仍按 easy/medium/hard 走
  const [product, task, tool, process, difficulty, notes] = fields;
  if (!product || !task || !tool || !process) {
    return { ok: false, reason: '缺 4 元组' };
  }
  return { ok: true };
}

function _parseBatchText(text) {
  const out = [];
  const lines = text.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i].trim();
    if (!raw || raw.startsWith('#') || raw.startsWith('//')) continue;
    const fields = raw.split('|').map(s => s.trim());
    // 允许 4 元组（不带 difficulty/notes）或 6 元组
    let product, task, tool, process, difficulty, notes;
    if (fields.length >= 6) {
      [product, task, tool, process, difficulty, notes] = fields;
    } else if (fields.length >= 4) {
      [product, task, tool, process] = fields;
      difficulty = ''; notes = '';
    } else {
      out.push({ line: i + 1, fields, ok: false, reason: `只 ${fields.length} 列（最少 4）` });
      continue;
    }
    const v = _validateBatchRow(fields);
    out.push({ line: i + 1, fields: [product, task, tool, process, difficulty, notes], ...v });
  }
  return out;
}

function openBatchTaskWizard() {
  document.getElementById('batchTaskOverlay').classList.remove('hidden');
  document.getElementById('btw_text').value = '';
  document.getElementById('btw_result').innerHTML = '粘贴数据后点「预览」查看每行校验状态';
  document.getElementById('btw_result').className = 'wizard-result';
}

function closeBatchTaskWizard() {
  document.getElementById('batchTaskOverlay').classList.add('hidden');
}

let _btwRows = [];
async function batchTaskPreview() {
  const text = document.getElementById('btw_text').value;
  const rows = _parseBatchText(text);
  _btwRows = rows;
  const result = document.getElementById('btw_result');
  if (rows.length === 0) {
    result.innerHTML = '无有效行';
    result.className = 'wizard-result err';
    return;
  }
  // Try to fetch suggested task_ids for valid rows
  for (const r of rows) {
    if (!r.ok) continue;
    try {
      const resp = await fetch('/api/dim/tasks/next-id', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          product: r.fields[0], task: r.fields[1],
          tool: r.fields[2], process: r.fields[3],
        }),
      });
      const data = await resp.json();
      r.taskId = data.ok ? data.suggested : null;
      if (!data.ok) { r.ok = false; r.reason = data.reason; }
    } catch (e) {
      r.taskId = null;
    }
  }
  // Render
  const okCount = rows.filter(r => r.ok).length;
  const html = rows.map(r => {
    const icon = r.ok ? '✅' : '❌';
    const tid = r.taskId ? `<code style="color:#1677ff">${r.taskId}</code>` : '';
    const reason = r.reason ? ` <span style="color:#cf1322">(${r.reason})</span>` : '';
    const [product, task, tool, process, difficulty, notes] = r.fields;
    const noteSuffix = notes ? ` <span style="color:#888;">(备注: ${esc(notes)})</span>` : '';
    return `<div style="font-size:11px;padding:2px 0;">${icon} 行${r.line}: ${esc(product)} / ${esc(task)} / ${esc(tool)} / ${esc(process)} → ${tid}${reason}${noteSuffix}</div>`;
  }).join('');
  result.innerHTML = `<div style="margin-bottom:6px;color:${okCount === rows.length ? '#389e0d' : '#cf1322'}">${okCount} / ${rows.length} 行校验通过</div>${html}`;
  result.className = `wizard-result ${okCount === rows.length ? 'ok' : 'err'}`;
}
