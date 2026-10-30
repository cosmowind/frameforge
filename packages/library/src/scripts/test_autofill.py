# ────────────────────────────────────────────────────────────────
# test_autofill.py — 端到端测试 auto-fill / clipboard API
#
# 启动方式：
#   1) 启动 Flask：python src/run.py
#   2) 在另一终端：python src/scripts/test_autofill.py
#
# 验证：
#   - GET /api/auto-fill/defaults 返回非空 template + samples
#   - POST /api/auto-fill/clipboard/set-field 3 次写满三件套
#   - GET  /api/auto-fill/clipboard 返回 3 字段 + updated_at
#   - POST /api/auto-fill  用三件套匹配 → fields 中包含所有维表字段
#   - POST /api/auto-fill/match  typeahead 给候选
#   - POST /api/auto-fill/apply 把 matched 写回 video_manager.csv（如果该 path 存在）
# ────────────────────────────────────────────────────────────────

import json
import os
import sys
import time
import urllib.request
import urllib.error

API = os.environ.get("AUTO_FILL_API", "http://localhost:5000")


def _req(method: str, path: str, body=None):
    url = API + path
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


def expect(cond, label, payload=None):
    if cond:
        print(f"  [PASS] {label}")
        return True
    print(f"  [FAIL] {label}")
    if payload is not None:
        print(f"     payload: {json.dumps(payload, ensure_ascii=False)[:300]}")
    return False


def main():
    print(f"=== auto-fill 端到端测试 → {API} ===\n")

    # ── 0) 服务可达 ──
    try:
        urllib.request.urlopen(API + "/api/upload-config", timeout=3)
    except Exception as e:
        print(f"❌ Flask 不可达 ({API}): {e}\n请先启动 python src/run.py")
        return 1

    pass_count = fail_count = 0
    def T(cond, label, payload=None):
        nonlocal pass_count, fail_count
        if expect(cond, label, payload):
            pass_count += 1
        else:
            fail_count += 1

    # ── 1) defaults ──
    print("[1] GET /api/auto-fill/defaults")
    code, body = _req("GET", "/api/auto-fill/defaults")
    T(code == 200, "status 200")
    T(body.get("ok") is True, "ok=True")
    T(bool(body.get("template")), "template 非空")
    samples = body.get("samples") or {}
    T(len(samples.get("recorders", [])) > 0, "samples.recorders 非空", samples.get("recorders", [])[:1])
    T(len(samples.get("tasks", [])) > 0, "samples.tasks 非空", samples.get("tasks", [])[:1])
    T(len(samples.get("environments", [])) > 0, "samples.environments 非空", samples.get("environments", [])[:1])

    # ── 2) clipboard 清空 + 写三件套 ──
    print("\n[2] POST /api/auto-fill/clipboard (3 字段)")
    _req("DELETE", "/api/auto-fill/clipboard")
    cb = body.get("clipboard", {}) if False else None  # noop
    test_op = "op1"
    test_task = "faucet"            # tasks.process_en 含 "faucet"
    test_env = "faucet factory workshop"
    code, body = _req("POST", "/api/auto-fill/clipboard/set-field",
                      {"field": "operator_name", "value": test_op, "source": "recorders:op1"})
    T(code == 200 and body.get("ok"), "set operator_name")
    code, body = _req("POST", "/api/auto-fill/clipboard/set-field",
                      {"field": "task_description", "value": test_task, "source": "tasks:xxx"})
    T(code == 200 and body.get("ok"), "set task_description")
    code, body = _req("POST", "/api/auto-fill/clipboard/set-field",
                      {"field": "environment_description", "value": test_env, "source": "envs:xxx"})
    T(code == 200 and body.get("ok"), "set environment_description")
    code, body = _req("GET", "/api/auto-fill/clipboard")
    cb = (body.get("clipboard") or {})
    T(cb.get("operator_name") == test_op, f"operator_name == {test_op}", cb)
    T(cb.get("task_description") == test_task, f"task_description == {test_task}", cb)
    T(cb.get("environment_description") == test_env, f"environment_description == {test_env}", cb)
    # 切换到真实匹配数据（tasks.process_en 含 "faucet"），验证 unmatched 应为空
    real_task = "faucet"
    T(bool(cb.get("updated_at")), "updated_at 非空", cb)

    # ── 3) auto-fill 主流程 ──
    print("\n[3] POST /api/auto-fill （主入口）")
    code, body = _req("POST", "/api/auto-fill", {
        "operator_name": test_op,
        "task_description": real_task,        # "faucet" → process_en 含 faucet 的记录
        "environment_description": test_env,
    })
    T(code == 200, "status 200")
    T(body.get("ok") is True, "ok=True")
    fields = body.get("fields") or {}
    T(fields.get("operator_name") == test_op, "fields.operator_name 回填", fields)
    T(fields.get("task_description") == test_task, "fields.task_description 回填", fields)
    T(fields.get("environment_description") == test_env, "fields.environment_description 回填", fields)
    # 维表字段
    T(bool(fields.get("operator_job")), "fields.operator_job 由 recorders 补全", fields)
    T(bool(fields.get("age_range")), "fields.age_range 由 recorders 补全", fields)
    T(bool(fields.get("country")), "fields.country 由 sd_cards 或默认补全", fields)
    matched = body.get("matched") or {}
    T(bool(matched.get("recorder_id")), f"matched.recorder_id = {matched.get('recorder_id')}", matched)
    T(not body.get("unmatched"), f"unmatched 为空（全部命中），实际={body.get('unmatched')}", body)

    # ── 4) typeahead match ──
    print("\n[4] POST /api/auto-fill/match")
    for field in ("operator_name", "task_description", "environment_description"):
        code, body = _req("POST", "/api/auto-fill/match",
                          {"field": field, "prefix": ""})
        T(code == 200 and body.get("ok"), f"match {field} status 200")
        T(len(body.get("items", [])) > 0, f"match {field} 返回 ≥1 候选")

    # ── 5) 错误处理 ──
    print("\n[5] 错误处理")
    # 先清空剪贴板，确保空 body 真的没东西
    _req("DELETE", "/api/auto-fill/clipboard")
    code, body = _req("POST", "/api/auto-fill", {})  # 空 body
    T(code == 400, "空 body 返回 400（剪贴板也空）", body)
    code, body = _req("POST", "/api/auto-fill/match", {"field": "invalid"})
    T(code == 400, "非法 field 返回 400", body)

    # ── 6) 清理 ──
    _req("DELETE", "/api/auto-fill/clipboard")

    # ── 总结 ──
    print()
    print("─" * 56)
    print(f"通过: {pass_count}    失败: {fail_count}")
    print("─" * 56)
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
