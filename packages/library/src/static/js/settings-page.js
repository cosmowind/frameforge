// settings-page.js — Settings page logic
// Extracted from index.html

async function settingsLoad() {
  const status = document.getElementById('settingsStatus');
  if (status) status.textContent = '加载中…';
  try {
    const r = await fetch('/api/estimate');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const data = await r.json();
    document.getElementById('settingsCurrentRatio').value = data.size_mb_per_min || '';
    document.getElementById('settingsCurrentSource').value = data.source || '';
    document.getElementById('settingsUserRatio').value = data.saved_value != null ? data.saved_value : '';
    // Samples
    const samplesEl = document.getElementById('settingsSamples');
    if (samplesEl) {
      const samples = (data.samples || []).slice(0, 10);
      if (samples.length === 0) {
        samplesEl.textContent = '（尚无已处理 HMD session 可参考）';
      } else {
        samplesEl.innerHTML = samples.map(s =>
          `<div>${esc(s.path.split(/[\\/]/).pop())} · size=${s.size_mb} MB · dur=${fmtDur(s.duration_sec)} · ratio=${s.size_mb_per_min} MB/min</div>`
        ).join('');
      }
    }
    // Scan dir
    try {
      const cr = await fetch('/api/config');
      const cfg = await cr.json();
      document.getElementById('settingsScanDir').value = cfg.scanDirectory || '';
    } catch (e) { /* ignore */ }
    if (status) status.textContent = '已加载';
  } catch (e) {
    if (status) status.textContent = '加载失败: ' + e.message;
  }
}

async function settingsSaveRatio() {
  const v = document.getElementById('settingsUserRatio').value.trim();
  const body = {};
  if (v) {
    const n = parseFloat(v);
    if (!(n > 0)) { showToast('请输入正数', 'warn'); return; }
    body.size_mb_per_min = n;
  } else {
    body.reset = true;
  }
  const r = await fetch('/api/estimate', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (!r.ok) { showToast('保存失败', 'warn'); return; }
  showToast('已保存', 'success');
  // settingsLoad() 已经会拉 /api/estimate 刷新设置页字段，无需再调 loadEstimateRatio()
  await settingsLoad();
  // 触发视频表/画廊重新渲染（让新比例立即生效）
  renderTable();
  if (galleryState.loaded) _galleryRender();
}

function settingsResetRatio() {
  document.getElementById('settingsUserRatio').value = '';
  settingsSaveRatio();
}

async function settingsSaveScanDir() {
  const v = document.getElementById('settingsScanDir').value.trim();
  const r = await fetch('/api/config', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scanDirectory: v }),
  });
  if (!r.ok) { showToast('保存失败', 'warn'); return; }
  scanDirectory = v;
  showToast('已保存扫描目录', 'success');
}

