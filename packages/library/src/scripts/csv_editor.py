# ────────────────────────────────────────────────────────────────
# csv_editor.py — CSV Web 编辑器（Flask）
# 下拉显示中文，选中后自动填 ID + 英文字段
# 运行：python src/scripts/csv_editor.py
# 访问：http://localhost:5001
# ────────────────────────────────────────────────────────────────

from flask import Flask, render_template_string, request, jsonify
import csv, os, json

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV_PATH = os.path.join(BASE_DIR, "runtime", "data", "video_batch_config.csv")
DIM_DIR  = os.path.join(BASE_DIR, "runtime", "data")

HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Video Batch Config Editor</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: -apple-system, 'Segoe UI', sans-serif; margin: 0; padding: 16px;
         background: #f5f5f5; color: #333; font-size: 13px; }
  h1 { font-size: 20px; margin: 0 0 12px; }
  .stats { display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
  .stat { background: #fff; padding: 12px 16px; border-radius: 8px;
          box-shadow: 0 1px 3px rgba(0,0,0,.1); }
  .stat .num { font-size: 24px; font-weight: 700; }
  .stat .label { font-size: 12px; color: #888; }
  .filters { display: flex; gap: 12px; margin-bottom: 12px; flex-wrap: wrap; align-items: center; }
  .filters label { font-size: 13px; }
  .filters select { padding: 4px 8px; font-size: 13px; }
  table { width: 100%; border-collapse: collapse; background: #fff;
          box-shadow: 0 1px 3px rgba(0,0,0,.1); border-radius: 8px; overflow: hidden; }
  th { background: #f0f0f0; font-size: 11px; text-align: left; padding: 6px 4px;
       position: sticky; top: 0; z-index: 1; white-space: nowrap; }
  td { padding: 3px 4px; font-size: 12px; border-top: 1px solid #eee; vertical-align: middle; }
  tr:hover { background: #fafafa; }
  tr.missing-row { background: #fff8e1; }
  tr.filled-row { background: #e8f5e9; }
  select.fs { width: 100%; padding: 3px 2px; font-size: 11px;
              border: 1px solid #ddd; border-radius: 3px; }
  input[type=text] { width: 100%; padding: 3px 4px; font-size: 11px;
                     border: 1px solid #ddd; border-radius: 3px; }
  input[type=text]:focus, select.fs:focus { border-color: #4a90d9; outline: none; }
  .badge { display: inline-block; padding: 1px 6px; border-radius: 8px;
           font-size: 10px; font-weight: 600; }
  .badge-red { background: #ffcdd2; color: #c62828; }
  .badge-green { background: #c8e6c9; color: #2e7d32; }
  .badge-gray { background: #e0e0e0; color: #666; }
  .saved-msg { position: fixed; bottom: 24px; right: 24px; padding: 8px 16px;
               background: #4caf50; color: #fff; border-radius: 6px;
               font-size: 13px; display: none; z-index: 10; }
  .cell-stack { display: flex; flex-direction: column; gap: 1px; }
  .auto-fill { font-size: 9px; color: #999; line-height: 1.2; max-width: 200px;
               overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
</head>
<body>
<h1>Video Batch Config Editor</h1>

<div class="stats">
  <div class="stat"><div class="num">{{ total }}</div><div class="label">Total</div></div>
  <div class="stat"><div class="num">{{ with_missing }}</div><div class="label">Has Missing</div></div>
  <div class="stat"><div class="num">{{ filled }}</div><div class="label">Filled</div></div>
  <div class="stat"><div class="num">{{ empty }}</div><div class="label">Empty</div></div>
</div>

<form method="GET" class="filters">
  <label>Show:
    <select name="filter" onchange="this.form.submit()">
      <option value="all" {{ 'selected' if filter=='all' else '' }}>All</option>
      <option value="missing" {{ 'selected' if filter=='missing' else '' }}>Missing &gt; 0</option>
      <option value="empty" {{ 'selected' if filter=='empty' else '' }}>Empty fields</option>
      <option value="filled" {{ 'selected' if filter=='filled' else '' }}>Already filled</option>
    </select>
  </label>
</form>

<form method="POST" id="editForm">
<input type="hidden" name="filter" value="{{ filter }}">
<table>
<thead>
<tr>
  <th style="width:25px">#</th>
  <th style="width:120px">Session ID</th>
  <th style="width:65px">Date</th>
  <th style="width:45px">Duration</th>
  <th style="width:35px">Missing</th>
  <th style="width:150px">Recorder (录入员)</th>
  <th style="width:220px">Task (任务) <button type="button" onclick="refreshTasks()" style="font-size:10px;padding:1px 6px;cursor:pointer;border:1px solid #ccc;border-radius:3px;background:#fff;" title="刷新任务列表（无需刷新页面）">↻</button></th>
  <th style="width:200px">Env (环境)</th>
  <th>Notes</th>
</tr>
</thead>
<tbody>
{% for row in rows %}
<tr class="{{ 'missing-row' if row.missing|int > 0 else ('filled-row' if row.recorder_id and row.task_id else '') }}">
  <td style="font-size:10px;color:#888">{{ loop.index }}</td>
  <td style="font-size:10px;word-break:break-all">{{ row.session_id }}</td>
  <td style="font-size:10px">{{ row.date }}</td>
  <td style="font-size:10px">{{ row.duration }}</td>
  <td>
    {% if row.missing|int > 0 %}
      <span class="badge badge-red">{{ row.missing }}</span>
    {% elif row.missing == '0' %}
      <span class="badge badge-green">0</span>
    {% else %}
      <span class="badge badge-gray">?</span>
    {% endif %}
  </td>
  {# ── Recorder ── #}
  <td>
    <div class="cell-stack">
      <select class="fs" onchange="pickRecorder('{{ row.uid }}', this.value)">
        <option value="">-- 选择录入员 --</option>
        {% for c in recorders %}
        <option value="{{ c.id }}" {{ 'selected' if row.recorder_id == c.id else '' }}>{{ c.name }}（{{ c.id }}）</option>
        {% endfor %}
      </select>
      <input type="text" id="cid_{{ row.uid }}" name="recorder_{{ row.uid }}" value="{{ row.recorder_id }}" readonly style="background:#f5f5f5">
      <div class="auto-fill" id="cname_{{ row.uid }}">{{ row._recorder_name }}</div>
    </div>
  </td>
  {# ── Task ── #}
  <td>
    <div class="cell-stack">
      <select class="fs" onchange="pickTask('{{ row.uid }}', this.value)">
        <option value="">-- 选择任务 --</option>
        {% for t in tasks %}
        <option value="{{ t.task_id }}" {{ 'selected' if row.task_id == t.task_id else '' }}>{{ t.product }}｜{{ t.task }}｜{{ t.process }}</option>
        {% endfor %}
      </select>
      <input type="text" id="tid_{{ row.uid }}" name="task_{{ row.uid }}" value="{{ row.task_id }}" readonly style="background:#f5f5f5">
      <div class="auto-fill" id="tdesc_{{ row.uid }}">{{ row._task_process_en }}</div>
    </div>
  </td>
  {# ── Env ── #}
  <td>
    <div class="cell-stack">
      <select class="fs" onchange="pickEnv('{{ row.uid }}', this.value)">
        <option value="">-- 选择环境 --</option>
        {% for e in envs %}
        <option value="{{ e.env_id }}" {{ 'selected' if row.env_id == e.env_id else '' }}>{{ e.environment_description }}</option>
        {% endfor %}
      </select>
      <input type="text" id="eid_{{ row.uid }}" name="env_{{ row.uid }}" value="{{ row.env_id }}" readonly style="background:#f5f5f5">
      <div class="auto-fill" id="edesc_{{ row.uid }}">{{ row._env_desc_en }}</div>
    </div>
  </td>
  <td><input type="text" name="notes_{{ row.uid }}" value="{{ row.notes }}" placeholder=""></td>
</tr>
{% endfor %}
</tbody>
</table>
</form>

<div class="saved-msg" id="savedMsg">✓ Saved</div>

<script>
var recorders = {{ recorders_json | safe }};
var tasks = {{ tasks_json | safe }};
var envs = {{ envs_json | safe }};

var cMap = {}; recorders.forEach(function(c){ cMap[c.id]=c; });
var tMap = {}; tasks.forEach(function(t){ tMap[t.task_id]=t; });
var eMap = {}; envs.forEach(function(e){ eMap[e.env_id]=e; });

function pickRecorder(uid, val){
  document.getElementById('cid_'+uid).value = val;
  var c = cMap[val];
  document.getElementById('cname_'+uid).textContent = c ? c.name : '';
  saveRow(uid);
}
function pickTask(uid, val){
  document.getElementById('tid_'+uid).value = val;
  var t = tMap[val];
  document.getElementById('tdesc_'+uid).textContent = t ? t.process_en : '';
  saveRow(uid);
}

// ── 刷新任务下拉（无需刷新整个页面）──
function refreshTasks(){
  fetch('/api/tasks').then(function(r){return r.json()}).then(function(list){
    tasks = list;
    tMap = {}; tasks.forEach(function(t){ tMap[t.task_id]=t; });
    document.querySelectorAll('select.fs').forEach(function(sel){
      // 只更新 onchange 含 pickTask 的 select（任务列）
      if(!sel.getAttribute('onchange') || sel.getAttribute('onchange').indexOf('pickTask')<0) return;
      var curVal = sel.value;
      sel.innerHTML = '<option value="">-- 选择任务 --</option>';
      tasks.forEach(function(t){
        var opt = document.createElement('option');
        opt.value = t.task_id;
        opt.textContent = t.product + '｜' + t.task + '｜' + t.process;
        if(t.task_id === curVal) opt.selected = true;
        sel.appendChild(opt);
      });
    });
    var m=document.getElementById('savedMsg');
    m.textContent='✓ 已刷新 '+tasks.length+' 个任务';
    m.style.display='block';
    setTimeout(function(){m.style.display='none'; m.textContent='✓ Saved';},1500);
  }).catch(function(e){ console.error('[refreshTasks]',e); });
}
function pickEnv(uid, val){
  document.getElementById('eid_'+uid).value = val;
  var e = eMap[val];
  document.getElementById('edesc_'+uid).textContent = e ? e.environment_description_en : '';
  saveRow(uid);
}

// ── Save single row ──
function saveRow(uid){
  var data = {
    uid: uid,
    recorder_id: document.getElementById('cid_'+uid).value,
    task_id: document.getElementById('tid_'+uid).value,
    env_id: document.getElementById('eid_'+uid).value,
    notes: document.querySelector('input[name="notes_'+uid+'"]').value
  };
  console.log('[saveRow]', uid, data);
  fetch('/save_row',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(data)
  }).then(function(r){return r.json()})
    .then(function(d){
      console.log('[saveRow] ok:', d);
      if(d.ok){
        var m=document.getElementById('savedMsg');
        m.style.display='block';
        setTimeout(function(){m.style.display='none'},1200);
      }
    }).catch(function(e){console.error('[saveRow] err:',e)});
}

// Listen on notes text inputs
document.addEventListener('input', function(e){
  if(e.target.tagName==='INPUT' && e.target.type==='text' && e.target.name.indexOf('notes_')===0){
    var uid = e.target.name.replace('notes_','');
    saveRow(uid);
  }
});
</script>
</body>
</html>
"""


def load_dim(name, sort_key=None):
    path = os.path.join(DIM_DIR, name)
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    if sort_key:
        rows.sort(key=sort_key)
    return rows


def load_csv():
    rows = []
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            for k in ['missing','notes','duration','recorder_id','task_id','env_id',
                       'operator_name','task_description','environment_description']:
                row.setdefault(k, '')
            row['uid'] = f"{row['session_id']}_{row['date']}"
            rows.append(row)
    return rows


def save_csv(rows):
    headers = ['session_id', 'date', 'duration', 'score', 'missing',
               'recorder_id', 'task_id', 'env_id',
               'operator_name', 'task_description', 'environment_description', 'notes']
    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def enrich_rows(rows, recorders, tasks, envs):
    cMap = {c['id']: c for c in recorders}
    tMap = {t['task_id']: t for t in tasks}
    eMap = {e['env_id']: e for e in envs}
    for r in rows:
        c = cMap.get(r.get('recorder_id', ''), {})
        t = tMap.get(r.get('task_id', ''), {})
        e = eMap.get(r.get('env_id', ''), {})
        r['_recorder_name'] = c.get('name', '')
        r['_task_process_en'] = t.get('process_en', '')
        r['_env_desc_en'] = e.get('environment_description_en', '')
        # Auto-fill downstream English fields
        if r.get('recorder_id') and c:
            r['operator_name'] = c.get('name', '')
        if r.get('task_id') and t:
            r['task_description'] = t.get('process_en', '')
        if r.get('env_id') and e:
            r['environment_description'] = e.get('environment_description_en', '')
    return rows


@app.route('/')
def index():
    recorders = load_dim('recorders.csv')
    tasks = load_dim('tasks.csv', sort_key=lambda t: (
        (t.get('product') or '').lower(),
        (t.get('task') or '').lower(),
        (t.get('tool') or '').lower(),
    ))
    envs = load_dim('environments.csv')
    rows = enrich_rows(load_csv(), recorders, tasks, envs)

    filter_type = request.args.get('filter', 'all')
    if filter_type == 'missing':
        drows = [r for r in rows if r.get('missing','') not in ('','0','-1','-2')]
    elif filter_type == 'empty':
        drows = [r for r in rows if not r.get('recorder_id','').strip() and not r.get('task_id','').strip()]
    elif filter_type == 'filled':
        drows = [r for r in rows if r.get('recorder_id','').strip() and r.get('task_id','').strip()]
    else:
        drows = rows

    total = len(rows)
    with_missing = sum(1 for r in rows if r.get('missing','') not in ('','0','-1','-2'))
    filled = sum(1 for r in rows if r.get('recorder_id','').strip() and r.get('task_id','').strip())
    return render_template_string(HTML,
        rows=drows, filter=filter_type,
        total=total, with_missing=with_missing,
        filled=filled, empty=total-filled,
        recorders=recorders, tasks=tasks, envs=envs,
        recorders_json=json.dumps(recorders, ensure_ascii=False),
        tasks_json=json.dumps(tasks, ensure_ascii=False),
        envs_json=json.dumps(envs, ensure_ascii=False))


@app.route('/save', methods=['POST'])
def save():
    rows = load_csv()
    for r in rows:
        uid = r['uid']
        r['recorder_id'] = request.form.get(f'recorder_{uid}', '')
        r['task_id'] = request.form.get(f'task_{uid}', '')
        r['env_id'] = request.form.get(f'env_{uid}', '')
        r['notes'] = request.form.get(f'notes_{uid}', '')

    cMap = {c['id']: c for c in load_dim('recorders.csv')}
    tMap = {t['task_id']: t for t in load_dim('tasks.csv')}
    eMap = {e['env_id']: e for e in load_dim('environments.csv')}
    for r in rows:
        c = cMap.get(r.get('recorder_id',''), {})
        t = tMap.get(r.get('task_id',''), {})
        e = eMap.get(r.get('env_id',''), {})
        if c: r['operator_name'] = c.get('name','')
        if t: r['task_description'] = t.get('process_en','')
        if e: r['environment_description'] = e.get('environment_description_en','')

    save_csv(rows)
    return jsonify({'ok': True})


@app.route('/save_row', methods=['POST'])
def save_row():
    """Save a single row (JSON body: uid, recorder_id, task_id, env_id, notes)."""
    data = request.get_json(force=True)
    uid = data.get('uid', '')

    rows = load_csv()
    cMap = {c['id']: c for c in load_dim('recorders.csv')}
    tMap = {t['task_id']: t for t in load_dim('tasks.csv')}
    eMap = {e['env_id']: e for e in load_dim('environments.csv')}

    for r in rows:
        if r['uid'] == uid:
            r['recorder_id'] = data.get('recorder_id', '')
            r['task_id'] = data.get('task_id', '')
            r['env_id'] = data.get('env_id', '')
            r['notes'] = data.get('notes', '')
            c = cMap.get(r['recorder_id'], {})
            t = tMap.get(r['task_id'], {})
            e = eMap.get(r['env_id'], {})
            if c: r['operator_name'] = c.get('name', '')
            if t: r['task_description'] = t.get('process_en', '')
            if e: r['environment_description'] = e.get('environment_description_en', '')
            break

    save_csv(rows)
    return jsonify({'ok': True})


@app.route('/api/tasks')
def api_tasks():
    tasks = load_dim('tasks.csv', sort_key=lambda t: (
        (t.get('product') or '').lower(),
        (t.get('task') or '').lower(),
        (t.get('tool') or '').lower(),
    ))
    return jsonify(tasks)


if __name__ == '__main__':
    print(f"CSV Editor: http://localhost:5001")
    app.run(host='0.0.0.0', port=5001, debug=False)
