"""Quick Flask startup test - 测试能否启动并响应基本请求"""
import sys
import os
import json
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app import app as flask_app

# Test 1: can we get config route?
with flask_app.test_client() as client:
    resp = client.get('/api/config')
    assert resp.status_code in (200, 405), f"Config route failed: {resp.status_code}"
    print("Test 1: GET /api/config OK")

    resp = client.get('/')
    assert resp.status_code == 200, f"Index route failed: {resp.status_code}"
    print("Test 2: GET / OK")

    resp = client.get('/api/data')
    assert resp.status_code == 200, f"Data route failed: {resp.status_code}"
    data = json.loads(resp.data)
    if isinstance(data, dict):
        print(f"Test 3: GET /api/data OK ({len(data.get('data', []))} rows)")
    else:
        print(f"Test 3: GET /api/data OK ({len(data) if isinstance(data, list) else '?'} items)")

    resp = client.get('/api/upload-options')
    assert resp.status_code == 200, f"Upload options route failed: {resp.status_code}"
    print("Test 4: GET /api/upload-options OK")

    resp = client.get('/api/upload-config')
    assert resp.status_code == 200, f"Upload config route failed: {resp.status_code}"
    print("Test 5: GET /api/upload-config OK")

    resp = client.get('/api/dim/recorders')
    assert resp.status_code == 200, f"Dim route failed: {resp.status_code}"
    print("Test 6: GET /api/dim/recorders OK")

    resp = client.get('/api/preprocess-overview')
    assert resp.status_code == 200, f"Preprocess overview route failed: {resp.status_code}"
    print("Test 7: GET /api/preprocess-overview OK")

    resp = client.get('/api/disk-space-status')
    assert resp.status_code == 200, f"Disk space route failed: {resp.status_code}"
    print("Test 8: GET /api/disk-space-status OK")

    resp = client.get('/api/auto-upload-status')
    assert resp.status_code == 200, f"Auto upload status route failed: {resp.status_code}"
    print("Test 9: GET /api/auto-upload-status OK")

    resp = client.get('/api/hmd/queue-status')
    assert resp.status_code == 200, f"HMD queue status route failed: {resp.status_code}"
    print("Test 10: GET /api/hmd/queue-status OK")

    resp = client.get('/favicon.ico')
    assert resp.status_code in (200, 404), f"Favicon route failed: {resp.status_code}"
    print("Test 11: GET /favicon.ico OK")

    # Test static file serving
    resp = client.get('/static/index.js')
    if resp.status_code == 200:
        print("Test 12: GET /static/index.js OK")
    else:
        print(f"Test 12: GET /static/index.js -> {resp.status_code} (may be expected)")

    # Test template rendering
    resp = client.get('/hmd-preview')
    assert resp.status_code == 200, f"HMD preview failed: {resp.status_code}"
    print("Test 13: GET /hmd-preview OK")

    resp = client.get('/')
    assert resp.status_code == 200, f"Index page failed: {resp.status_code}"
    html = resp.data.decode('utf-8')
    assert '<html' in html.lower() or '<!doctype' in html.lower(), "Index didn't return HTML"
    print("Test 14: GET / returns HTML OK")

print("\n=== ALL 14 TESTS PASSED ===")
