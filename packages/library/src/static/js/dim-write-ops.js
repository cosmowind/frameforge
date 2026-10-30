// dim-write-ops.js — DIM table write operations (add, save, copy, delete)
// Extracted from index.html

function dimAddRow(name) {
  const st = dimPageState[name];
  const primary = st.schema[0];
  const tmpKey = '__new_' + Date.now() + '__';
  const newRow = { [primary]: '', _tmpKey: tmpKey };  // 写一个 _tmpKey 字段方便 find 兜底
  _uiFields(name).slice(1).forEach(fn => { newRow[fn] = ''; });  // 只初始化 UI 可见字段；schema 里的隐藏字段保留为 undefined
  st.rows.unshift(newRow);
  st.newKeys.add(tmpKey);
  dimRenderTable(name);
  const bodyEl = document.getElementById('dimBody' + _cap(name));
  if (!bodyEl) { console.error('[dimAddRow] NO bodyEl for', name); return; }
  const firstTr = bodyEl.querySelector('tr');
  if (!firstTr) { console.error('[dimAddRow] NO tr in bodyEl'); return; }
  // 同时设置 data-key 属性 和 dataset.key 属性（双重保险）
  firstTr.setAttribute('data-key', tmpKey);
  firstTr.dataset.key = tmpKey;
  firstTr.classList.add('dirty', 'dim-new');
  let focusInput = null;
  if (name === 'tasks') {
    // scene 已被 UI 屏蔽，新行的第一个可编辑输入是 product
    focusInput = firstTr.querySelector("input[data-field='product']") || firstTr.querySelector('input');
  } else {
    focusInput = firstTr.querySelector('input');
  }
  if (focusInput) focusInput.focus();
}

async function dimSaveOne(name, keyVal) {
  const st = dimPageState[name];
  const primary = st.schema[0];
  const isNew = !keyVal || keyVal.startsWith('__new_');
  let row;
  // 找到 tr 节点以读取 originalKey（连续改名场景下保留最初主键）
  const bodyEl = document.getElementById('dimBody' + _cap(name));
  let trEl = null;
  if (bodyEl) {
    const trs = bodyEl.querySelectorAll('tr');
    for (const t of trs) {
      if (t.dataset.key === keyVal || t.getAttribute('data-key') === keyVal) { trEl = t; break; }
    }
  }
  const originalKey = trEl ? (trEl.dataset.originalKey || '') : '';
  if (isNew) {
    // 优先按 _tmpKey 找
    row = st.rows.find(r => r._tmpKey === keyVal)
        || st.rows.find(r => !(r[primary] || ''));
  } else {
    row = st.rows.find(r => (r[primary] || '') === keyVal);
  }
  if (!row) {
    row = st.rows.find(r => !(r[primary] || ''));
  }
  if (!row) { showToast('未找到该行', 'warn'); return; }
  // 任务页校验：4 元组 / difficulty 不合法则拒绝保存
  if (name === 'tasks') {
    const v = _taskValidateRow(row);
    if (!v.ok) { showToast('该行无效，无法保存：' + v.reason, 'warn'); return; }
    // 新任务行：先调 /api/dim/tasks/next-id 生成 task_id（不依赖用户手填）
    if (isNew || !(row.task_id || '').trim()) {
      try {
        const nr = await fetch('/api/dim/tasks/next-id', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            product: row.product || '', task: row.task || '',
            tool: row.tool || '', process: row.process || '',
          }),
        });
        const nd = await nr.json();
        if (!nd.ok) { showToast('生成 task_id 失败: ' + (nd.reason || ''), 'warn'); return; }
        row.task_id = nd.suggested;
      } catch (e) {
        showToast('生成 task_id 异常: ' + e.message, 'warn'); return;
      }
    }
  }
  // 环境页：新行自动生成 env_id（基于 environment_description 哈希）
  if (name === 'environments') {
    if (isNew || !(row.env_id || '').trim()) {
      const desc = (row.environment_description || '').trim();
      if (!desc) { showToast('请先填写 environment_description', 'warn'); return; }
      try {
        const nr = await fetch('/api/dim/environments/next-id', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ environment_description: desc }),
        });
        const nd = await nr.json();
        if (!nd.ok) { showToast('生成 env_id 失败: ' + (nd.reason || ''), 'warn'); return; }
        row.env_id = nd.suggested;
      } catch (e) {
        showToast('生成 env_id 异常: ' + e.message, 'warn'); return;
      }
    }
  }
  // mode 选择：
  //   - 新行 → insert
  //   - 主键改名（行级 originalKey 存在且与当前 id 不同）→ upsert（让服务端走 rename 路径）
  //   - 其他更新 → update
  let mode = isNew ? 'insert' : 'update';
  let renameFromKey = '';
  if (!isNew && originalKey && originalKey !== (row[primary] || '')) {
    mode = 'upsert';
    renameFromKey = originalKey;
  }
  let url = '/api/dim/' + name;
  if (renameFromKey) {
    url += '?original_key=' + encodeURIComponent(renameFromKey);
  }
  try {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ row, mode }),
    });
    const data = await r.json();
    if (!r.ok) {
      showToast('保存失败: ' + (data.error || r.status) + (data.errors ? ' / ' + data.errors.join('; ') : ''), 'warn');
      return;
    }
    // 清除 dirty/newKeys：包括旧 key 和当前 key（因为可能已变更）
    st.dirty.delete(keyVal);
    st.dirty.delete(originalKey);
    st.newKeys.delete(keyVal);
    // 用服务器返回值更新本地行（服务器可能补充了 process_en / env_id 等字段）
    if (data.row) {
      const serverRow = data.row;
      // 用 primary key 找到本地对应行并同步字段
      const localRow = st.rows.find(r => (r[primary] || '') === (serverRow[primary] || ''));
      if (localRow) {
        for (const fn of st.schema) {
          if (serverRow[fn] !== undefined) localRow[fn] = serverRow[fn];
        }
      }
    }
    // 用真实 key 替换（新行场景）
    if (isNew && data.row && data.row[primary]) {
      const realKey = data.row[primary];
      row[primary] = realKey;
    }
    // 改名成功：更新 dirty 集合使用新 key，并清掉 tr.dataset.originalKey（已对齐服务器）
    if (data.action === 'renamed' && row[primary]) {
      const newKey = row[primary];
      st.dirty.delete(newKey);  // 防止前一行删除
      st.dirty.add(newKey);
      if (trEl) {
        trEl.removeAttribute('data-original-key');
        delete trEl.dataset.originalKey;
      }
    }
    dimRenderTable(name);
    showToast(`已保存（${data.action}）`, 'success');
    return 'ok';
  } catch (e) {
    showToast('保存异常: ' + e.message, 'warn');
    return 'fail';
  }
}

async function dimSaveDirtyRows(name) {
  const st = dimPageState[name];
  // 快照（避免边迭代边改：dimSaveOne 内部 rename 会迁移 dirty set）
  const dirtyKeys = [...st.dirty];
  const newKeys = [...st.newKeys];
  if (dirtyKeys.length === 0) { showToast('没有待保存的行', 'warn'); return; }
  let ok = 0, fail = 0;
  for (const k of dirtyKeys) {
    const r = await dimSaveOne(name, k);
    if (r === 'ok') ok++;
    else fail++;
  }
  showToast(`保存完成：${ok} 成功 / ${fail} 失败`, fail ? 'warn' : 'success');
  // 自动排序：批量保存后重新排序
  if (name === 'tasks' && _tasksAutoSort) {
    _applyTasksSort();
    _persistTasksOrder();
  }
  // 重新渲染（保证 dirty/newKeys 集合同步）
  dimRenderTable(name);
}

function dimCopyRow(name, keyVal) {
  const st = dimPageState[name];
  if (!st) return;
  const primary = st.schema[0];
  const src = st.rows.find(r => (r[primary] || '') === keyVal);
  if (!src) { showToast('未找到源行', 'warn'); return; }
  // 深拷贝，清空 task_id（主键）及 产品/任务/工具/工序
  const copy = { ...src };
  copy[primary] = '';
  copy['product'] = '';
  copy['task'] = '';
  copy['tool'] = '';
  copy['process'] = '';
  // 为新行生成临时 key
  const tmpKey = '__new_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6);
  copy._tmpKey = tmpKey;
  // 插入到源行的下一行
  const srcIdx = st.rows.indexOf(src);
  st.rows.splice(srcIdx + 1, 0, copy);
  st.newKeys.add(tmpKey);
  st.dirty.add(tmpKey);
  dimRenderTable(name);
  showToast('已拷贝（可编辑后保存）', 'success');
}

// ── 📋 复制维表字段到剪贴板（纯前端，无网络请求） ──
async function dimCopyFieldToClipboard(name, keyVal, sourceCol, btn) {
  const st = dimPageState[name];
  const cacheRows = dimCache[name] || [];
  const primary = st && st.schema && st.schema[0];
  const rowsToSearch = (st && st.rows && st.rows.length > 0) ? st.rows : cacheRows;
  const row = primary ? rowsToSearch.find(r => (r[primary] || '') === keyVal) : null;
  if (!row) { showToast('未找到源行', 'warn'); return; }
  const value = (row[sourceCol] || '').trim();
  if (!value) { showToast(`该行 ${sourceCol} 为空，无法复制`, 'warn'); return; }
  try {
    await navigator.clipboard.writeText(value);
  } catch (e) {
    // Fallback for non-HTTPS or blocked clipboard
    const ta = document.createElement('textarea');
    ta.value = value;
    ta.style.position = 'fixed'; ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  }
  if (btn) {
    const orig = btn.innerHTML;
    btn.innerHTML = '✓';
    btn.style.color = '#52c41a';
    btn.style.borderColor = '#52c41a';
    setTimeout(() => { btn.innerHTML = orig; btn.style.color = '#389e0d'; btn.style.borderColor = '#b7eb8f'; }, 1500);
  }
  showToast(`📋 已复制: "${value}"`, 'success');
}
