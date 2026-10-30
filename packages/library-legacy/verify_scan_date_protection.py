"""端到端测试 scan_date 保护逻辑"""
import json
import sys
import urllib.request

# Windows GBK stdout 兼容：避免 emoji 打印失败
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = "http://localhost:5000"

def get(path):
    return json.load(urllib.request.urlopen(BASE + path))

def post(path, body):
    req = urllib.request.Request(
        BASE + path, method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps(body).encode("utf-8"),
    )
    return json.load(urllib.request.urlopen(req))

# 读初始数据
data = get("/api/data")
original_scan = data[0]["scan_date"]
original_orig = data[0]["original_history_date"]
test_path = data[0]["path"]
print(f"测试路径: {test_path}")
print(f"原始 scan_date: {original_scan!r}, orig: {original_orig!r}\n")

# === 测试 1: 恶意清空 scan_date 应被保护 ===
print("=== 测试 1: 清空 scan_date 后保存 ===")
data[0]["scan_date"] = ""
data[0]["work_content_cn"] = "测试清空攻击"
resp = post("/api/save", data)
print(f"  response: {resp}")
data2 = get("/api/data")
print(f"  save 后 scan_date: {data2[0]['scan_date']!r}  (应等于 {original_scan!r})")
assert data2[0]["scan_date"] == original_scan, "[FAIL] scan_date 被覆盖了!"
assert data2[0]["work_content_cn"] == "测试清空攻击", "[FAIL] work_content_cn 应被保存"
print("  [OK] scan_date 保住 + 中文描述保存成功\n")

# === 测试 2: 正常编辑（不改 scan_date） ===
print("=== 测试 2: 正常编辑（不动 scan_date）===")
data2[0]["work_content_cn"] = "正常编辑测试"
resp = post("/api/save", data2)
print(f"  response: {resp}")
data3 = get("/api/data")
assert data3[0]["work_content_cn"] == "正常编辑测试"
assert data3[0]["scan_date"] == original_scan
print("  [OK] 正常编辑 + scan_date 不变\n")

# === 测试 3: 显式改 scan_date（用户主动解锁后改）应被允许 ===
print("=== 测试 3: 显式改 scan_date（用户主动）===")
data3[0]["scan_date"] = "2025-01-01"
resp = post("/api/save", data3)
print(f"  response: {resp}")
data4 = get("/api/data")
assert data4[0]["scan_date"] == "2025-01-01", "[FAIL] 用户显式改 scan_date 不应被回滚"
print(f"  save 后 scan_date: {data4[0]['scan_date']!r}  [OK] 用户主动改值被允许\n")

# === 测试 4: 修复回原值（以免污染测试数据） ===
print("=== 测试 4: 还原 ===")
data4[0]["scan_date"] = original_scan
data4[0]["work_content_cn"] = ""
post("/api/save", data4)
print("  [OK] 已还原\n")

print("[PASS] 全部通过")
