// 端到端验证 pickCanonicalEnglish 的 4 条规则 + handleCellEdit
// 直接复刻 templates/index.html 中的实现，跑 Case A–J

let tableData = [];
let toastMessages = [];
function showToast(msg, kind) { toastMessages.push({msg, kind}); }

// === 复制自 templates/index.html 的实现（保持一致）===
function pickCanonicalEnglish(cn, excludeIndex = -1) {
  cn = (cn || '').trim();
  if (!cn) return null;

  const candidates = tableData
    .map((r, i) => ({ r, i }))
    .filter(({ r, i }) => (r.work_content_cn || '').trim() === cn && i !== excludeIndex);

  if (candidates.length === 0) {
    if (excludeIndex >= 0 && tableData[excludeIndex]) {
      return (tableData[excludeIndex].work_content_en || '').trim() || null;
    }
    return null;
  }
  if (candidates.length === 1) {
    return (candidates[0].r.work_content_en || '').trim() || null;
  }

  const counts = {};
  for (const { r } of candidates) {
    const en = (r.work_content_en || '').trim();
    if (!en) continue;
    counts[en] = (counts[en] || 0) + 1;
  }
  const keys = Object.keys(counts);
  if (keys.length === 0) return null;

  const maxCount = Math.max(...keys.map(k => counts[k]));
  const top = keys.filter(k => counts[k] === maxCount);
  if (top.length === 1) return top[0];

  showToast(
    `中文 "${cn}" 对应 ${top.length} 种并列最多的英文，建议加 -1/-2/-3 后缀`,
    'warn'
  );
  return top[Math.floor(Math.random() * top.length)];
}

function handleCellEditLive(rowIndex, key, newValue) {
  if (!tableData[rowIndex]) return;
  tableData[rowIndex][key] = newValue;

  if (key === 'work_content_cn') {
    const canonical = pickCanonicalEnglish(newValue, rowIndex);
    if (canonical && !tableData[rowIndex].work_content_en) {
      tableData[rowIndex].work_content_en = canonical;
    }
  }
  // 实时：绝不弹框
  return { prompt: false };
}

function handleCellEditCommit(rowIndex, key, newValue) {
  if (!tableData[rowIndex]) return { prompt: false };
  if (key !== 'work_content_en') return { prompt: false };
  const cn = (tableData[rowIndex].work_content_cn || '').trim();
  if (!cn) return { prompt: false };
  const sameCount = tableData.filter(
    r => (r.work_content_cn || '').trim() === cn).length;
  if (sameCount > 1) return { prompt: true, sameCount };
  return { prompt: false };
}

// === 测试用例 ===
let pass = 0, fail = 0;
function test(name, cond, info='') {
  if (cond) { pass++; console.log(`  ✅ ${name}${info?'  — '+info:''}`); }
  else      { fail++; console.log(`  ❌ ${name}${info?'  — '+info:''}`); }
}

console.log('=== Case A: 新记录（无同中文）→ 不自动补 ===');
tableData = [{work_content_cn: '', work_content_en: ''}];
toastMessages = [];
let r = handleCellEditLive(0, 'work_content_cn', '测试');
test('Case A: 不补全', tableData[0].work_content_en === '');
test('Case A: 实时不弹框', r.prompt === false);

console.log('\n=== Case B: 已有 1 条，新建第 2 条同中文 → 自动补 ===');
tableData = [
  {work_content_cn: '测试', work_content_en: 'test'},
  {work_content_cn: '',     work_content_en: ''},
];
r = handleCellEditLive(1, 'work_content_cn', '测试');
test('Case B: 自动补全为 test', tableData[1].work_content_en === 'test');

console.log('\n=== Case C: 编辑英文（提交/change 事件），2 条同中文 → 弹框 ===');
tableData = [
  {work_content_cn: '测试', work_content_en: 'test'},
  {work_content_cn: '测试', work_content_en: 'test'},
];
r = handleCellEditLive(0, 'work_content_en', 'foo');  // input: 实时
test('Case C-input: 实时不弹框', r.prompt === false);
r = handleCellEditCommit(0, 'work_content_en', 'foo'); // change: 提交
test('Case C-commit: 弹框', r.prompt === true && r.sameCount === 2);

console.log('\n=== Case D: 1 条记录提交英文 → 不弹框 ===');
tableData = [{work_content_cn: '唯一', work_content_en: 'only'}];
r = handleCellEditCommit(0, 'work_content_en', 'new');
test('Case D-commit: 不弹框', r.prompt === false);

console.log('\n=== Case E: 中文到新值 → 不补全 ===');
tableData = [
  {work_content_cn: 'A', work_content_en: 'a'},
  {work_content_cn: 'B', work_content_en: 'b'},
];
r = handleCellEditLive(1, 'work_content_cn', 'X');
test('Case E: 不补全', tableData[1].work_content_en === 'b');

console.log('\n=== Case F (新): input 事件期间连续打字 → 不应多次弹框 ===');
tableData = [
  {work_content_cn: '多次', work_content_en: 'multi'},
  {work_content_cn: '多次', work_content_en: 'multi'},
];
let promptCount = 0;
['m', 'mu', 'mul', 'mult', 'multi'].forEach(v => {
  const r = handleCellEditLive(0, 'work_content_en', v);
  if (r.prompt) promptCount++;
});
test('Case F: 5 次 input 弹 0 次框', promptCount === 0, `实际 ${promptCount} 次`);
const rCommit = handleCellEditCommit(0, 'work_content_en', 'multi');
test('Case F: 离开框时弹 1 次', rCommit.prompt === true);

console.log('\n=== Rule 1 (1 条记录): pickCanonicalEnglish(自) ===');
tableData = [{work_content_cn: '孤', work_content_en: 'lonely'}];
test('Rule 1: 返回自身', pickCanonicalEnglish('孤', 0) === 'lonely');

console.log('\n=== Rule 2 (2 条记录, exclude 1 条) → 用"另一条" ===');
tableData = [
  {work_content_cn: '双', work_content_en: 'twin-A'},
  {work_content_cn: '双', work_content_en: 'twin-B'},
];
test('Rule 2: excludeIndex=0 → 用 B', pickCanonicalEnglish('双', 0) === 'twin-B');
test('Rule 2: excludeIndex=1 → 用 A', pickCanonicalEnglish('双', 1) === 'twin-A');

console.log('\n=== Rule 3 (>2 条, 多数派 2:1) → 用多数 ===');
tableData = [
  {work_content_cn: '多', work_content_en: 'many'},
  {work_content_cn: '多', work_content_en: 'many'},
  {work_content_cn: '多', work_content_en: 'odd'},
];
// 模拟"仅此条"：刚编辑的是 idx=2（odd 那条），exclude 它
test('Rule 3: exclude odd → 用 many', pickCanonicalEnglish('多', 2) === 'many');

console.log('\n=== Rule 4 (并列最多 1:1:1) → 随机 + 提示 ===');
tableData = [
  {work_content_cn: '平', work_content_en: 'A'},
  {work_content_cn: '平', work_content_en: 'B'},
  {work_content_cn: '平', work_content_en: 'C'},
];
toastMessages = [];
const got = pickCanonicalEnglish('平', -1);
const inTop = ['A','B','C'].includes(got);
test('Rule 4: 返回 A/B/C 之一', inTop, `got=${got}`);
test('Rule 4: 触发 toast', toastMessages.length === 1 && toastMessages[0].kind === 'warn');

console.log('\n=== 边界：中文空字符串 ===');
tableData = [{work_content_cn: '', work_content_en: 'x'}];
test('空中文不补', pickCanonicalEnglish('', 0) === null);

console.log(`\n=== 结果: ${pass} pass / ${fail} fail ===`);
process.exit(fail > 0 ? 1 : 0);
