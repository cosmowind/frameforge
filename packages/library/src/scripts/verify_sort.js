// 端到端测试：排序 3 状态循环 + 多列优先级 + 后端持久化
const http = require('http');

const BASE = 'http://localhost:5000';

function req(method, path, body) {
  return new Promise((resolve, reject) => {
    const data = body ? JSON.stringify(body) : null;
    const r = http.request(BASE + path, {
      method,
      headers: data ? { 'Content-Type': 'application/json' } : {}
    }, res => {
      let buf = '';
      res.on('data', c => buf += c);
      res.on('end', () => {
        try { resolve({ status: res.statusCode, body: JSON.parse(buf) }); }
        catch (e) { resolve({ status: res.statusCode, body: buf }); }
      });
    });
    r.on('error', reject);
    if (data) r.write(data);
    r.end();
  });
}

// 复制 templates/index.html 里的状态机和比较函数
let sortStack = [];

function toggleSort(colKey) {
  const idx = sortStack.findIndex(s => s.col === colKey);
  if (idx === -1) {
    sortStack.push({ col: colKey, dir: 'asc' });
  } else {
    const cur = sortStack[idx];
    if (cur.dir === 'asc') {
      cur.dir = 'desc';
      sortStack.splice(idx, 1);
      sortStack.push(cur);
    } else {
      sortStack.splice(idx, 1);
    }
  }
}

function compareSingle(aVal, bVal) {
  const aStr = String(aVal ?? '');
  const bStr = String(bVal ?? '');
  if (aStr !== '' && bStr !== '') {
    const aNum = parseFloat(aStr);
    const bNum = parseFloat(bStr);
    if (!isNaN(aNum) && !isNaN(bNum)) return aNum - bNum;
  }
  if (/^\d{4}-\d{2}-\d{2}/.test(aStr) && /^\d{4}-\d{2}-\d{2}/.test(bStr)) {
    const aDate = new Date(aStr);
    const bDate = new Date(bStr);
    if (!isNaN(aDate.getTime()) && !isNaN(bDate.getTime())) return aDate.getTime() - bDate.getTime();
  }
  return aStr.localeCompare(bStr, 'zh-Hans-CN');
}

function compareRows(a, b) {
  for (const { col, dir } of sortStack) {
    const cmp = compareSingle(a[col], b[col]);
    if (cmp !== 0) return dir === 'asc' ? cmp : -cmp;
  }
  return 0;
}

let pass = 0, fail = 0;
function check(name, cond, extra) {
  if (cond) { pass++; console.log('  [PASS]', name); }
  else { fail++; console.log('  [FAIL]', name, extra || ''); }
}

// === 用例 1: 3 状态循环 ===
console.log('=== 用例 1: 3 状态循环（无 → 升 → 降 → 无）===');
sortStack = [];
toggleSort('score');
check('第 1 次点击 → 升序', sortStack.length === 1 && sortStack[0].dir === 'asc' && sortStack[0].col === 'score');
toggleSort('score');
check('第 2 次点击 → 降序', sortStack.length === 1 && sortStack[0].dir === 'desc');
toggleSort('score');
check('第 3 次点击 → 移除（无排序）', sortStack.length === 0);

// === 用例 2: 多列优先级 — 最后点击的 = 最高优先级 ===
console.log('\n=== 用例 2: 多列排序 — 最后点的 = 第一优先级 ===');
sortStack = [];
toggleSort('category');  // 第 1 次：category 升
toggleSort('score');     // 第 2 次：score 升（第一优先）
toggleSort('recorder');  // 第 3 次：recorder 升（最优先）
check('3 列都在栈里', sortStack.length === 3);
check('栈末尾是 recorder（最高优先级）', sortStack[2].col === 'recorder' && sortStack[2].dir === 'asc');
check('栈头部是 category（最低优先级）', sortStack[0].col === 'category');

// === 用例 3: 多列排序结果正确 ===
// sortStack 顺序 = 优先级顺序：第 1 个是最高优先级
// 预期：先按 category 升（X 排在 Y 前），同 category 时按 score 升（5 排在 10 前）
// → A(X,5), D(X,5), B(X,10), C(Y,3)
console.log('\n=== 用例 3: 多列排序结果正确 ===');
sortStack = [];
const data = [
  { name: 'A', category: 'X', score: 5 },
  { name: 'B', category: 'X', score: 10 },
  { name: 'C', category: 'Y', score: 3 },
  { name: 'D', category: 'X', score: 5 },
];
toggleSort('category');  // 栈：[category asc] — 最高优先级
toggleSort('score');     // 栈：[category asc, score asc] — score 是最高优先级
const sorted = [...data].sort(compareRows);
check('A 在最前（X 类别 + score=5）', sorted[0].name === 'A');
check('C 在最后（Y 类别，category 升序时 Y 在 X 后）', sorted[3].name === 'C' && sorted[3].category === 'Y');
check('中间两个是 X 类别 score=5 的 D 和 score=10 的 B（D 在 B 前）',
  sorted[1].name === 'D' && sorted[1].score === 5 &&
  sorted[2].name === 'B' && sorted[2].score === 10);

// === 用例 4: 点击已降序列再次循环后，其他列优先级不变 ===
console.log('\n=== 用例 4: 移除某列后其余列优先级保持 ===');
sortStack = [];
toggleSort('category');
toggleSort('score');
toggleSort('recorder');
// 当前：[category asc, score asc, recorder desc]
const beforeRemove = JSON.parse(JSON.stringify(sortStack));
// 移除 recorder 回到无排序：第 4 次点 recorder
toggleSort('recorder');  // 当前是 desc → 移除
// 但 score 当前是 asc，不是 desc；这里 toggleSort 找到 recorder 移除
// 重新检查：需要先看 recorder 当前是 desc 还是 asc
// 重新做一遍更明确的测试
sortStack = [];
toggleSort('a');
toggleSort('b');
// 现在 [a asc, b asc]  -  b 是第一优先
toggleSort('a');  // a 从 asc 升到 desc 并移至末尾 → [b asc, a desc]，a 是第一优先
check('a 升级后变第一优先', sortStack[0].col === 'b' && sortStack[1].col === 'a' && sortStack[1].dir === 'desc');
toggleSort('a');  // a 从 desc → 移除
check('a 被移除后剩 b asc（其他列不变）', sortStack.length === 1 && sortStack[0].col === 'b' && sortStack[0].dir === 'asc');

// === 用例 5: 数字 / 日期 / 字符串三种类型都能排 ===
console.log('\n=== 用例 5: 三种类型列都能排 ===');
sortStack = [{ col: 'score', dir: 'desc' }];
const dataNum = [{ name: 'a', score: 1 }, { name: 'b', score: 100 }, { name: 'c', score: 50 }];
const r5a = [...dataNum].sort(compareRows);
check('数字降序：100, 50, 1', r5a[0].score === 100 && r5a[1].score === 50 && r5a[2].score === 1);

sortStack = [{ col: 'date', dir: 'asc' }];
const dataDate = [{ name: 'a', date: '2026-01-01' }, { name: 'b', date: '2025-12-31' }, { name: 'c', date: '2026-06-09' }];
const r5b = [...dataDate].sort(compareRows);
check('日期升序：2025-12-31, 2026-01-01, 2026-06-09',
  r5b[0].date === '2025-12-31' && r5b[1].date === '2026-01-01' && r5b[2].date === '2026-06-09');

sortStack = [{ col: 'name', dir: 'asc' }];
const dataStr = [{ name: 'banana' }, { name: 'apple' }, { name: 'cherry' }];
const r5c = [...dataStr].sort(compareRows);
check('字符串升序：apple, banana, cherry',
  r5c[0].name === 'apple' && r5c[1].name === 'banana' && r5c[2].name === 'cherry');

// === 用例 6: 后端持久化 sortStack ===
console.log('\n=== 用例 6: 后端持久化 sortStack + 旧字段兼容 ===');
const stack = [{ col: 'work_content_cn', dir: 'asc' }, { col: 'score', dir: 'desc' }];
// 模拟前端 saveColConfig 行为：sortStack + 兼容旧字段一起 POST
req('POST', '/api/config', {
  sortStack: stack,
  sortColumn: stack[stack.length - 1].col,        // 栈末 = 当前主排序列
  sortDirection: stack[stack.length - 1].dir
})
  .then(r => {
    check('POST /api/config 返回 ok', r.body.ok === true);
    return req('GET', '/api/config');
  })
  .then(r => {
    const cfg = r.body;
    const got = cfg.sortStack;
    check('GET 读回 sortStack 长度 = 2', got && got.length === 2);
    check('第 1 优先是 work_content_cn asc（push 顺序 = 优先级）',
      got[0].col === 'work_content_cn' && got[0].dir === 'asc' &&
      got[1].col === 'score' && got[1].dir === 'desc');
    // 兼容旧字段：栈末（最高优先级）写为 sortColumn/sortDirection
    check('兼容 sortColumn = 栈末 col', cfg.sortColumn === 'score');
    check('兼容 sortDirection = 栈末 dir', cfg.sortDirection === 'desc');

    // 清空所有排序字段（避免旧 sortColumn 残留影响下次测试）
    return req('POST', '/api/config', { sortStack: [], sortColumn: '', sortDirection: 'asc' });
  })
  .then(() => {
    console.log(`\n=== 结果: ${pass} pass / ${fail} fail ===`);
    process.exit(fail > 0 ? 1 : 0);
  })
  .catch(e => { console.error('网络错误:', e.message); process.exit(2); });
