// statistics-page.js — Statistics page rendering
// Extracted from index.html

async function loadStatistics() {
  const status = document.getElementById('statisticsStatus');
  const wrap = document.getElementById('statisticsWrap');
  if (status) status.textContent = '加载中…';
  try {
    const r = await fetch('/api/statistics');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const data = await r.json();
    renderStatistics(data, wrap);
    if (status) status.textContent = `已加载 · 总时长 ${data.total_hours}h`;
  } catch (e) {
    if (status) status.textContent = '加载失败: ' + e.message;
    if (wrap) wrap.innerHTML = `<div style="text-align:center;color:#cf1322;padding:40px;">加载失败: ${e.message}</div>`;
  }
}

function renderStatistics(data, wrap) {
  if (!wrap) return;

  // ── Helper: format seconds ──
  const fmtH = (sec) => (sec / 3600).toFixed(1) + 'h';
  const fmtM = (sec) => (sec / 60).toFixed(1) + 'min';

  // ── Summary cards ──
  let html = `<div class="stats-summary">
    <div class="stats-card"><div class="val">${data.total_hours}h</div><div class="label">总时长</div></div>
    <div class="stats-card"><div class="val">${data.total_min}min</div><div class="label">总分钟</div></div>
  </div>`;

  // ── 1. 环境统计 ──
  const es = data.env_stats;
  html += `<div class="stats-section"><h3>🌍 环境总时长</h3>`;
  html += `<div class="stats-summary">
    <div class="stats-card ${es.max_exceeded ? 'over' : ''}"><div class="val">${es.max_pct}%</div><div class="label">最大单环境占比 (限 ≤20%)</div></div>
    <div class="stats-card ${es.top5_exceeded ? 'over' : (es.top5_pct > 50 ? 'warn' : '')}"><div class="val">${es.top5_pct}%</div><div class="label">Top 5 环境占比 (限 ≤60%)</div></div>
  </div>`;
  html += renderStatsTable(
    ['环境', '时长(h)', '时长(min)', '占比', '限制状态'],
    es.data.map(e => [
      esc(e.env_desc),
      (e.used_sec / 3600).toFixed(1),
      e.used_min,
      e.percent + '%',
      e.percent > 20 ? '<span style="color:#cf1322;font-weight:700;">⚠ 超限</span>' : '<span style="color:#389e0d;">✓</span>'
    ]),
    (row) => parseFloat(row[3]) > 20 ? 'over' : (parseFloat(row[3]) > 15 ? 'warn' : '')
  );

  // ── 2. 任务统计 ──
  const ts = data.task_stats;
  const diffLimits = { easy: 1.5, medium: 4.0, hard: 6.0 };
  html += `<div class="stats-section"><h3>📝 任务总时长</h3>`;
  html += renderStatsTable(
    ['任务', '难度', '已用(min)', '配额(min)', '配额状态', '占比', '占比限制'],
    ts.data.map(t => {
      const limit = diffLimits[t.difficulty] || 999;
      const over = t.percent > limit;
      const quota = t.quota_min;
      const quotaOver = quota != null && t.used_min > quota;
      const quotaPct = quota != null ? Math.min(Math.round(t.used_min / quota * 100), 999) : 0;
      return [
        `<span title="${esc(t.product || '')} / ${esc(t.task_id)}">${esc(t.process || t.task_id)}</span>`,
        `<span style="color:${t.difficulty==='hard'?'#cf1322':t.difficulty==='medium'?'#faad14':'#389e0d'}">${t.difficulty}</span>`,
        t.used_min,
        quota != null ? quota : '-',
        quota != null
          ? (quotaOver
              ? `<span style="color:#cf1322;font-weight:700;">⚠ ${t.used_min}/${quota} (${quotaPct}%)</span>`
              : `<span style="color:#389e0d;">${t.used_min}/${quota} (${quotaPct}%)</span>`)
          : '<span style="color:#bbb;">-</span>',
        t.percent + '%',
        over ? `<span style="color:#cf1322;font-weight:700;">超 ${t.percent}% > ${limit}%</span>` : `<span style="color:#389e0d;">≤${limit}%</span>`
      ];
    }),
    (row) => {
      const pct = parseFloat(row[5]);
      const diff = row[1].match(/easy|medium|hard/)?.[0];
      const limit = diffLimits[diff] || 999;
      return pct > limit || row[4].includes('⚠') ? 'over' : '';
    }
  );

  // ── 3. 任务×环境统计 ──
  const te = data.task_env_stats;
  html += `<div class="stats-section"><h3>🔗 任务 × 环境总时长</h3>`;
  html += renderStatsTable(
    ['任务', '环境', '难度', '已用(h)', '上限(h)', '状态'],
    te.data.map(row => [
      `<span title="${esc(row.task_id)}">${esc(row.process || row.task_id)}</span>`,
      esc(row.env_desc),
      row.difficulty,
      row.used_hours,
      row.limit_hours != null ? row.limit_hours : '-',
      row.exceeded ? '<span style="color:#cf1322;font-weight:700;">⚠ 超限</span>' : '<span style="color:#389e0d;">✓</span>'
    ]),
    (row) => row[5].includes('超限') ? 'over' : ''
  );

  // ── 4. 操作员×任务×环境统计 ──
  const ote = data.operator_task_env_stats;
  html += `<div class="stats-section"><h3>👤 操作员 × 任务 × 环境</h3>`;
  html += renderStatsTable(
    ['操作员', '任务', '环境', '难度', '已用(h)', '上限(h)', '状态'],
    ote.data.map(row => [
      esc(row.recorder_name),
      `<span title="${esc(row.task_id)}">${esc(row.process || row.task_id)}</span>`,
      esc(row.env_desc),
      row.difficulty,
      row.used_hours,
      row.limit_hours != null ? row.limit_hours : '-',
      row.exceeded ? '<span style="color:#cf1322;font-weight:700;">⚠ 超限</span>' : '<span style="color:#389e0d;">✓</span>'
    ]),
    (row) => row[6].includes('超限') ? 'over' : ''
  );

  wrap.innerHTML = html;
}

function renderStatsTable(headers, rows, rowClassFn) {
  let h = '<table class="stats-table"><thead><tr>';
  headers.forEach(hdr => { h += `<th>${hdr}</th>`; });
  h += '</tr></thead><tbody>';
  rows.forEach(row => {
    const cls = rowClassFn ? rowClassFn(row) : '';
    h += `<tr class="${cls}">`;
    row.forEach(cell => { h += `<td>${cell}</td>`; });
    h += '</tr>';
  });
  h += '</tbody></table>';
  return h;
}

/* ============================================================ */
/* === SETTINGS PAGE                                          === */
/* ============================================================ */
